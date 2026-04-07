"""
rag_pipeline.py — Full RAG pipeline following technical guide v2.2
Router → Query Rewrite → Entity Extract → HyDE → Hybrid Search → Rerank → Self-Reflect → Generate
"""
import re
import os
import pickle
import time
import requests
import json
import numpy as np

import ollama as ollama_client
import chromadb

from src.config import (
    OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_EMBED_MODEL, ROUTER_MODEL,
    RERANKER_URL, USE_REMOTE_RERANKER,
    HYDE_ENABLED, QUERY_REWRITE_ENABLED, SELF_REFLECT_ENABLED,
    ROUTER_TIMEOUT, RETRIEVER_LLM_TIMEOUT,
    VECTORSTORE_DIR, BM25_PATH, CHUNKS_PATH,
    HAUI_DEBUG,
    RAG_LITE, HYDE_INTENTS, SELF_REFLECT_INTENTS,
)
from src.rag.structured import try_deterministic_b1_answer, try_deterministic_kb_answer, enrich_context

try:
    from underthesea import word_tokenize
except ImportError:
    def word_tokenize(text):
        return text.split()

try:
    from rank_bm25 import BM25Okapi
except ImportError:
    BM25Okapi = None

# ══════════════════════════════════════════
#  GLOBAL STATE
# ══════════════════════════════════════════
_client = None
_chroma = None
_collection = None
_bm25 = None
_chunks = None

def get_ollama_client():
    global _client
    if _client is None:
        _client = ollama_client.Client(host=OLLAMA_BASE_URL)
    return _client

def load_index():
    global _chroma, _collection, _bm25, _chunks
    if os.path.exists(VECTORSTORE_DIR):
        _chroma = chromadb.PersistentClient(path=VECTORSTORE_DIR)
        try:
            _collection = _chroma.get_collection("haui_chunks")
            if HAUI_DEBUG:
                print(f"[INDEX] ChromaDB loaded: {_collection.count()} docs")
        except Exception:
            _collection = None
            if HAUI_DEBUG:
                print("[INDEX] ChromaDB collection not found")
    if os.path.exists(BM25_PATH) and BM25Okapi:
        with open(BM25_PATH, 'rb') as f:
            _bm25 = pickle.load(f)
        if HAUI_DEBUG:
            print("[INDEX] BM25 loaded")
    if os.path.exists(CHUNKS_PATH):
        with open(CHUNKS_PATH, 'rb') as f:
            _chunks = pickle.load(f)
        if HAUI_DEBUG:
            print(f"[INDEX] {len(_chunks)} chunks loaded")

def reload_index():
    global _chroma, _collection, _bm25, _chunks
    _chroma = None
    _collection = None
    _bm25 = None
    _chunks = None
    load_index()

# ══════════════════════════════════════════
#  LLM HELPERS
# ══════════════════════════════════════════
def call_llm(prompt, model=None, max_tokens=1024, temperature=0.05):
    if model is None:
        model = OLLAMA_MODEL
    client = get_ollama_client()
    try:
        response = client.generate(model=model, prompt=prompt, options={'num_predict': max_tokens, 'temperature': temperature})
        return response['response'].strip()
    except Exception as e:
        if HAUI_DEBUG:
            print(f"[LLM ERROR] {e}")
        return ""

def embed_query(query):
    client = get_ollama_client()
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    response = client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=prefixed)
    return response['embedding']

# ══════════════════════════════════════════
#  ENTITY EXTRACTION
# ══════════════════════════════════════════
ENTITY_PATTERNS = {
    'ma_nganh': r'\b7[0-9]{6}\b',
    'diem': r'\b([0-9]{1,2}(\.[0-9]{1,2})?)\s*(điểm|đ\b)',
    'to_hop': r'\b(A00|A01|A02|B00|C01|C02|C03|C04|D01|D04|D06|D07|D14|D15|DD2|X05|X06|X07|X25|X27)\b',
    'khu_vuc': r'\b(KV1|KV2-NT|KV2|KV3)\b',
    'nam': r'\b(2023|2024|2025|2026)\b',
    'phuong_thuc': r'\b(PT[1-6])\b',
}

NGANH_ALIASES = {
    'cntt': 'Công nghệ thông tin', 'công nghệ thông tin': 'Công nghệ thông tin',
    'ktpm': 'Kỹ thuật phần mềm', 'kỹ thuật phần mềm': 'Kỹ thuật phần mềm',
    'khmt': 'Khoa học máy tính', 'khoa học máy tính': 'Khoa học máy tính',
    'httt': 'Hệ thống thông tin', 'attt': 'An toàn thông tin',
    'an toàn thông tin': 'An toàn thông tin',
    'đa phương tiện': 'Công nghệ đa phương tiện',
    'mạng máy tính': 'Mạng máy tính và truyền thông dữ liệu',
    'cơ điện tử': 'Công nghệ kỹ thuật cơ điện tử',
    'cơ điện tử ô tô': 'Công nghệ kỹ thuật cơ điện tử ô tô',
    'robot': 'Robot và trí tuệ nhân tạo', 'robot ai': 'Robot và trí tuệ nhân tạo',
    'tự động hóa': 'Công nghệ kỹ thuật điều khiển và tự động hóa',
    'tđh': 'Công nghệ kỹ thuật điều khiển và tự động hóa',
    'điện tử viễn thông': 'Công nghệ kỹ thuật điện tử - viễn thông',
    'điện điện tử': 'Công nghệ kỹ thuật điện, điện tử',
    'cơ khí': 'Công nghệ kỹ thuật cơ khí', 'ô tô': 'Công nghệ kỹ thuật ô tô',
    'khuôn mẫu': 'Công nghệ kỹ thuật khuôn mẫu',
    'năng lượng tái tạo': 'Năng lượng tái tạo',
    'y sinh': 'Công nghệ kỹ thuật điện tử y sinh',
    'sản xuất thông minh': 'Kỹ thuật sản xuất thông minh',
    'kỹ thuật nhiệt': 'Công nghệ kỹ thuật nhiệt',
    'cơ khí động lực': 'Kỹ thuật cơ khí động lực',
    'hệ thống công nghiệp': 'Kỹ thuật hệ thống công nghiệp',
    'kế toán': 'Kế toán', 'kiểm toán': 'Kiểm toán', 'marketing': 'Marketing',
    'logistics': 'Logistics và quản lý chuỗi cung ứng',
    'quản trị kinh doanh': 'Quản trị kinh doanh',
    'tài chính ngân hàng': 'Tài chính – Ngân hàng',
    'nhân lực': 'Quản trị nhân lực',
    'phân tích dữ liệu': 'Phân tích dữ liệu kinh doanh',
    'kinh tế đầu tư': 'Kinh tế đầu tư', 'quản trị văn phòng': 'Quản trị văn phòng',
    'tiếng anh': 'Ngôn ngữ Anh', 'ngôn ngữ anh': 'Ngôn ngữ Anh',
    'tiếng trung': 'Ngôn ngữ Trung Quốc', 'ngôn ngữ trung': 'Ngôn ngữ Trung Quốc',
    'tiếng nhật': 'Ngôn ngữ Nhật', 'tiếng hàn': 'Ngôn ngữ Hàn Quốc',
    'ngôn ngữ học': 'Ngôn ngữ học', 'trung quốc học': 'Trung Quốc học',
    'du lịch': 'Du lịch', 'khách sạn': 'Quản trị khách sạn',
    'nhà hàng': 'Quản trị nhà hàng và dịch vụ ăn uống',
    'lữ hành': 'Quản trị dịch vụ du lịch và lữ hành',
    'hoá học': 'Công nghệ kỹ thuật hóa học', 'hóa học': 'Công nghệ kỹ thuật hóa học',
    'môi trường': 'Công nghệ kỹ thuật môi trường',
    'thực phẩm': 'Công nghệ thực phẩm', 'hóa dược': 'Hóa dược',
    'dệt may': 'Công nghệ dệt, may', 'vật liệu dệt': 'Công nghệ vật liệu dệt, may',
    'thời trang': 'Thiết kế thời trang',
}

NHOM_KEYWORDS = {
    'cntt': 'CNTT', 'công nghệ thông tin': 'CNTT', 'it': 'CNTT',
    'lập trình': 'CNTT', 'phần mềm': 'CNTT',
    'cơ khí': 'Cơ khí', 'ô tô': 'Cơ khí', 'điện': 'Cơ khí',
    'robot': 'Cơ khí', 'tự động hóa': 'Cơ khí', 'cơ điện tử': 'Cơ khí',
    'kinh tế': 'Kinh tế', 'kế toán': 'Kinh tế', 'tài chính': 'Kinh tế',
    'marketing': 'Kinh tế', 'logistics': 'Kinh tế',
    'ngôn ngữ': 'Ngôn ngữ', 'tiếng': 'Ngôn ngữ', 'trung quốc': 'Ngôn ngữ',
    'du lịch': 'Du lịch', 'khách sạn': 'Du lịch', 'nhà hàng': 'Du lịch',
    'thực phẩm': 'Thực phẩm', 'hóa dược': 'Thực phẩm', 'hóa học': 'Thực phẩm',
    'dệt may': 'Dệt may', 'thời trang': 'Dệt may',
}

def extract_entities(query):
    entities = {}
    query_norm = query.lower()
    for key, pattern in ENTITY_PATTERNS.items():
        matches = re.findall(pattern, query, re.IGNORECASE)
        if matches:
            if key == 'to_hop':
                entities[key] = [m if isinstance(m, str) else m[0] for m in matches]
            elif key == 'diem':
                entities[key] = [m[0] if isinstance(m, tuple) else m for m in matches]
            else:
                match = matches[0]
                entities[key] = match if isinstance(match, str) else match[0]
    for alias, full_name in NGANH_ALIASES.items():
        if alias in query_norm:
            entities['ten_nganh'] = full_name
            break
    for kw, nhom in NHOM_KEYWORDS.items():
        if kw in query_norm:
            entities['nhom_nganh'] = nhom
            break
    return entities

# ══════════════════════════════════════════
#  ROUTER
# ══════════════════════════════════════════
FAST_PATTERNS = {
    'A1': [r'điểm chuẩn.*(ngành|mã)\s+\d{7}',
           r'học phí\s+(ngành|tín chỉ)', r'(học phí|mức thu).*(k20|k19|k18|tiếng anh|đại trà|thạc sĩ)',
           r'ký túc xá.*(giá|bao nhiêu|tiền)', r'phòng ktx.*(loại|chất lượng cao|tiêu chuẩn|\d+\s*người)',
           r'điểm chuẩn\s+\d{7}',
           r'(ngành|chuyên ngành)\s+\w+.*tổ hợp\s+(gì|nào)',
           r'ngành\s+\w+.*(ra trường|việc làm|làm gì|cơ hội)',
           r'(tỷ lệ|tỉ lệ).*(việc làm|tốt nghiệp|có việc)',
           r'(haui|đại học công nghiệp).*(là gì|trường gì|giới thiệu|bao nhiêu sinh viên|quy mô)',
           r'chương trình.*(liên kết|2\+2|song bằng)',
           r'(ngành|chuyên ngành)\s+.+\s+chỉ tiêu',
           ],
    'A2': [r'(các|tất cả|danh sách|toàn bộ).*(ngành|điểm chuẩn)', r'(điểm chuẩn|dc).*(các ngành|nhóm ngành)',
           r'tổng hợp.*(điểm chuẩn|chỉ tiêu)', r'so sánh.*(điểm chuẩn|các năm)',
           r'xu hướng.*(điểm chuẩn|\d+ năm)',
           r'xếp hạng.*(điểm chuẩn|ngành)',
           r'ngành nào.*(điểm.*(cao nhất|thấp nhất))',
           r'ngành nào.*(thi|xét).*(toán|lý|hóa|anh|văn)',
           ],
    'B1': [r'(tính|tôi được|em được).+điểm', r'\d+(\.\d+)?\s*(toán|lý|hóa|anh|văn)',
           r'quy đổi.*(hsa|tsa|đgnl|đgtd)', r'(kv1|kv2|kv3|kv2-nt).*(điểm|tính)',
           r'tính.*(học phí|hp)\s+\d+\s*(tín chỉ|tc)', r'học phí.*(học phần|\d+\s*tc|\d+\s*tín chỉ)',
           r'(hsa|tsa)\s+\d+',
           r'tổng\s+\d+\s*điểm.*(kv|đt|tính)',
           r'\d+\s*tín\s*chỉ.*(lý thuyết|thực hành|chuyên sâu).*(k20|học phí|hp)',
           r'tính\s+học\s*phí.*\d+\s*tín\s*chỉ',
           ],
    'B2': [r'ngành nào.*phù hợp', r'(nên|có thể).*(đăng ký|chọn) ngành', r'gợi ý ngành',
           r'với điểm.*(nên|có thể|đăng ký)', r'(đỗ|trúng tuyển).*(ngành|đâu)',
           r'em có thể vào.*ngành', r'ngành nào em.*(đỗ|vào được)'],
    'C': [r'(cách|làm thế nào|hướng dẫn).*(đăng ký|nộp|nhập học)', r'hồ sơ.*(cần|gồm|bao gồm)',
          r'(bước|thủ tục)', r'(deadline|hạn nộp|thời hạn).*(hồ sơ|đăng ký)',
          r'(học bổng|hỗ trợ tài chính).*(điều kiện|xét|cách|làm sao|loại|nào|mấy loại)',
          r'(ký túc xá|ktx).*(đăng ký|thủ tục|cách)', r'(nhập học|khai giảng|bắt đầu học)',
          r'(lịch|thời gian|khi nào).*(tuyển sinh|nhập học|xét tuyển|công bố|đăng ký)',
          r'phương thức.*(là gì|như thế nào|gồm|có mấy|những gì)',
          r'chỉ tiêu\s+20(25|26)(?!\s*\d{7})',
          r'lịch tuyển sinh\s+20(25|26)', r'(phương thức|pt[1-5])\s+(là gì|như thế nào)',
          r'điều kiện.*(pt[1-5]|phương thức|xét tuyển|đăng ký)',
          r'(văn bằng|bằng (gì|cấp|tốt nghiệp))',
          r'(mở thẻ|thẻ sinh viên)',
          r'cách tính học phí(?!.*\d+\s*(tc|tín chỉ))',
          r'(ielts|chứng chỉ).*(bao nhiêu|điều kiện|đủ|yêu cầu)',
          r'(ưu tiên|đối tượng).*(ut1|ut2|đt\s*\d|nhóm|cộng|mấy điểm|bao nhiêu)',
          r'(người khuyết tật|thương binh|con liệt sĩ).*(điểm|ưu tiên)',
          r'(tuyển|lấy) bao nhiêu.*(sinh viên|sv|chỉ tiêu)',
          r'(thí sinh tự do|tốt nghiệp trước).*(xét|được|pt)',
          r'(gửi|nộp).*hồ sơ.*(bản cứng|bản giấy)',
          ],
    'D': [r'(so sánh|khác nhau|giống nhau).*(ngành|phương thức)',
          r'nên chọn.*(ngành|phương thức).*(hay|hoặc)',
          r'(pt\d)\s+(và|vs|hay|khác)\s+(pt\d)',
          ],
    'E': [r'^(xin chào|chào bạn|chào em|hello|hi|hey)\s*[!?.]*$',
          r'^(ok|được rồi|hiểu rồi)\s*[!?.]*$',
          r'^(cảm ơn|thanks|thank you|cám ơn).*$',
          r'(chatbot|trợ lý|bot).*(là gì|tên gì|ai)'],
    'F': [r'(trường|đại học)\s+(bách khoa|ngoại thương|kinh tế quốc dân|sư phạm|y hà nội|fpt|phenikaa|thăng long)',
          r'điểm chuẩn.*(bách khoa|ngoại thương|kinh tế quốc dân|fpt)',
          r'(dự báo thời tiết|bóng đá|y tế|pháp luật|game|phim)',
          ]
}

def fast_route(query):
    query_lower = query.lower().strip()

    # Guard 0: F — trường khác / ngoài phạm vi (ưu tiên cao nhất)
    for pat in FAST_PATTERNS.get('F', []):
        if re.search(pat, query_lower):
            # Chỉ match F nếu KHÔNG nhắc đến HaUI
            if not re.search(r'(haui|công nghiệp hà nội)', query_lower):
                return 'F'

    # Guard 1: E — chào hỏi ngắn (chỉ match khi câu rất ngắn / rõ ràng)
    if len(query_lower.split()) <= 5:
        for pat in FAST_PATTERNS.get('E', []):
            if re.search(pat, query_lower):
                return 'E'

    # Guard 1b: A1 — ngành cụ thể + tổ hợp / chỉ tiêu (tránh LLM nhầm sang C)
    if re.search(r'ngành\s+.{2,120}\s+(thi|xét)\s+tổ\s+hợp', query_lower):
        return 'A1'
    if re.search(r'ngành\s+.{2,120}\s+tổ\s+hợp\s+(gì|nào)', query_lower):
        return 'A1'

    # Guard 2: A2 — nhóm ngành (match khi hỏi NHIỀU ngành, không có mã cụ thể + năm cụ thể)
    if re.search(r'(điểm chuẩn|dc)\s+(các ngành|nhóm ngành|tất cả)', query_lower):
        return 'A2'
    if re.search(r'(các|tất cả|danh sách|toàn bộ).*(ngành|điểm chuẩn)', query_lower):
        return 'A2'
    if re.search(r'ngành nào.*(điểm.*(cao nhất|thấp nhất))', query_lower):
        return 'A2'
    if re.search(r'ngành nào.*(thi|xét).*(toán|lý|hóa|anh|văn)', query_lower):
        return 'A2'

    # Guard 3: C — chỉ tiêu tổng, lịch, chính sách
    if re.search(r'chỉ tiêu\s+20(25|26)', query_lower):
        if not re.search(r'\d{7}', query_lower) and not re.search(r'ngành\s+\w+', query_lower):
            return 'C'
    if re.search(r'(tuyển|lấy) bao nhiêu.*(sinh viên|sv|chỉ tiêu)', query_lower):
        return 'C'

    # Guard 4: B1 — tính cụ thể (phải có SỐ LIỆU)
    if re.search(r'tính.*(học phí|hp).*\d+\s*(tc|tín chỉ)', query_lower):
        return 'B1'
    if re.search(r'(hsa|tsa)\s+\d+', query_lower):
        return 'B1'
    if re.search(r'tổng\s+\d+\s*điểm.*(kv|đt|tính)', query_lower):
        return 'B1'
    if re.search(r'\d+(\.\d+)?\s*(toán|lý|hóa|anh|văn)', query_lower):
        return 'B1'

    # Guard 5: C — cách tính học phí (không có số cụ thể → C, không phải B1)
    if re.search(r'cách tính học phí', query_lower):
        return 'C'

    # Standard pattern matching (thứ tự: B2 → C → D → A1)
    for intent in ['B2', 'C', 'D', 'A1']:
        for pattern in FAST_PATTERNS.get(intent, []):
            if re.search(pattern, query_lower):
                return intent
    return None

ROUTER_PROMPT = """Phân loại câu hỏi tuyển sinh đại học HaUI vào ĐÚNG 1 nhóm:

A1 - Tra cứu đơn: điểm chuẩn/học phí/chỉ tiêu/tổ hợp/việc làm/giới thiệu của 1 ngành hoặc 1 vấn đề cụ thể
A2 - Tra cứu nhiều: liệt kê NHIỀU ngành, xếp hạng, xu hướng nhiều năm, ngành nào cao/thấp nhất
B1 - Tính toán: tính điểm có ưu tiên kèm SỐ LIỆU CỤ THỂ, quy đổi HSA/TSA với điểm số, tính học phí N tín chỉ
B2 - Tư vấn ngành: gợi ý ngành theo điểm + tổ hợp + sở thích
C  - Thủ tục/chính sách: đăng ký, hồ sơ, nhập học, học bổng, KTX đăng ký, lịch tuyển sinh, phương thức xét tuyển, văn bằng, cách tính HP (không kèm số), điều kiện xét tuyển, ưu tiên đối tượng, chỉ tiêu tổng
D  - So sánh: ngành vs ngành, PT vs PT (phải có TỪ KHÓA so sánh rõ ràng)
E  - Chào hỏi / cảm ơn ngắn gọn (chỉ 1-2 từ, không hỏi thông tin)
F  - Ngoài phạm vi (trường khác, thời tiết, y tế...)

Ví dụ phân loại:
- "Điểm chuẩn CNTT 2025" → A1 (1 ngành cụ thể)
- "Điểm chuẩn tất cả ngành CNTT" → A2 (nhiều ngành)
- "HaUI là trường gì?" → A1 (tra cứu giới thiệu, KHÔNG phải E)
- "Ngành KTPM ra trường làm gì?" → A1 (tra cứu việc làm 1 ngành)
- "HaUI có bao nhiêu sinh viên?" → A1 (tra cứu quy mô)
- "Tỷ lệ có việc làm sau tốt nghiệp?" → A1 (tra cứu thống kê)
- "Cách tính học phí HaUI?" → C (hỏi cách, không có số)
- "Tính HP 3 TC lý thuyết K20" → B1 (tính với số liệu cụ thể)
- "Phương thức xét tuyển gồm gì?" → C
- "IELTS bao nhiêu đủ PT2?" → C (điều kiện)
- "Người khuyết tật cộng mấy điểm?" → C (chính sách ưu tiên)
- "PT3 và PT5 khác nhau thế nào?" → D
- "Ngành Logistics tổ hợp gì?" → A1 (tra cứu 1 ngành)
- "Chương trình liên kết 2+2?" → A1

Trả về ĐÚNG 1 trong: A1 A2 B1 B2 C D E F
Câu hỏi: {query}"""

def llm_route(query):
    result = call_llm(ROUTER_PROMPT.format(query=query), model=ROUTER_MODEL, max_tokens=5)
    for intent in ['A1', 'A2', 'B1', 'B2', 'C', 'D', 'E', 'F']:
        if intent in result:
            return intent
    return 'A1'

def route(query):
    intent = fast_route(query)
    if intent is None:
        intent = llm_route(query)
    if HAUI_DEBUG:
        print(f"[ROUTER] {query[:50]}... -> {intent}")
    return intent

# ══════════════════════════════════════════
#  QUERY REWRITE
# ══════════════════════════════════════════
REWRITE_PROMPT = """Chuẩn hóa câu hỏi tuyển sinh HaUI. Mở rộng viết tắt, thêm ngữ cảnh.
Quy tắc thêm ngữ cảnh năm (NĂM HIỆN TẠI: 2026):
- Hỏi về lịch tuyển sinh, chỉ tiêu → thêm "năm 2026"
- Hỏi về điểm chuẩn mà không có năm → thêm "điểm chuẩn gần nhất (2025)"
- Hỏi về học phí, KTX, học bổng → thêm "năm học 2025-2026"
- Không có tên trường → thêm "tại HaUI"
Trả về 1 câu query đã chuẩn hóa (không giải thích).
Query gốc: {query}"""

def rewrite_query(query, intent):
    if not QUERY_REWRITE_ENABLED:
        return query
    if RAG_LITE and intent in ('A1', 'C', 'D', 'B1') and len(query) < 72:
        return query
    result = call_llm(REWRITE_PROMPT.format(query=query), max_tokens=200)
    return result if result else query

def expand_query(query, intent):
    if intent not in ['A2', 'B2']:
        return [query]
    prompt = f"""Tạo 2 câu hỏi liên quan bổ sung cho query tuyển sinh HaUI.
Mỗi câu trên 1 dòng. Không đánh số.
Query gốc: {query}"""
    result = call_llm(prompt, max_tokens=200)
    variants = [q.strip() for q in result.strip().split('\n') if q.strip()]
    return [query] + variants[:2]

# ══════════════════════════════════════════
#  HyDE
# ══════════════════════════════════════════
def generate_hyde(query, intent):
    if not HYDE_ENABLED:
        return None
    if RAG_LITE and HYDE_INTENTS is not None and intent not in HYDE_INTENTS:
        return None
    prompt = f"""Viết đoạn văn ngắn (3-5 câu) mô tả thông tin tuyển sinh HaUI trả lời cho câu hỏi:
Câu hỏi: {query}"""
    return call_llm(prompt, max_tokens=300)

# ══════════════════════════════════════════
#  PRE-FILTER
# ══════════════════════════════════════════
def build_filter(query, intent, entities):
    filters = {}
    query_lower = query.lower()

    # === A1: tra cứu đơn — filter theo ngành + loại dữ liệu ===
    if intent == 'A1':
        if entities.get('ma_nganh'):
            filters['ma_nganh'] = entities['ma_nganh']
        if entities.get('nhom_nganh') and not entities.get('ma_nganh') and not entities.get('ten_nganh'):
            filters['nhom_nganh'] = entities['nhom_nganh']
        # Filter theo loại dữ liệu
        if any(kw in query_lower for kw in ['điểm chuẩn', 'dc ', 'đc ']):
            filters['loai__in'] = ['diem_chuan']
        elif any(kw in query_lower for kw in ['tổ hợp', 'chỉ tiêu', 'xét tuyển tổ hợp']):
            filters['loai__in'] = ['chi_tieu_to_hop', 'mo_ta_nganh']
        elif any(kw in query_lower for kw in ['việc làm', 'ra trường', 'làm gì', 'cơ hội',
                                               'tỷ lệ', 'tỉ lệ', 'có việc']):
            filters['loai__in'] = ['mo_ta_nganh', 'gioi_thieu']
        elif any(kw in query_lower for kw in ['ký túc xá', 'ktx', 'phòng ở', 'phòng ktx']):
            filters['loai__in'] = ['ky_tuc_xa']
        elif any(kw in query_lower for kw in ['học phí', 'mức thu']):
            filters['loai__in'] = ['hoc_phi']
        elif any(kw in query_lower for kw in ['giới thiệu', 'là trường gì', 'quy mô', 'bao nhiêu sinh viên',
                                               'đang học', 'số lượng sinh viên', 'tổng số']):
            filters['loai__in'] = ['gioi_thieu']
        elif any(kw in query_lower for kw in ['liên kết', '2+2', 'song bằng', 'chương trình']):
            filters['loai__in'] = ['mo_ta_nganh', 'chinh_sach']
        # Nếu không match loại nào → search rộng (không filter loai)

    # === A2: tra cứu nhiều ===
    elif intent == 'A2':
        if entities.get('nhom_nganh'):
            filters['nhom_nganh'] = entities['nhom_nganh']
        if any(kw in query_lower for kw in ['điểm chuẩn', 'dc ']):
            filters['loai__in'] = ['diem_chuan']
        elif any(kw in query_lower for kw in ['tổ hợp', 'chỉ tiêu']):
            filters['loai__in'] = ['chi_tieu_to_hop']

    # === B1: tính toán ===
    elif intent == 'B1':
        if any(kw in query_lower for kw in ['học phí', 'tín chỉ', 'tc']):
            filters['loai__in'] = ['hoc_phi']
        elif any(kw in query_lower for kw in ['quy đổi', 'hsa', 'tsa', 'đgnl', 'đgtd']):
            filters['loai__in'] = ['diem_quy_doi']
        elif any(kw in query_lower for kw in ['pt2', 'phương thức 2', 'học bạ', 'hsg', 'chứng chỉ']):
            filters['loai__in'] = ['diem_quy_doi', 'huong_dan', 'diem_uu_tien']
        else:
            filters['loai__in'] = ['diem_chuan', 'diem_uu_tien', 'diem_quy_doi']

    # === C: thủ tục / chính sách ===
    elif intent == 'C':
        if any(kw in query_lower for kw in ['học phí', 'mức thu', 'đơn giá', 'cách tính học phí']):
            filters['loai__in'] = ['hoc_phi', 'huong_dan', 'chinh_sach']
        elif any(kw in query_lower for kw in ['ký túc xá', 'ktx', 'phòng ở']):
            filters['loai__in'] = ['ky_tuc_xa']
        elif any(kw in query_lower for kw in ['học bổng', 'hỗ trợ tài chính', 'miễn giảm']):
            filters['loai__in'] = ['hoc_bong']
        elif any(kw in query_lower for kw in ['lịch', 'thời gian', 'khi nào',
                                               'chỉ tiêu 2026', 'tuyển bao nhiêu']):
            filters['loai__in'] = ['lich_tuyen_sinh', 'chi_tieu_tong', 'huong_dan']
        elif any(kw in query_lower for kw in ['phương thức', 'pt1', 'pt2', 'pt3', 'pt4', 'pt5',
                                               'điều kiện', 'ielts', 'chứng chỉ']):
            filters['loai__in'] = ['huong_dan', 'faq', 'chinh_sach']
        elif any(kw in query_lower for kw in ['ưu tiên', 'đối tượng', 'khuyết tật', 'thương binh',
                                               'liệt sĩ', 'ut1', 'ut2']):
            filters['loai__in'] = ['diem_uu_tien', 'chinh_sach']
        elif any(kw in query_lower for kw in ['nhập học', 'hồ sơ', 'đăng ký', 'bản cứng', 'thẻ sinh viên',
                                               'mở thẻ', 'vietinbank']):
            filters['loai__in'] = ['huong_dan', 'faq']
        elif any(kw in query_lower for kw in ['văn bằng', 'bằng cấp', 'bằng cử nhân', 'bằng kỹ sư',
                                               'tốt nghiệp cấp']):
            filters['loai__in'] = ['chinh_sach']
        elif any(kw in query_lower for kw in ['thí sinh tự do', 'tốt nghiệp trước']):
            filters['loai__in'] = ['huong_dan', 'faq', 'chinh_sach']
        else:
            filters['loai__in'] = ['huong_dan', 'faq', 'chinh_sach', 'hoc_phi',
                                   'ky_tuc_xa', 'hoc_bong', 'lich_tuyen_sinh',
                                   'chi_tieu_tong', 'diem_uu_tien']

    # === D: so sánh ===
    elif intent == 'D':
        # Không filter chặt — cần retrieve nhiều loại chunk cho cả 2 entity
        pass

    return filters

def apply_chroma_filter(filters):
    """Build ChromaDB where clause. Uses $and when multiple conditions exist."""
    conditions = []
    if 'ma_nganh' in filters:
        conditions.append({'ma_nganh': filters['ma_nganh']})
    if 'nhom_nganh' in filters:
        conditions.append({'nhom_nganh': filters['nhom_nganh']})
    if 'loai__in' in filters:
        conditions.append({'loai': {'$in': filters['loai__in']}})
    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {'$and': conditions}

def check_filter(chunk, filters):
    meta = chunk.get('metadata', {})
    if 'ma_nganh' in filters and meta.get('ma_nganh') != filters['ma_nganh']:
        return False
    if 'nhom_nganh' in filters and meta.get('nhom_nganh') != filters['nhom_nganh']:
        return False
    if 'loai__in' in filters:
        loai = meta.get('loai', '')
        if loai not in filters['loai__in']:
            return False
    return True

# ══════════════════════════════════════════
#  HYBRID SEARCH + RRF
# ══════════════════════════════════════════
TOP_K_CONFIG = {
    'A1': {'vector': 5, 'bm25': 5, 'rerank_top': 3},
    'A2': {'vector': 15, 'bm25': 10, 'rerank_top': 8},
    'B1': {'vector': 8, 'bm25': 8, 'rerank_top': 5},
    'B2': {'vector': 15, 'bm25': 12, 'rerank_top': 8},
    'C': {'vector': 8, 'bm25': 6, 'rerank_top': 5},
    'D': {'vector': 10, 'bm25': 8, 'rerank_top': 6},
    'E': {'vector': 0, 'bm25': 0, 'rerank_top': 0},
    'F': {'vector': 0, 'bm25': 0, 'rerank_top': 0},
}

def hybrid_search(query_vec, query_text, filters, top_k=10):
    rrf_scores = {}
    k_const = 60
    id_to_chunk = {}

    if _collection:
        chroma_filter = apply_chroma_filter(filters)
        try:
            n = min(top_k * 2, _collection.count())
            if n > 0:
                results = _collection.query(
                    query_embeddings=[query_vec], n_results=n,
                    where=chroma_filter if chroma_filter else None,
                    include=['documents', 'metadatas']
                )
                if results and results['ids'] and results['ids'][0]:
                    for rank, (doc_id, doc, meta) in enumerate(zip(
                        results['ids'][0], results['documents'][0], results['metadatas'][0]
                    )):
                        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k_const + rank + 1)
                        id_to_chunk[doc_id] = {'id': doc_id, 'text': doc, 'metadata': meta}
        except Exception as e:
            if HAUI_DEBUG:
                print(f"[VECTOR SEARCH] {e}")

    if _bm25 and _chunks:
        tokens = word_tokenize(query_text)
        bm25_scores = _bm25.get_scores(tokens)
        bm25_top = sorted([(i, s) for i, s in enumerate(bm25_scores) if s > 0], key=lambda x: -x[1])[:top_k * 2]
        bm25_top = [(i, s) for i, s in bm25_top if check_filter(_chunks[i], filters)]
        for rank, (doc_idx, _) in enumerate(bm25_top):
            doc_id = _chunks[doc_idx]['id']
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k_const + rank + 1)
            if doc_id not in id_to_chunk:
                id_to_chunk[doc_id] = _chunks[doc_idx]

    merged = sorted(rrf_scores.items(), key=lambda x: -x[1])[:20]
    return [id_to_chunk[doc_id] for doc_id, _ in merged if doc_id in id_to_chunk]

# ══════════════════════════════════════════
#  RERANKER
# ══════════════════════════════════════════
def rerank(query, candidates, top_k=5):
    if not candidates:
        return []
    if USE_REMOTE_RERANKER:
        try:
            response = requests.post(
                f"{RERANKER_URL}/rerank",
                json={'query': query, 'texts': [c['text'] for c in candidates]},
                timeout=10
            )
            if response.status_code == 200:
                # Server trả về list: [{"index": 0, "score": 0.9}, ...]
                results = response.json()
                if isinstance(results, list) and results:
                    ranked = sorted(results, key=lambda x: x['score'], reverse=True)
                    return [candidates[r['index']] for r in ranked[:top_k]]
        except Exception as e:
            if HAUI_DEBUG:
                print(f"[RERANKER] Remote failed: {e}")
    return candidates[:top_k]

# ══════════════════════════════════════════
#  SELF-REFLECT
# ══════════════════════════════════════════
SELF_REFLECT_PROMPT = """Kiểm tra: các đoạn văn sau có đủ thông tin để trả lời câu hỏi không?
Câu hỏi: {query}
Đoạn văn: {context_preview}
Trả lời ĐÚNG 1 trong: SUFFICIENT PARTIAL MISSING"""

def self_reflect(query, chunks_list, intent):
    if not SELF_REFLECT_ENABLED or not chunks_list:
        return ('ok' if chunks_list else 'empty'), chunks_list
    if RAG_LITE and SELF_REFLECT_INTENTS is not None and intent not in SELF_REFLECT_INTENTS:
        return 'ok', chunks_list
    context_preview = '\n---\n'.join([c['text'][:300] for c in chunks_list[:3]])
    result = call_llm(SELF_REFLECT_PROMPT.format(query=query, context_preview=context_preview), max_tokens=10)
    if 'SUFFICIENT' in result:
        return 'ok', chunks_list
    elif 'PARTIAL' in result:
        return 'partial', chunks_list
    else:
        # FIX: GIỮ LẠI chunks — để LLM cố trả lời từ context hiện có
        # Chỉ log warning, không xóa docs
        if HAUI_DEBUG:
            print(f"[SELF-REFLECT] MISSING but keeping {len(chunks_list)} chunks for LLM")
        return 'missing', chunks_list

# ══════════════════════════════════════════
#  GENERATE
# ══════════════════════════════════════════
from src.rag.prompts import SYSTEM_PROMPT_TEMPLATE

CONTEXT_MISSING_MESSAGE = (
    "Em chưa tìm được thông tin chính xác về vấn đề này. "
    "Anh/chị vui lòng liên hệ Văn phòng Tuyển sinh HaUI: "
    "☎ 024.3765.5121 / 0834.560.255 hoặc xem tại tuyensinh.haui.edu.vn"
)

FALLBACK_MESSAGE = (
    "Câu hỏi này nằm ngoài phạm vi tư vấn tuyển sinh HaUI của em. "
    "Em chỉ có thể hỗ trợ thông tin về tuyển sinh tại Đại học Công nghiệp Hà Nội. "
    "Anh/chị có câu hỏi nào khác về HaUI không ạ?"
)

def generate_smalltalk(query):
    q = query.lower()
    if any(w in q for w in ['chào', 'hello', 'hi', 'xin chào']):
        return "Xin chào! 👋 Em là Trợ lý Tuyển sinh HaUI. Em có thể giúp anh/chị tra cứu điểm chuẩn, tính điểm xét tuyển, tìm hiểu ngành học, thủ tục nhập học và nhiều thông tin khác. Anh/chị muốn hỏi gì ạ?"
    elif any(w in q for w in ['cảm ơn', 'thanks', 'thank']):
        return "Không có gì ạ! 😊 Nếu anh/chị cần thêm thông tin về tuyển sinh HaUI, cứ hỏi em nhé!"
    return "Xin chào! Em là Trợ lý Tuyển sinh HaUI. Em có thể giúp anh/chị về điểm chuẩn, ngành học, thủ tục tuyển sinh và nhiều thông tin khác. Hãy hỏi em nhé! 📚"

VI_RULE = (
    "\n\n[QUY TẮC BẮT BUỘC — NGÔN NGỮ]\n"
    "- Trả lời **100% tiếng Việt** (trừ mã tổ hợp A01, PT3, mã ngành, tên riêng quốc tế trong tài liệu).\n"
    "- **Không** dùng tiếng Trung (chữ Hán), tiếng Nhật hay tiếng Hàn trong câu trả lời.\n"
    "- **A01** = Toán – Vật lí – Tiếng Anh; **A00** = Toán – Lý – Hóa (không nhầm lẫn).\n"
)

def generate_response(query, context, intent):
    system = SYSTEM_PROMPT_TEMPLATE.replace('{context}', context).replace('{intent}', intent)
    prompt = f"{system}{VI_RULE}\n\nCâu hỏi của người dùng: {query}"
    mt = 1536 if intent in ('A1', 'E', 'F', 'C') else 2048
    if intent == 'A1':
        mt = 1024
    raw = call_llm(prompt, max_tokens=mt, temperature=0.02)
    return sanitize_answer_vietnamese(raw)


def sanitize_answer_vietnamese(text: str) -> str:
    """Bỏ đoạn chỉ chứa chữ CJK (trường hợp model lệch ngôn ngữ)."""
    if not text or not re.search(r'[\u4e00-\u9fff]', text):
        return text
    lines = []
    for line in text.splitlines():
        if re.fullmatch(r'[\s\u4e00-\u9fff，。：；？！、（）【】""''…]+', line or ''):
            continue
        line = re.sub(r'[\u4e00-\u9fff]{2,}', ' ', line)
        lines.append(line)
    out = '\n'.join(lines).strip()
    return out if out else text

# ══════════════════════════════════════════
#  MAIN PIPELINE
# ══════════════════════════════════════════
def handle_query(user_query):
    """Full RAG pipeline: route → retrieve → generate."""
    start = time.time()

    # 1. Route
    intent = route(user_query)

    # 2. Short-circuit
    if intent == 'E':
        return {'answer': generate_smalltalk(user_query), 'intent': intent, 'time': time.time() - start}
    if intent == 'F':
        return {'answer': FALLBACK_MESSAGE, 'intent': intent, 'time': time.time() - start}

    # 2b. Tính toán / quy đổi chính xác từ JSON (bỏ qua LLM nếu parse được)
    det = try_deterministic_b1_answer(user_query)
    if det:
        return {
            'answer': det,
            'intent': intent,
            'entities': extract_entities(user_query),
            'context': '[deterministic JSON / công thức HaUI]',
            'num_chunks': 0,
            'time': round(time.time() - start, 2),
        }

    det_kb = try_deterministic_kb_answer(user_query)
    if det_kb:
        return {
            'answer': det_kb,
            'intent': intent,
            'entities': extract_entities(user_query),
            'context': '[deterministic KB: chi_tieu / PT2 / quy_mo]',
            'num_chunks': 0,
            'time': round(time.time() - start, 2),
        }

    # 3. Entity extraction
    entities = extract_entities(user_query)

    # 4. Query rewrite
    clean_query = rewrite_query(user_query, intent)
    if HAUI_DEBUG:
        print(f"[REWRITE] {user_query} -> {clean_query}")

    # 5. Multi-query expansion
    queries = expand_query(clean_query, intent)

    # 6. HyDE
    hyde_doc = generate_hyde(clean_query, intent)

    # 7. Embedding
    query_vec = embed_query(clean_query)
    if hyde_doc:
        hyde_vec = embed_query(hyde_doc)
        final_vec = [0.7 * q + 0.3 * h for q, h in zip(query_vec, hyde_vec)]
    else:
        final_vec = query_vec

    # 8. Build pre-filter
    filters = build_filter(clean_query, intent, entities)

    # 9. Hybrid search
    cfg = TOP_K_CONFIG.get(intent, TOP_K_CONFIG['A1'])
    candidates = hybrid_search(final_vec, clean_query, filters, top_k=max(cfg['vector'], cfg['bm25']))

    # 9b. Fallback: nếu filter chặt quá → mở rộng search không filter
    if len(candidates) < 2 and filters:
        if HAUI_DEBUG:
            print(f"[SEARCH] Only {len(candidates)} results with filter, retrying without filter")
        fallback_candidates = hybrid_search(final_vec, clean_query, {}, top_k=max(cfg['vector'], cfg['bm25']))
        seen_ids = {c['id'] for c in candidates}
        for c in fallback_candidates:
            if c['id'] not in seen_ids:
                candidates.append(c)
                seen_ids.add(c['id'])

    # 9c. Intent D: multi-entity search — search cho từng entity ngành
    if intent == 'D' and entities.get('ten_nganh'):
        # Trích 2 ngành từ query cho so sánh
        d_entities = _extract_comparison_entities(user_query)
        for ent_name in d_entities:
            ent_query = f"Thông tin ngành {ent_name} HaUI điểm chuẩn tổ hợp chỉ tiêu việc làm"
            ent_vec = embed_query(ent_query)
            ent_results = hybrid_search(ent_vec, ent_query, {}, top_k=5)
            seen_ids = {c['id'] for c in candidates}
            for r in ent_results:
                if r['id'] not in seen_ids:
                    candidates.append(r)
                    seen_ids.add(r['id'])

    # For multi-query, merge results
    if len(queries) > 1:
        for extra_q in queries[1:]:
            extra_vec = embed_query(extra_q)
            extra_results = hybrid_search(extra_vec, extra_q, filters, top_k=5)
            seen_ids = {c['id'] for c in candidates}
            for r in extra_results:
                if r['id'] not in seen_ids:
                    candidates.append(r)
                    seen_ids.add(r['id'])

    # 10. Rerank
    top_docs = rerank(clean_query, candidates, top_k=cfg['rerank_top'])

    # 11. Self-reflect
    status, docs = self_reflect(clean_query, top_docs, intent)

    # FIX: Chỉ fallback khi thực sự KHÔNG CÓ chunk nào
    if not docs:
        return {
            'answer': CONTEXT_MISSING_MESSAGE,
            'intent': intent,
            'time': time.time() - start,
            'num_chunks': 0
        }

    # 12. Build context
    context = '\n\n---\n\n'.join([d['text'] for d in docs])
    extra = enrich_context(user_query, intent, entities)
    if extra:
        context = extra + '\n\n---\n\n' + context

    # 12b. Input validation for B1 — cảnh báo điểm > 30
    if intent == 'B1':
        nums = re.findall(r'tổng\s+(\d+(?:\.\d+)?)\s*điểm', user_query.lower())
        if not nums:
            nums = re.findall(r'(\d+(?:\.\d+)?)\s*điểm\s*3\s*môn', user_query.lower())
        for n in nums:
            try:
                if float(n) > 30:
                    return {
                        'answer': f"⚠️ Tổng điểm 3 môn là {n} điểm, vượt quá thang điểm tối đa (30 điểm). "
                                  f"Anh/chị vui lòng kiểm tra lại điểm đầu vào nhé!",
                        'intent': intent,
                        'entities': entities,
                        'context': context,
                        'num_chunks': len(docs),
                        'time': round(time.time() - start, 2)
                    }
            except ValueError:
                pass

    # 13. Generate
    answer = generate_response(user_query, context, intent)

    result = {
        'answer': answer,
        'intent': intent,
        'entities': entities,
        'context': context,  # Expose context for evaluation
        'num_chunks': len(docs),
        'time': round(time.time() - start, 2)
    }

    if HAUI_DEBUG:
        print(f"[PIPELINE] Intent={intent}, Chunks={len(docs)}, Time={result['time']}s")

    return result


def _extract_comparison_entities(query):
    """Trích 2 entity ngành/phương thức từ câu hỏi so sánh."""
    entities = []
    query_lower = query.lower()
    # Tìm tên ngành
    for alias, full_name in NGANH_ALIASES.items():
        if alias in query_lower and full_name not in entities:
            entities.append(full_name)
    # Tìm PT
    pts = re.findall(r'PT\d', query, re.IGNORECASE)
    for pt in pts:
        entities.append(f"Phương thức {pt.upper()} HaUI")
    return entities[:4]  # Tối đa 4 entity