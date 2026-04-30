# KHUNG BÁO CÁO ĐỒ ÁN TỐT NGHIỆP

> **Đề tài:** Xây dựng Chatbot Tư vấn Tuyển sinh Trường Đại học Công nghiệp Hà Nội  
> ứng dụng kiến trúc RAG (Retrieval-Augmented Generation)  
> **Sinh viên:** [Họ tên] — MSV: [Mã số]  
> **GVHD:** [Họ tên giảng viên]  
> **Khoa:** Công nghệ thông tin — Trường Đại học Công nghiệp Hà Nội  
> **Năm:** 2026

---
## LỜI MỞ ĐẦU

## MỤC LỤC (tự sinh)

## DANH MỤC BẢNG BIỂU

## DANH MỤC HÌNH VẼ

## DANH MỤC TỪ VIẾT TẮT

| Viết tắt | Diễn giải |
|----------|-----------|
| RAG | Retrieval-Augmented Generation |
| LLM | Large Language Model |
| BM25 | Best Match 25 — thuật toán xếp hạng văn bản |
| RRF | Reciprocal Rank Fusion |
| HyDE | Hypothetical Document Embedding |
| HNSW | Hierarchical Navigable Small World (chỉ mục vector) |
| HaUI | Hanoi University of Industry |

---


## Mở đầu
### 1. Lý do chọn đề tài
- Lượng thí sinh truy vấn thông tin tuyển sinh hàng năm lớn, gây áp lực lên bộ phận tư vấn.
- Chatbot truyền thống (cây kịch bản cố định) không xử lý được câu hỏi mở và tính toán.
- LLM giải quyết ngôn ngữ tự nhiên nhưng gặp vấn đề hallucination — RAG là giải pháp kết hợp.
- Dữ liệu tuyển sinh HaUI có cấu trúc rõ, phù hợp xây dựng RAG miền hẹp.

### 2. Mục tiêu đồ án
- Xây dựng Chatbot RAG nâng cao phục vụ tư vấn tuyển sinh HaUI.
- Đảm bảo chính xác tuyệt đối cho các phép tính điểm xét tuyển (Deterministic Engine).
- Đánh giá chất lượng RAG theo từng component để định hướng cải tiến.

### 3. Đối tượng và phạm vi
- **Đối tượng:** Hệ thống hỏi-đáp miền hẹp (domain-specific QA) lĩnh vực tuyển sinh.
- **Phạm vi:** Dữ liệu tuyển sinh HaUI 2023–2026 (điểm chuẩn, chỉ tiêu, tổ hợp, chính sách, thủ tục).

### 4. Phương pháp nghiên cứu
- Nghiên cứu lý thuyết: LLM, RAG, Hybrid Search.
- Thực nghiệm: xây dựng hệ thống, đánh giá trên bộ test tự xây dựng.

### 5. Bố cục đồ án
- Tóm tắt 4 chương.

---

## CHƯƠNG 1. CƠ SỞ LÝ THUYẾT

> **Nguyên tắc:** Chỉ trình bày lý thuyết trực tiếp phục vụ các quyết định kỹ thuật ở Chương 2–3. Không diễn giải kiến thức phổ thông (Flask, JWT, CSS…).

### 1.1. Bài toán Chatbot miền hẹp

- Phân biệt chatbot rule-based vs. chatbot dựa trên LLM.
- Đặc thù domain tuyển sinh: dữ liệu có cấu trúc (JSON), thay đổi theo năm, yêu cầu tính toán chính xác.
- Các nghiên cứu liên quan (chatbot tuyển sinh trong và ngoài nước), phân tích hạn chế.

### 1.2. Mô hình ngôn ngữ lớn (LLM)

#### 1.2.1. Cơ chế sinh văn bản
- Kiến trúc Transformer (Self-Attention) — trình bày ngắn gọn, tập trung vào khả năng suy luận ngôn ngữ.

#### 1.2.2. Vấn đề Hallucination và Knowledge Cutoff
- Đây là **lý do cốt lõi** dẫn đến kiến trúc RAG: LLM bịa số liệu, dữ liệu không cập nhật.
- → Cần cơ chế cung cấp context thực tế cho LLM trước khi sinh.

#### 1.2.3. Mô hình Qwen2.5 và Ollama
- Qwen2.5 (14B): lựa chọn cho hệ thống — lý do (hỗ trợ tiếng Việt, kích thước phù hợp on-premise).
- Ollama: framework chạy LLM cục bộ, lợi ích triển khai không phụ thuộc cloud.

### 1.3. Kiến trúc RAG

#### 1.3.1. Nguyên lý RAG cơ bản
- Quy trình: Query → Retrieve → Augment Context → Generate.
- So sánh RAG vs. Fine-tuning: lý do chọn RAG (dữ liệu thay đổi hàng năm, không cần re-train).

#### 1.3.2. Các kỹ thuật RAG nâng cao
- **Query Rewriting:** chuẩn hóa câu hỏi, bổ sung ngữ cảnh thiếu (ví dụ: thêm năm, mở rộng viết tắt).
- **HyDE:** sinh tài liệu giả định → embedding → tìm kiếm chính xác hơn.
- **Self-Reflection:** đánh giá context trước khi sinh, phân loại SUFFICIENT / PARTIAL / MISSING.
- **Deterministic Fallback:** bỏ qua LLM khi truy vấn có thể giải bằng logic cứng (tính điểm, tra bảng).

### 1.4. Biểu diễn văn bản và tìm kiếm hỗn hợp

#### 1.4.1. Sentence Embedding
- Ánh xạ văn bản → vector trong không gian ngữ nghĩa.
- BGE-M3: embedding đa ngôn ngữ 1024 chiều, hỗ trợ tiếng Việt.

#### 1.4.2. Vector Search và BM25
- **Vector Search:** tìm kiếm ngữ nghĩa (Cosine Similarity) qua ChromaDB (HNSW index).
- **BM25Okapi:** tìm kiếm từ khóa — bắt mạnh entity chính xác (mã ngành, tổ hợp) mà vector search có thể bỏ sót.
- **Tại sao cần cả hai:** vector search mạnh ngữ nghĩa nhưng yếu entity; BM25 ngược lại.

#### 1.4.3. Reciprocal Rank Fusion (RRF)
- Công thức: `score(d) = Σ 1/(k + rank_i(d))`.
- Ưu điểm: không cần chuẩn hóa score giữa hai phương pháp khác thang.

### 1.5. Tổng kết chương
- Liên hệ: mỗi khái niệm lý thuyết trên sẽ áp dụng vào component nào (bảng ánh xạ ngắn).

---

## CHƯƠNG 2. PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG

> **Nguyên tắc:** Chương này trả lời "THIẾT KẾ CÁI GÌ và TẠI SAO" — chỉ sơ đồ, bảng, flowchart. Không mô tả code, không trích mã nguồn. Code nằm ở Chương 3.

### 2.1. Phân tích yêu cầu

#### 2.1.1. Khảo sát nghiệp vụ
- Quy trình tư vấn tuyển sinh hiện tại (thủ công).
- Thống kê dạng câu hỏi thường gặp → dẫn đến bảng phân loại Intent.

#### 2.1.2. Yêu cầu chức năng

| STT | Chức năng | Mô tả |
|-----|-----------|-------|
| F1 | Tra cứu thông tin | Điểm chuẩn, tổ hợp, chỉ tiêu, học phí, KTX theo ngành/năm |
| F2 | Tính toán điểm | PT2 (HSG + chứng chỉ), PT3 (thi THPT + ưu tiên), quy đổi HSA/TSA, tính học phí |
| F3 | Gợi ý ngành | Dựa trên điểm + tổ hợp + sở thích |
| F4 | Hướng dẫn thủ tục | Đăng ký, nhập học, hồ sơ, deadline |
| F5 | So sánh | Ngành vs ngành, phương thức vs phương thức |
| F6 | Quản trị | Upload/xóa dữ liệu, re-index, analytics |
| F7 | Đa kênh | Web, Telegram, Facebook Messenger |
| F8 | Phản hồi | Thumbs-up/down trên mỗi câu trả lời |

#### 2.1.3. Yêu cầu phi chức năng
- Thời gian phản hồi ≤ 5s (RAG_LITE ≤ 3s).
- Factual accuracy ≥ 80%.
- Hỗ trợ hoàn toàn tiếng Việt.
- Triển khai on-premise (không cần GPU cloud).

### 2.2. Thiết kế kiến trúc tổng thể

#### 2.2.1. Sơ đồ kiến trúc hệ thống
*(Vẽ sơ đồ 4 tầng)*

```
┌──────────────────────────────────────────┐
│  Tầng giao diện: Web UI │ Telegram │ FB  │
└─────────────────┬────────────────────────┘
                  │
┌─────────────────▼────────────────────────┐
│  Tầng API: Flask Server                  │
│  (Chat, Admin, Feedback, Webhook)        │
└─────────────────┬────────────────────────┘
                  │
┌─────────────────▼────────────────────────┐
│  Tầng xử lý: RAG Pipeline               │
│  Router → Retrieval → Generation         │
│  + Deterministic Engine (B1 bypass)      │
└──────┬──────────────────┬────────────────┘
       │                  │
┌──────▼───────┐  ┌───────▼───────┐
│ ChromaDB     │  │ BM25 Index    │
│ (Vector DB)  │  │ (Keyword)     │
└──────┬───────┘  └───────┬───────┘
       │                  │
┌──────▼──────────────────▼────────┐
│  Tầng dữ liệu: JSON + Markdown  │
│  (data/processed/)               │
└──────────────────────────────────┘
```

#### 2.2.2. Cấu trúc thư mục
- Sơ đồ cây thư mục thực tế, giải thích nguyên tắc phân tách module.

### 2.3. Thiết kế phân loại Intent

#### 2.3.1. Bảng 8 nhóm Intent

| Intent | Mô tả | Chiến lược xử lý |
|--------|-------|-------------------|
| A1 | Tra cứu 1 ngành / 1 vấn đề | Search hẹp + filter ngành |
| A2 | Tra cứu nhiều ngành / xếp hạng | Multi-query + top_k lớn |
| B1 | Tính toán có số liệu | Deterministic trước, LLM sau |
| B2 | Gợi ý ngành theo điểm | Tính ĐXT → lọc → phân nhóm |
| C | Thủ tục / chính sách | Retrieve hướng dẫn |
| D | So sánh ngành hoặc phương thức | Multi-entity search |
| E | Chào hỏi | Short-circuit, không RAG |
| F | Ngoài phạm vi | Từ chối lịch sự |

#### 2.3.2. Router hai tầng — Flowchart
*(Vẽ sơ đồ luồng)*
- Tầng 1: Regex guard theo thứ tự ưu tiên F → E → A1 → A2 → C → B1 → B2 → D.
- Tầng 2: Gọi LLM phân loại khi regex không khớp.
- Lý do thiết kế thứ tự guard: tránh nhầm lẫn giữa intent giao nhau (ví dụ: B1 vs C đều có "học phí").

### 2.4. Thiết kế luồng RAG Pipeline

#### 2.4.1. Sơ đồ luồng xử lý (Flowchart)
*(Vẽ sơ đồ từ bước 1 đến 13 dựa trên `handle_query()` thực tế)*

```
Query đầu vào
  │
  ├─ (1) Router ──→ E/F? ──→ Trả lời ngay (short-circuit)
  │                  │
  │                  ▼
  ├─ (2) try_deterministic_b1 ──→ Parse được? ──→ Trả lời tính toán
  │                                    │
  │                                    ▼
  ├─ (3) try_deterministic_kb ──→ Match KB? ──→ Trả lời tra cứu
  │                                   │
  │                                   ▼
  ├─ (4) Entity Extraction (regex 6 loại)
  ├─ (5) Query Rewrite (LLM chuẩn hóa)
  ├─ (6) Multi-query Expansion [chỉ A2, B2]
  ├─ (7) HyDE [chỉ A2, B2 khi RAG_LITE bật]
  ├─ (8) Embedding (blend 0.7 gốc + 0.3 HyDE)
  ├─ (9) Build Pre-filter (theo intent + entity)
  ├─(10) Hybrid Search (ChromaDB + BM25 + RRF)
  │       └─ Fallback: bỏ filter nếu kết quả < 2
  ├─(11) Rerank (remote hoặc cắt top_k)
  ├─(12) Self-Reflect (SUFFICIENT/PARTIAL/MISSING)
  ├─(13) Enrich Context (inject snippet JSON chính thức)
  └─(14) LLM Generate → Sanitize Vietnamese → Trả lời
```

#### 2.4.2. Thiết kế Pre-filter theo Intent
- Bảng: mỗi Intent lọc theo metadata nào (`loai`, `ma_nganh`, `nhom_nganh`).
- Lý do: giảm nhiễu triệt để, tránh retrieve sai chủ đề.

#### 2.4.3. Thiết kế cấu hình Top_K theo Intent
- Bảng `TOP_K_CONFIG` thực tế (vector, bm25, rerank_top cho mỗi intent).
- Lý do: A1 cần ít chunk chính xác, A2/B2 cần nhiều chunk đa dạng.

### 2.5. Thiết kế Deterministic Engine

- **Vấn đề:** tính điểm xét tuyển yêu cầu chính xác 100%, LLM có thể sai số.
- **Giải pháp:** tách riêng module tính toán bằng code Python, bypass LLM khi parse được input.
- **Sơ đồ quyết định:** Query → regex parse → thành công → trả lời trực tiếp | thất bại → chuyển sang RAG.
- **Các nghiệp vụ tính toán:**

| Nghiệp vụ | Công thức / Quy tắc |
|------------|---------------------|
| PT3 (thi THPT) | Σ 3 môn + ưu tiên (giảm dần khi Σ ≥ 22.5) |
| PT2 (HSG/chứng chỉ) | ĐKQHT × 2 + ĐQĐCC |
| Quy đổi HSA/TSA/KQHB | Tra bảng JSON chính xác, không nội suy |
| Tính học phí | HP = số_TC × hệ_số_nhóm × đơn_giá |

### 2.6. Thiết kế dữ liệu

#### 2.6.1. Nguồn dữ liệu và chiến lược Chunking

| Nguồn | Định dạng | Chiến lược Chunking | Metadata chính |
|-------|-----------|---------------------|----------------|
| Điểm chuẩn 2023–2025 | JSON (mảng record) | Nhóm theo mã ngành, gộp nhiều năm | `ma_nganh`, `nhom_nganh`, `nam_list` |
| Chỉ tiêu + tổ hợp 2025 | JSON | Mỗi ngành 1 chunk | `to_hop`, `chi_tieu` |
| Bảng quy đổi HSA/TSA | JSON | Mỗi bảng 1 chunk (full bảng) | `ki_thi`, `loai_con` |
| Học phí | JSON | Nhóm theo chương trình | `nhom`, `nam_hoc` |
| Mô tả ngành | Markdown (50+ file) | Tách section: tuyển sinh, đầu ra, việc làm | `ma_nganh`, `loai_con` |
| FAQ | Markdown | Mỗi cặp Q&A 1 chunk | `loai: faq` |
| Học bổng | Markdown | Chunk 2 cấp (nhóm + chi tiết) | `nhom`, `section` |
| Chính sách/hướng dẫn | Markdown | Chunk theo heading `##` | `loai`, `section` |

- Lý do metadata phong phú: phục vụ Pre-filter, giảm nhiễu khi tìm kiếm.

#### 2.6.2. Cơ sở dữ liệu
- **ChromaDB:** collection `haui_chunks`, cosine similarity, HNSW index.
- **BM25 Index:** tokenizer tiếng Việt (Underthesea), serialized Pickle.
- **Analytics:** JSON log (auto-prune 7 ngày) + feedback log.

### 2.7. Thiết kế giao diện

#### 2.7.1. Giao diện Chat (Wireframe)
- Layout: Header (logo + status) → Messages Area → Input Bar.
- Render Markdown bảng biểu trong tin nhắn.
- Nút phản hồi 👍/👎 trên mỗi tin nhắn bot.

#### 2.7.2. Giao diện Admin (Wireframe)
- Đăng nhập → Dashboard: biểu đồ intent, top ngành, thời gian TB.
- Bảng quản lý file dữ liệu (upload/xóa/re-index).
- Bảng feedback người dùng.

### 2.8. Tổng kết chương

---

## CHƯƠNG 3. CÀI ĐẶT VÀ TRIỂN KHAI

> **Nguyên tắc:** Chương này trả lời "CÀI ĐẶT NHƯ THẾ NÀO" — trích mã nguồn, giải thích kỹ thuật, ảnh chụp kết quả. Không lặp lại sơ đồ/bảng đã có ở Chương 2.

### 3.1. Môi trường và công nghệ

| Thành phần | Công nghệ | Phiên bản |
|------------|-----------|-----------|
| Ngôn ngữ | Python | ≥ 3.10 |
| Web Server | Flask + Flask-CORS | 3.1.1 |
| LLM Inference | Ollama (local) | — |
| LLM Model | Qwen2.5 | 14B |
| Embedding | BGE-M3 (qua Ollama) | 1024 dim |
| Vector DB | ChromaDB | 0.6.3 |
| Keyword Search | rank_bm25 (BM25Okapi) | 0.2.2 |
| Tokenizer tiếng Việt | Underthesea | 6.8.4 |
| Telegram Bot | python-telegram-bot | 21.11 |
| Facebook Webhook | Flask Blueprint + Graph API v19.0 | — |
| Authentication | PyJWT + bcrypt | 2.10.1 / 4.3.0 |
| Analytics | JSON file-based logging | — |

### 3.2. Xử lý và nạp dữ liệu (`chunking.py`, `indexer.py`)

#### 3.2.1. Chunking dữ liệu JSON
- Trích mã `chunk_diem_chuan()`: nhóm record theo `ma_nganh` → sinh text tự nhiên + metadata.
- Trích mã `chunk_diem_quy_doi()`: embed toàn bộ bảng tra, đánh dấu "KHÔNG được nội suy".
- `chunk_all_files()`: dispatcher — quét thư mục, gọi đúng hàm chunking theo tên file.

#### 3.2.2. Chunking dữ liệu Markdown
- `chunk_nganh_md()`: regex trích section (tuyển sinh / đầu ra / việc làm) từ frontmatter YAML.
- `chunk_hoc_bong()`: xử lý 2 cấp heading (`##` nhóm → `###` chi tiết).
- `chunk_faq_md()`: pattern `**Q:...**` tách từng cặp Q&A.

#### 3.2.3. Indexing Pipeline
- `build_index()`: (1) xóa index cũ → (2) chunking → (3) embedding batch 20 (BGE-M3 qua Ollama) → (4) lưu ChromaDB → (5) xây BM25.
- Xử lý edge case: fallback zero-vector khi embedding lỗi; flatten list metadata cho ChromaDB.

### 3.3. Cài đặt RAG Pipeline (`pipeline.py`)

#### 3.3.1. Router hai tầng
- `fast_route()`: ~60 regex pattern, guard theo thứ tự ưu tiên.
  - Trích mã minh họa: guard B1 đòi hỏi SỐ LIỆU (regex `\d+`), còn C thì không có số.
- `llm_route()`: gọi LLM với `ROUTER_PROMPT` (~30 dòng prompt + ví dụ phân loại), parse 2 ký tự trả về.
- `route()`: thử fast_route trước, fallback llm_route.

#### 3.3.2. Entity Extraction
- `extract_entities()`: 6 regex pattern (`ma_nganh`, `diem`, `to_hop`, `khu_vuc`, `nam`, `phuong_thuc`).
- `NGANH_ALIASES`: dict ~60 alias → tên ngành chính thức (trích mã minh họa).

#### 3.3.3. Search và Ranking
- `hybrid_search()`:
  - ChromaDB query (vector) với `apply_chroma_filter()`.
  - BM25 scoring với `word_tokenize()` (Underthesea).
  - Hợp nhất RRF (`k_const = 60`), lấy top 20.
- `build_filter()`: ánh xạ intent + entity → điều kiện filter metadata. Trích mã minh họa filter cho intent A1 vs C.
- Fallback: nếu filter trả < 2 kết quả → search lại không filter.

#### 3.3.4. Query Enhancement (tuỳ chọn theo RAG_LITE)
- `rewrite_query()`: LLM chuẩn hóa (thêm năm, mở rộng viết tắt). Bỏ qua khi RAG_LITE + intent đơn giản.
- `generate_hyde()`: chỉ chạy cho A2, B2. Blend embedding: `0.7 * query_vec + 0.3 * hyde_vec`.
- `expand_query()`: sinh 2 sub-query bổ sung cho A2, B2 → merge kết quả.

#### 3.3.5. Reranker và Self-Reflect
- `rerank()`: gọi remote reranker (BGE-Reranker API), fallback cắt top_k nếu không khả dụng.
- `self_reflect()`: prompt 3 trạng thái (SUFFICIENT/PARTIAL/MISSING). Khi MISSING vẫn giữ chunks — không xóa.

#### 3.3.6. Context Enrichment và Generation
- `enrich_context()` (`structured.py`): inject snippet JSON chính thức (điểm chuẩn, chỉ tiêu, quy mô) vào đầu context — đảm bảo LLM không bỏ sót số liệu.
- `generate_response()`: ghép System Prompt (520 dòng, từ `prompts.py`) + context + VI_RULE + query → `call_llm()`.
- `sanitize_answer_vietnamese()`: loại bỏ ký tự CJK lẫn trong output (xử lý model lệch ngôn ngữ).
- RAG_LITE: bỏ qua HyDE + Self-Reflect cho intent A1/C/B1 → giảm latency từ ~10s xuống 2–3s.

### 3.4. Cài đặt Deterministic Engine (`structured.py`)

#### 3.4.1. Tính điểm xét tuyển
- `try_deterministic_b1_answer()`: regex parse điểm từng môn / tổng điểm / HSA / TSA / học phí → tính trực tiếp.
- `compute_pt3_admission()`: công thức giảm dần khi Σ ≥ 22.5. Trích mã minh họa.
- Tính PT2: parse `tb toán/lý/anh` + `ielts` hoặc `giải hsg` → `ĐXT = ĐKQHT × 2 + ĐQĐCC`.
- Tính học phí: `HP = số_TC × hệ_số × đơn_giá` (phân biệt lý thuyết/thực hành/thể chất).

#### 3.4.2. Tra bảng quy đổi
- `lookup_hsa()`, `lookup_tsa()`, `lookup_kqhb()`: duyệt bảng JSON, trả đúng giá trị. `@lru_cache` chỉ đọc file 1 lần.

#### 3.4.3. Tra cứu Deterministic (KB)
- `try_deterministic_kb_answer()`: trả lời trực tiếp không qua RAG cho: chỉ tiêu ngành, điều kiện IELTS PT2, tỷ lệ việc làm.
- `resolve_ma_chi_tieu()`: phân giải mã ngành khi tên mơ hồ (ví dụ: "Cơ điện tử" vs "Cơ điện tử ô tô").

### 3.5. Cài đặt thiết kế Prompt (`prompts.py`)

- `SYSTEM_PROMPT_TEMPLATE` (520 dòng): vai trò, quy tắc dùng context, xử lý theo 8 intent, quy tắc tính toán chi tiết, format trả lời, 8 câu hỏi mẫu.
- `VI_RULE`: ép LLM trả lời 100% tiếng Việt, phân biệt A01 vs A00.
- Nguyên tắc: prompt dài nhưng chi tiết → LLM ít sai hơn so với prompt ngắn.

### 3.6. Cài đặt API Server (`app.py`)

- REST API: 11 endpoint (chat, feedback, health, admin CRUD, analytics, facebook webhook).
- `admin_required` decorator: verify JWT token cho route admin.
- `init_app()`: load RAG index + register Facebook Blueprint + start Telegram bot thread.

### 3.7. Cài đặt Bot đa kênh

#### 3.7.1. Telegram (`telegram.py`)
- `start_telegram_bot_async()`: chạy polling trong thread riêng (daemon), song song Flask.
- Xử lý tin nhắn dài: tách thành nhiều phần (limit 4000 ký tự).

#### 3.7.2. Facebook Messenger (`facebook.py`)
- Flask Blueprint `/api/webhook/facebook`. Webhook verify + receive message → `handle_query()` → reply qua Graph API.

### 3.8. Cài đặt Analytics (`analytics.py`)

- `log_query()`: ghi intent, ngành, thời gian, số chunks → `analytics_log.json`. Auto-prune > 7 ngày.
- `log_feedback()`: ghi thumbs-up/down + câu hỏi/trả lời → `feedback_log.json`.
- `get_stats()`: aggregate cho Dashboard (đếm intent, top 10 ngành, thời gian TB).

### 3.9. Cài đặt giao diện

#### 3.9.1. Chat UI
- Dark theme: CSS Variables (17 biến), Glassmorphism (`backdrop-filter: blur`), gradient HaUI Red.
- Animation: float 3D logo, fadeIn tin nhắn, pulse typing indicator.
- Render Markdown bảng biểu trong tin nhắn bot. Responsive mobile (media query 768px).

#### 3.9.2. Admin Dashboard
- Login → Dashboard (Chart.js: Doughnut intent, Bar top ngành) → File manager → Feedback table.

### 3.10. Tổng kết chương

---

## CHƯƠNG 4. KIỂM THỬ VÀ ĐÁNH GIÁ

> **Nguyên tắc:** Chương này trình bày phương pháp đánh giá, kết quả định lượng, phân tích nguyên nhân, kết luận. Không lặp lại lý thuyết metrics đã nêu khái quát ở Chương 1.

### 4.1. Bộ dữ liệu kiểm thử (`test_dataset.json`)

#### 4.1.1. Cấu trúc test case
- Mỗi test case: `id`, `category`, `difficulty`, `question`, `expected_intent`, `ground_truth`, `ground_truth_full`, `key_facts`, `eval_type`.
- 4 loại `eval_type`: `exact` (số liệu chính xác), `contains` (từ khóa), `decision` (đỗ/trượt), `semantic`.

#### 4.1.2. Phân bố
- Bảng thống kê: số test case theo intent / theo độ khó / theo category.

### 4.2. Phương pháp đánh giá (`evaluate.py`)

#### 4.2.1. Đánh giá Rule-based (chính)
- `score_factual()`: so khớp `key_facts`, tolerance số liệu ±0.02.
- `score_answer_relevancy_rule()`: overlap từ khóa có trọng số với ground_truth.
- `score_completeness_rule()`: tỷ lệ key_facts xuất hiện.
- Overall: `Fact × 35 + Rel × 25 + Comp × 20 + Intent × 20` → điểm 0–100.

#### 4.2.2. Đánh giá LLM Judge (phụ, tuỳ chọn)
- LLM thứ hai chấm 1–5: Faithfulness, Relevancy, Completeness, Context Precision, Context Recall.
- Blend: 70% rule-based + 30% LLM judge.

#### 4.2.3. Root Cause Analysis
- `diagnose_failure()`: phân loại lỗi → ROUTER / RETRIEVER / GENERATOR / STRUCTURED / OK.
- Sinh `evaluation_diagnosis.json`: ghi rõ component lỗi, file cần sửa, hàm cần sửa, ví dụ.

### 4.3. Kết quả đánh giá

*(Chạy `python -m tests.evaluate` và điền số liệu thực tế vào các bảng dưới)*

#### 4.3.1. Kết quả tổng hợp
- Bảng: Intent Accuracy, Avg Factual, Avg Relevancy, Avg Completeness, Avg Overall, Avg Time.

#### 4.3.2. Kết quả theo Intent

| Intent | N | Intent Acc | Factual | Overall |
|--------|---|-----------|---------|---------|
| A1 | — | — | — | — |
| A2 | — | — | — | — |
| B1 | — | — | — | — |
| B2 | — | — | — | — |
| C  | — | — | — | — |
| D  | — | — | — | — |
| E  | — | — | — | — |
| F  | — | — | — | — |

#### 4.3.3. Phân bố Root Cause

| Component | Số lỗi | Tỷ lệ | Ý nghĩa |
|-----------|--------|--------|----------|
| OK | — | — | Trả lời chính xác |
| ROUTER | — | — | Phân loại intent sai |
| RETRIEVER | — | — | Context sai chủ đề hoặc thiếu |
| GENERATOR | — | — | LLM sinh sai dù context đúng |
| STRUCTURED | — | — | Hàm tính toán sai |

#### 4.3.4. Phân tích thời gian phản hồi
- Thời gian TB toàn pipeline.
- So sánh: Deterministic B1 (short-circuit) vs RAG đầy đủ vs RAG_LITE.

### 4.4. Kiểm thử chức năng

- Ảnh chụp màn hình minh họa cho mỗi chức năng F1–F8:
  - F1: Tra cứu điểm chuẩn 1 ngành.
  - F2: Tính điểm PT3 có ưu tiên KV + ĐT.
  - F3: Gợi ý ngành (bảng An toàn/Vừa sức/Mạo hiểm).
  - F4: Hướng dẫn thủ tục (trả lời theo bước).
  - F5: So sánh ngành dạng bảng.
  - F6: Admin upload file + re-index.
  - F7: Chat trên Telegram.
  - F8: Nút feedback 👍/👎.
- Kiểm thử tình huống biên: ngoài phạm vi (F), điểm vượt thang (>30), câu hỏi tiếng Anh.

### 4.5. Phân tích tổng hợp

#### 4.5.1. Điểm mạnh
- Deterministic Engine: 100% chính xác cho tính toán, loại bỏ sai số LLM.
- Hybrid Search + Pre-filter: giảm nhiễu, context chính xác theo metadata.
- Đánh giá component-level: biết chính xác lỗi ở Router, Retriever hay Generator → sửa đúng chỗ.

#### 4.5.2. Hạn chế
- Không hỗ trợ multi-turn conversation (không lưu lịch sử hội thoại).
- Regex Router có thể miss pattern mới chưa lập trình.
- Phụ thuộc tốc độ inference LLM on-premise.

#### 4.5.3. Hướng phát triển
- Bổ sung conversation memory (multi-turn).
- Fine-tune Router model riêng thay regex + generic LLM.
- Triển khai cloud (Docker) phục vụ thực tế.
- Tích hợp crawl tự động từ website HaUI.

### 4.6. Tổng kết chương

---

## KẾT LUẬN

### 1. Kết quả đạt được
- Đối chiếu từng mục tiêu ở Lời mở đầu với kết quả thực tế.

### 2. Đóng góp
- Kiến trúc RAG nâng cao cho domain tuyển sinh tiếng Việt.
- Mô hình Deterministic Fallback + RAG — giải pháp cho bài toán cần cả NLU lẫn tính toán chính xác.
- Framework đánh giá RAG component-level có khả năng tái sử dụng.

### 3. Hướng phát triển
- 3–5 hướng cụ thể.

---

## TÀI LIỆU THAM KHẢO

1. Lewis, P., et al. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS.
2. Vaswani, A., et al. (2017). *Attention Is All You Need*. NeurIPS.
3. Robertson, S., & Zaragoza, H. (2009). *The Probabilistic Relevance Framework: BM25 and Beyond*. Foundations and Trends in IR.
4. Gao, L., et al. (2023). *Precise Zero-Shot Dense Retrieval without Relevance Labels (HyDE)*. ACL.
5. Cormack, G. V., et al. (2009). *Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods*. SIGIR.
6. Chen, J., et al. (2024). *BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity*. arXiv.
7. Qwen Team. (2024). *Qwen2.5 Technical Report*. Alibaba Cloud.
8. Tài liệu tuyển sinh HaUI 2025–2026.

---

## PHỤ LỤC

### Phụ lục A. Mã nguồn chính
- `pipeline.py` (RAG Pipeline).
- `structured.py` (Deterministic Engine).
- `evaluate.py` (Evaluation Framework).

### Phụ lục B. Mẫu dữ liệu
- Trích `diem_chuan_2023_2024_2025.json` (3 ngành mẫu).
- Trích `diem_quy_doi.json` (bảng HSA/TSA).

### Phụ lục C. Kết quả đánh giá chi tiết
- Trích `evaluation_results.json`.
- Trích `evaluation_diagnosis.json`.

### Phụ lục D. Ảnh chụp giao diện
- Chat UI (Desktop + Mobile).
- Admin Dashboard.
- Telegram Bot.
