# Hướng dẫn kỹ thuật: Chunking → Embedding → Routing → Retrieval
## HaUI RAG Chatbot — Thiết kế chi tiết

---

## PHẦN 1: CHUNKING STRATEGY

### 1.1 Nguyên tắc chung

Mỗi chunk phải đáp ứng 3 điều kiện:
- **Tự chứa** (self-contained): đọc một mình vẫn hiểu được
- **Có metadata đầy đủ** để pre-filter trước khi vector search
- **Không vượt quá 512 token** (giới hạn tối ưu cho BGE-M3)

---

### 1.2 Chunking JSON — điểm chuẩn

File: `diem_chuan_2023_2024_2025.json`

**Vấn đề:** File có ~350 records, mỗi record là một (ngành × năm × phương thức). Nếu vector từng record thì mỗi lần query "điểm chuẩn CNTT" sẽ lấy được 3 record rời rạc thay vì toàn bộ bức tranh.

**Giải pháp: nhóm theo ngành**

```python
def chunk_diem_chuan(records):
    from collections import defaultdict
    groups = defaultdict(list)
    for r in records:
        groups[r['ma_nganh']].append(r)
    
    chunks = []
    for ma_nganh, recs in groups.items():
        ten_nganh = recs[0]['ten_nganh']
        nhom = recs[0].get('nhom_nganh', '')
        
        by_year = defaultdict(list)
        for r in recs:
            by_year[r['nam']].append(r)
        
        lines = [
            f"# Điểm chuẩn: {ten_nganh} (mã {ma_nganh})",
            f"Nhóm ngành: {nhom}",
            ""
        ]
        for year in sorted(by_year.keys(), reverse=True):
            year_recs = by_year[year]
            # Năm 2025: điểm chuẩn CHUNG cho tất cả phương thức áp dụng
            if year == 2025:
                r = year_recs[0]
                pt_list = ', '.join(r.get('cac_phuong_thuc_ap_dung', []))
                lines.append(f"Năm {year} (điểm chuẩn chung): {r['diem_chuan']} điểm (thang {r['thang_diem']})")
                lines.append(f"  Phương thức áp dụng: {pt_list}")
                lines.append(f"  Lưu ý: Năm 2025 HaUI áp dụng 1 mức điểm chuẩn chung cho tất cả phương thức trên.")
            else:
                lines.append(f"Năm {year} (điểm chuẩn riêng từng phương thức):")
                for r in year_recs:
                    pt = r['phuong_thuc_ten']
                    lines.append(f"  - PT {r['phuong_thuc_code']} ({pt}): {r['diem_chuan']} điểm")
        
        text = '\n'.join(lines)
        chunks.append({
            'text': text,
            'metadata': {
                'source': 'diem_chuan',
                'loai': 'diem_chuan',
                'ma_nganh': ma_nganh,
                'ten_nganh': ten_nganh,
                'nhom_nganh': nhom,
                'nam_list': sorted(by_year.keys()),
                'nam_moi_nhat': max(by_year.keys())
            }
        })
    return chunks
```

**Output cho ngành CNTT:**
```
# Điểm chuẩn: Công nghệ thông tin (mã 7480201)
Nhóm ngành: CNTT

Năm 2025 (điểm chuẩn chung): 23.09 điểm (thang 30)
  Phương thức áp dụng: PT2, PT3, PT5
  Lưu ý: Năm 2025 HaUI áp dụng 1 mức điểm chuẩn chung cho tất cả phương thức trên.
Năm 2024 (điểm chuẩn riêng từng phương thức):
  - PT3 (thpt): 25.22 điểm
  - PT4 (hoc_ba): 28.89 điểm
  - PT2 (chung_chi_hsg): 27.00 điểm
  - PT5 (danh_gia_nl): 18.50 điểm
Năm 2023 (điểm chuẩn riêng từng phương thức):
  - PT3 (thpt): 25.19 điểm
  - PT4 (hoc_ba): 29.23 điểm
  - PT2 (chung_chi_hsg): 28.93 điểm
  - PT6 (danh_gia_tu_duy): 15.43 điểm
```

---

### 1.3 Chunking JSON — chỉ tiêu và tổ hợp

File: `chi_tieu_to_hop_2025.json` + `to_hop_mon_thi.json`

**Giải pháp: join và expand tổ hợp**

```python
def chunk_chi_tieu_to_hop(records, to_hop_map):
    """
    to_hop_map: {"A01": ["Toán", "Vật lý", "Tiếng Anh"], ...}
    """
    chunks = []
    for r in records:
        to_hop_expanded = []
        for code in r['to_hop']:
            mon = to_hop_map.get(code, [])
            to_hop_expanded.append(f"{code} ({'-'.join(mon)})")
        
        text = f"""# Chỉ tiêu & tổ hợp: {r['ten_nganh']} (mã {r['ma_nganh']})
Nhóm ngành: {r.get('nhom', '')}
Chỉ tiêu 2025: {r['chi_tieu']} sinh viên
Tổ hợp xét tuyển: {', '.join(to_hop_expanded)}
Phương thức: {', '.join(r['phuong_thuc'])}
"""
        chunks.append({
            'text': text,
            'metadata': {
                'source': 'chi_tieu',
                'loai': 'chi_tieu_to_hop',
                'ma_nganh': r['ma_nganh'],
                'ten_nganh': r['ten_nganh'],
                'nhom_nganh': r.get('nhom', ''),
                'to_hop': r['to_hop'],
                'phuong_thuc': r['phuong_thuc'],
                'chi_tieu': r['chi_tieu'],
                'nam': 2025
            }
        })
    return chunks
```

---

### 1.3b Chunking JSON — chỉ tiêu tuyển sinh 2026

File: `chi_tieu_tuyen_sinh_2026.json`

**[FIX v2.2] File này bị bỏ sót trong phiên bản trước.** Cần chunk riêng để retrieve khi user hỏi "chỉ tiêu năm 2026", "tổng chỉ tiêu HaUI 2026".

```python
def chunk_chi_tieu_2026(data):
    lines = [
        f"# Chỉ tiêu tuyển sinh HaUI năm {data['nam']}",
        f"Nguồn: {data.get('nguon', '')}",
        f"Lưu ý: {data.get('ghi_chu', '')}",
        ""
    ]
    for item in data['chi_tieu']:
        lines.append(f"- {item['he_dao_tao']}: {item['chi_tieu']:,} chỉ tiêu")
    lines.append(f"\nTổng chỉ tiêu: {data['tong_chi_tieu']:,} sinh viên")

    return [{
        'text': '\n'.join(lines),
        'metadata': {
            'source': 'chi_tieu_tuyen_sinh_2026',
            'loai': 'chi_tieu_tong',
            'nam': 2026
        }
    }]
```

---

### 1.4 Chunking JSON — điểm ưu tiên và quy đổi

File: `diem_uu_tien.json`, `diem_quy_doi.json`

```python
def chunk_diem_uu_tien(data):
    # Chunk 1: Ưu tiên khu vực
    kv_text = "# Điểm ưu tiên khu vực tuyển sinh (2026)\n\n"
    for kv in data['uu_tien_khu_vuc']:
        kv_text += f"- {kv['ma']} ({kv['ten']}): +{kv['diem']} điểm\n"
    kv_text += "\nCông thức áp dụng:\n"
    kv_text += "- Khi tổng điểm < 22.5: cộng thẳng mức điểm ưu tiên (KHÔNG dùng công thức giảm dần).\n"
    kv_text += "- Khi tổng điểm ≥ 22.5: Điểm ưu tiên thực = [(30 - Tổng điểm) / 7.5] × Mức ưu tiên"
    
    # Chunk 2: Ưu tiên đối tượng  
    dt_text = "# Điểm ưu tiên đối tượng chính sách (2026)\n\n"
    for nhom in data['uu_tien_doi_tuong']:
        dt_text += f"Nhóm {nhom['nhom']} (+{nhom['diem']} điểm): Đối tượng {', '.join(nhom['doi_tuong'])}\n"
    dt_text += "\nLưu ý: Thí sinh thuộc nhiều diện chỉ được hưởng một mức điểm ưu tiên cao nhất."
    
    return [
        {'text': kv_text, 'metadata': {'loai': 'diem_uu_tien', 'loai_con': 'khu_vuc', 'nam': 2026}},
        {'text': dt_text, 'metadata': {'loai': 'diem_uu_tien', 'loai_con': 'doi_tuong', 'nam': 2026}}
    ]

def chunk_diem_quy_doi(data):
    """
    GIỮ TOÀN BỘ bảng tra cứu — KHÔNG dùng skip/sample.
    BGE-M3 context 8192 token đủ sức chứa bảng đầy đủ.
    Nếu sample (::5), các giá trị lẻ như HSA=91,92,93,94 sẽ bị mất
    và model nội suy sai khi user hỏi điểm chính xác.
    """
    chunks = []
    for key in ['quy_doi_HSA', 'quy_doi_TSA', 'quy_doi_KQHB']:
        qd = data[key]
        bang = qd['bang']  # giữ toàn bộ, không lấy mẫu

        lines = [f"# Bảng quy đổi đầy đủ: {qd['ten']}"]
        lines.append(f"Kỳ thi: {qd['ki_thi']}")
        lines.append(f"Thang gốc: {qd['thang_goc']} → Thang quy đổi: {qd['thang_quy_doi']}")
        lines.append(f"Ghi chú: {qd.get('ghi_chu', '')}")
        lines.append("QUAN TRỌNG: Tra bảng đúng giá trị, KHÔNG được nội suy giữa hai mốc.")
        lines.append("Bảng tra cứu đầy đủ (mỗi dòng: điểm_từ–điểm_đến → điểm_quy_đổi):")
        for row in bang:
            if row['tu'] == row['den']:
                lines.append(f"  {row['tu']} → {row['diem_quy_doi']}")
            else:
                lines.append(f"  {row['tu']}–{row['den']} → {row['diem_quy_doi']}")

        chunks.append({
            'text': '\n'.join(lines),
            'metadata': {
                'loai': 'diem_quy_doi',
                'loai_con': key,
                'ki_thi': qd['ki_thi']
            }
        })
    return chunks
```

---

### 1.5 Chunking Markdown ngành học

**[FIX v2.2]** Mỗi file ngành (cả prefix `nganh_` lẫn không có prefix) tạo ra **3 chunks** riêng biệt.
Danh sách file ngành không có prefix `nganh_` được dispatch trong `NGANH_EXTRA_FILES`.

```python
import re

def chunk_nganh_md(filepath, content):
    # Extract metadata từ YAML front matter
    meta_match = re.search(r'---\n(.*?)\n---', content, re.DOTALL)
    meta = {}
    if meta_match:
        for line in meta_match.group(1).split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip().strip('"')
    
    ma_nganh = meta.get('ma_nganh', '')
    ten_nganh = meta.get('ten_nganh', '')
    
    tuyen_sinh = re.search(
        r'## Thông tin tuyển sinh\n(.*?)(?=\n##|\Z)', 
        content, re.DOTALL
    )
    dau_ra = re.search(
        r'## Chuẩn đầu ra.*?\n(.*?)(?=\n##|\Z)', 
        content, re.DOTALL
    )
    viec_lam = re.search(
        r'## Cơ hội việc làm\n(.*?)(?=\n##|\Z)', 
        content, re.DOTALL
    )
    
    chunks = []
    # FIX: 'nam' KHÔNG hardcode 2025 — lấy từ meta hoặc None
    # (file ngành mô tả chương trình, không gắn cứng với 1 năm tuyển sinh)
    base_meta = {
        'source': filepath,
        'loai': 'mo_ta_nganh',
        'ma_nganh': ma_nganh,
        'ten_nganh': ten_nganh,
        'nhom_nganh': meta.get('truong_khoa', ''),
        'nam': int(meta.get('nam', 0)) or None
    }
    
    if tuyen_sinh:
        text = f"# Thông tin tuyển sinh: {ten_nganh} (mã {ma_nganh})\n{tuyen_sinh.group(1).strip()}"
        chunks.append({'text': text, 'metadata': {**base_meta, 'loai_con': 'tuyen_sinh'}})
    
    if dau_ra:
        text = f"# Chuẩn đầu ra ngành {ten_nganh} (mã {ma_nganh})\n{dau_ra.group(1).strip()}"
        chunks.append({'text': text, 'metadata': {**base_meta, 'loai_con': 'dau_ra'}})
    
    if viec_lam:
        text = f"# Cơ hội việc làm ngành {ten_nganh} (mã {ma_nganh})\n{viec_lam.group(1).strip()}"
        chunks.append({'text': text, 'metadata': {**base_meta, 'loai_con': 'viec_lam'}})
    
    return chunks

# FIX: Danh sách file ngành KHÔNG có prefix 'nganh_' — bị bỏ sót trong phiên bản trước
NGANH_EXTRA_FILES = [
    'cong_nghe_ky_thuat_hoa_hoc.md',
    'cong_nghe_ky_thuat_moi_truong.md',
    'cong_nghe_thuc_pham.md',
    'hoa_duoc.md',
    'cong_nghe_det_may.md',
    'cong_nghe_vat_lieu_det_may.md',
    'thiet_ke_thoi_trang.md',
]
```

---

### 1.6 Chunking Markdown quy trình và FAQ

```python
def chunk_faq_md(content):
    """Chunk mỗi cặp Q&A thành 1 chunk riêng"""
    chunks = []
    qa_pattern = re.findall(r'\*\*Q:(.*?)\*\*(.*?)(?=\n---|\Z)', content, re.DOTALL)
    for q, a in qa_pattern:
        text = f"Câu hỏi: {q.strip()}\nTrả lời: {a.strip()}"
        chunks.append({
            'text': text,
            'metadata': {'loai': 'faq', 'source': 'faq_dang_ky_xet_tuyen'}
        })
    return chunks

def chunk_huong_dan_md(content, source_name):
    """Chunk theo từng bước / section heading"""
    sections = re.split(r'\n### ', content)
    chunks = []
    for section in sections[1:]:  # Bỏ section đầu (header)
        title_match = re.match(r'(.+?)\n', section)
        title = title_match.group(1) if title_match else 'Hướng dẫn'
        text = f"### {title}\n{section.strip()}"
        if len(text) > 2000:
            text = text[:2000] + '...'
        chunks.append({
            'text': text,
            'metadata': {'loai': 'huong_dan', 'source': source_name, 'section': title}
        })
    return chunks
```

---

### 1.7 Chunking JSON — học phí

File: `muc_thu_hoc_phi.json`

```python
def chunk_hoc_phi(data):
    """
    Mỗi nhóm chương trình đào tạo → 1 chunk.
    Cần chunk riêng để filter 'loai': 'hoc_phi' hoạt động đúng.
    """
    from collections import defaultdict
    groups = defaultdict(list)
    for item in data['hoc_phi_theo_chuong_trinh']:
        groups[item['nhom']].append(item)

    chunks = []
    for nhom, items in groups.items():
        lines = [f"# Học phí {nhom} — HaUI năm học {data.get('nam_hoc', '2025-2026')}"]
        for item in items:
            lines.append(f"- {item['chuong_trinh']}: {item['gia_tri']:,} {item['don_vi']}")
        chunks.append({
            'text': '\n'.join(lines),
            'metadata': {
                'loai': 'hoc_phi',
                'nhom': nhom,
                'nam_hoc': data.get('nam_hoc', '2025-2026'),
                'source': 'muc_thu_hoc_phi'
            }
        })
    return chunks
```

---

### 1.7b Chunking Markdown — cách tính học phí

File: `cach_tinh_hoc_phi_2025_2026.md`

**[FIX v2.2]** File này chứa **công thức tính HP = N_TCHP × H_LHP × ĐG** và các hệ số tín chỉ theo từng nhóm học phần. Cần chunk với `loai: 'hoc_phi'` để retrieve cùng với `muc_thu_hoc_phi.json` khi user hỏi tính học phí.

```python
def chunk_cach_tinh_hoc_phi(content, source_name='cach_tinh_hoc_phi'):
    """
    Dùng chunk_policy_md với loai='hoc_phi' thay vì loai='chinh_sach'.
    Đảm bảo filter 'loai__in': ['hoc_phi'] sẽ lấy được cả file này.
    """
    return chunk_policy_md(content, source_name, loai='hoc_phi')
```

---

### 1.8 Chunking Markdown — chính sách/giới thiệu (chunk theo heading ##)

Áp dụng cho: `ky_tuc_xa.md`, `hoc_bong.md`, `gioi_thieu_truong.md`, `quy_mo_dao_tao.md`,
`lich_tuyen_sinh_2026.md`, `chinh_sach_uu_tien.md`, `van_bang.md`,
`phuong_thuc_tuyen_sinh_2025.md`

```python
def chunk_policy_md(content, source_name, loai='chinh_sach'):
    """
    Split theo heading ## (không phải ###).
    Gắn tiêu đề cha vào đầu mỗi chunk con để đảm bảo tự chứa.
    """
    import re
    doc_title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
    doc_title = doc_title_match.group(1).strip() if doc_title_match else source_name

    sections = re.split(r'\n(?=## )', content)
    chunks = []
    for section in sections:
        if not section.strip():
            continue
        title_match = re.match(r'## (.+)', section.strip())
        if not title_match:
            if len(section.strip()) > 50:
                chunks.append({
                    'text': f"# {doc_title}\n{section.strip()[:2000]}",
                    'metadata': {'loai': loai, 'source': source_name, 'section': 'gioi_thieu'}
                })
            continue

        section_title = title_match.group(1).strip()
        text = f"# {doc_title} — {section_title}\n{section.strip()}"
        if len(text) > 2000:
            text = text[:2000] + '...'
        chunks.append({
            'text': text,
            'metadata': {'loai': loai, 'source': source_name, 'section': section_title}
        })
    return chunks
```

**Bảng ánh xạ file → loai metadata:**

```python
POLICY_FILE_MAP = {
    'ky_tuc_xa.md':                    'ky_tuc_xa',
    'hoc_bong.md':                     'hoc_bong',       # Xử lý riêng bằng chunk_hoc_bong
    'gioi_thieu_truong.md':            'gioi_thieu',
    'quy_mo_dao_tao.md':               'gioi_thieu',
    'lich_tuyen_sinh_2026.md':         'lich_tuyen_sinh',
    'chinh_sach_uu_tien.md':           'diem_uu_tien',   # FIX: trước map sai sang 'chinh_sach'
    'van_bang.md':                     'chinh_sach',
    'phuong_thuc_tuyen_sinh_2025.md':  'huong_dan',
    'cach_tinh_hoc_phi_2025_2026.md':  'hoc_phi',        # FIX: thêm mới, dùng chunk_cach_tinh_hoc_phi
}
```

---

### 1.9 Chunking đặc biệt — hoc_bong.md

File này có cấu trúc nhiều lớp (nhóm học bổng → điều kiện chi tiết). Inject tên nhóm học bổng vào mỗi chunk con:

```python
def chunk_hoc_bong(content):
    """
    Chunk theo nhóm học bổng lớn (## heading), kèm tên nhóm ở đầu mỗi sub-chunk.
    """
    import re
    chunks = []

    top_sections = re.split(r'\n(?=## \d+\.)', content)
    for section in top_sections:
        if not section.strip() or not re.match(r'## \d+', section.strip()):
            continue
        group_title_match = re.match(r'## (.+)', section.strip())
        if not group_title_match:
            continue
        group_title = group_title_match.group(1).strip()

        sub_sections = re.split(r'\n(?=### )', section)
        overview = sub_sections[0]
        if len(overview.strip()) > 60:
            chunks.append({
                'text': f"# Học bổng HaUI — {group_title}\n{overview.strip()[:1500]}",
                'metadata': {'loai': 'hoc_bong', 'source': 'hoc_bong', 'nhom': group_title}
            })

        for sub in sub_sections[1:]:
            sub_title_match = re.match(r'### (.+)', sub.strip())
            sub_title = sub_title_match.group(1).strip() if sub_title_match else ''
            text = f"# Học bổng HaUI — {group_title} — {sub_title}\n{sub.strip()}"
            if len(text) > 2000:
                text = text[:2000] + '...'
            chunks.append({
                'text': text,
                'metadata': {
                    'loai': 'hoc_bong',
                    'source': 'hoc_bong',
                    'nhom': group_title,
                    'section': sub_title
                }
            })
    return chunks
```

---

### 1.10 Tổng hợp — hàm dispatch chunking

```python
import os, json

def chunk_all_files(project_dir):
    """
    Dispatch đúng function chunking cho từng file trong project.
    Trả về list tất cả chunks (có metadata đầy đủ).
    
    Ngữ cảnh thời gian (năm 2026):
    - Điểm chuẩn mới nhất trong dữ liệu: 2025
    - Chỉ tiêu tổng hợp mới nhất: 2026
    - Khi user không ghi rõ năm → query rewrite thêm ngữ cảnh phù hợp
    """
    all_chunks = []

    # --- JSON files ---
    diem_chuan_path = os.path.join(project_dir, 'diem_chuan_2023_2024_2025.json')
    if os.path.exists(diem_chuan_path):
        with open(diem_chuan_path, encoding='utf-8') as f:
            all_chunks.extend(chunk_diem_chuan(json.load(f)))

    chi_tieu_path = os.path.join(project_dir, 'chi_tieu_to_hop_2025.json')
    to_hop_path = os.path.join(project_dir, 'to_hop_mon_thi.json')
    if os.path.exists(chi_tieu_path) and os.path.exists(to_hop_path):
        with open(chi_tieu_path, encoding='utf-8') as f:
            chi_tieu = json.load(f)
        with open(to_hop_path, encoding='utf-8') as f:
            to_hop_map = {r['ma']: r['mon'] for r in json.load(f)}
        all_chunks.extend(chunk_chi_tieu_to_hop(chi_tieu, to_hop_map))

    # FIX: Thêm chi_tieu_tuyen_sinh_2026.json — bị bỏ sót trong v2.1
    chi_tieu_2026_path = os.path.join(project_dir, 'chi_tieu_tuyen_sinh_2026.json')
    if os.path.exists(chi_tieu_2026_path):
        with open(chi_tieu_2026_path, encoding='utf-8') as f:
            all_chunks.extend(chunk_chi_tieu_2026(json.load(f)))

    for fname in ['diem_uu_tien.json']:
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                all_chunks.extend(chunk_diem_uu_tien(json.load(f)))

    for fname in ['diem_quy_doi.json']:
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                all_chunks.extend(chunk_diem_quy_doi(json.load(f)))

    for fname in ['muc_thu_hoc_phi.json']:
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                all_chunks.extend(chunk_hoc_phi(json.load(f)))

    # --- Markdown ngành học (prefix 'nganh_') ---
    for fname in os.listdir(project_dir):
        if fname.startswith('nganh_') and fname.endswith('.md'):
            fpath = os.path.join(project_dir, fname)
            with open(fpath, encoding='utf-8') as f:
                content = f.read()
            all_chunks.extend(chunk_nganh_md(fname, content))

    # FIX: Các file ngành KHÔNG có prefix 'nganh_' — bị bỏ sót trong v2.1
    for fname in NGANH_EXTRA_FILES:
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                content = f.read()
            all_chunks.extend(chunk_nganh_md(fname, content))

    # --- FAQ & Hướng dẫn ---
    for fname in os.listdir(project_dir):
        fpath = os.path.join(project_dir, fname)
        if not fname.endswith('.md'):
            continue
        with open(fpath, encoding='utf-8') as f:
            content = f.read()
        if fname.startswith('faq_'):
            all_chunks.extend(chunk_faq_md(content))
        elif fname.startswith('huong_dan_'):
            all_chunks.extend(chunk_huong_dan_md(content, fname.replace('.md', '')))

    # --- Học bổng (chunking đặc biệt) ---
    hb_path = os.path.join(project_dir, 'hoc_bong.md')
    if os.path.exists(hb_path):
        with open(hb_path, encoding='utf-8') as f:
            all_chunks.extend(chunk_hoc_bong(f.read()))

    # FIX: cach_tinh_hoc_phi dùng hàm riêng (loai='hoc_phi'), không dùng chunk_policy_md chung
    cach_tinh_path = os.path.join(project_dir, 'cach_tinh_hoc_phi_2025_2026.md')
    if os.path.exists(cach_tinh_path):
        with open(cach_tinh_path, encoding='utf-8') as f:
            all_chunks.extend(chunk_cach_tinh_hoc_phi(f.read()))

    # --- File chính sách / giới thiệu ---
    for fname, loai in POLICY_FILE_MAP.items():
        # Bỏ qua các file đã xử lý riêng ở trên
        if fname in ('hoc_bong.md', 'cach_tinh_hoc_phi_2025_2026.md'):
            continue
        fpath = os.path.join(project_dir, fname)
        if os.path.exists(fpath):
            with open(fpath, encoding='utf-8') as f:
                all_chunks.extend(chunk_policy_md(f.read(), fname.replace('.md', ''), loai))

    # Đánh ID duy nhất cho từng chunk
    for i, chunk in enumerate(all_chunks):
        chunk['id'] = f"chunk_{i:05d}"

    return all_chunks
```

---

## PHẦN 2: EMBEDDING

### 2.1 BGE-M3 — lý do chọn

BGE-M3 hỗ trợ đồng thời dense + sparse embedding, phù hợp tiếng Việt, context length 8192 token. Dùng qua Ollama với model `bge-m3:latest`.

### 2.2 Cấu hình embedding

```python
def embed_chunk(text, model='bge-m3:latest'):
    text = text.strip()
    if len(text) > 2000:
        text = text[:2000]
    response = ollama.embeddings(model=model, prompt=text, options={'num_ctx': 512})
    return response['embedding']

def embed_query(query, model='bge-m3:latest'):
    prefixed = f"Represent this sentence for searching relevant passages: {query}"
    response = ollama.embeddings(model=model, prompt=prefixed, options={'num_ctx': 256})
    return response['embedding']
```

### 2.3 BM25 index — xây dựng

```python
from rank_bm25 import BM25Okapi
import underthesea

def build_bm25_index(chunks):
    tokenized = []
    for chunk in chunks:
        tokens = underthesea.word_tokenize(chunk['text'])
        meta_tokens = [
            chunk['metadata'].get('ma_nganh', ''),
            chunk['metadata'].get('ten_nganh', ''),
            str(chunk['metadata'].get('nam_moi_nhat', ''))
        ]
        tokens.extend([t for t in meta_tokens if t])
        tokenized.append(tokens)
    return BM25Okapi(tokenized)
```

---

## PHẦN 3: ROUTER

### 3.1 Router prompt (~200 token)

```
Phân loại câu hỏi tuyển sinh đại học vào ĐÚNG 1 nhóm:

A1 - Tra cứu đơn: điểm chuẩn/học phí/chỉ tiêu/tổ hợp của 1 ngành hoặc 1 vấn đề cụ thể
A2 - Tra cứu nhiều: liệt kê nhiều ngành, xếp hạng, xu hướng nhiều năm, điểm chuẩn toàn nhóm
B1 - Tính toán: tính điểm có ưu tiên, quy đổi HSA/TSA, tính học phí học phần
B2 - Tư vấn ngành: gợi ý ngành theo điểm + tổ hợp + sở thích
C  - Thủ tục/chính sách: đăng ký, hồ sơ, nhập học, học bổng, KTX, lịch tuyển sinh, phương thức xét tuyển, chỉ tiêu tổng hợp
D  - So sánh: ngành vs ngành, PT vs PT
E  - Chào hỏi / cảm ơn / hỏi về chatbot
F  - Ngoài phạm vi (trường khác, y tế, pháp luật...)

Lưu ý phân loại:
- "lịch tuyển sinh 2026", "chỉ tiêu 2026" (không có mã ngành) → C
- "ngành nào điểm thấp nhất", "liệt kê tất cả ngành CNTT" → A2
- "tính học phí 3 tín chỉ K20" → B1
- "điểm chuẩn ngành CNTT 2025" (1 ngành cụ thể) → A1

Trả về ĐÚNG 1 trong: A1 A2 B1 B2 C D E F
Câu hỏi: {query}
```

### 3.2 Router dự phòng (regex fast-path)

```python
import re

FAST_PATTERNS = {
    'A1': [
        r'điểm chuẩn.*(ngành|mã)\s+\d{7}',
        r'(điểm chuẩn|dc)\s+(cntt|ktpm|cơ điện|robot|kế toán)\s*\d{4}',
        r'học phí\s+(ngành|tín chỉ)',
        r'(học phí|mức thu).*(k20|k19|k18|tiếng anh|đại trà)',
        r'ký túc xá.*(giá|bao nhiêu|tiền)',
        r'phòng ktx.*(loại|chất lượng cao|tiêu chuẩn)',
        r'điểm chuẩn\s+\d{7}',
    ],
    'A2': [
        r'(các|tất cả|danh sách|toàn bộ).*(ngành|điểm chuẩn)',
        r'(điểm chuẩn|dc).*(các ngành|nhóm ngành)',
        r'(điểm chuẩn|dc)\s+(cntt|cơ khí|kinh tế|ngôn ngữ|du lịch)(?!\s*\d{4})',
        r'tổng hợp.*(điểm chuẩn|chỉ tiêu)',
        r'so sánh.*(điểm chuẩn|các năm)',
        r'xu hướng.*(điểm chuẩn|\d+ năm)',
        r'(ngành nào|ngành nào có).*(điểm|cao nhất|thấp nhất)',
        r'xếp hạng.*(điểm chuẩn|ngành)',
    ],
    'B1': [
        r'(tính|tôi được|em được).+điểm',
        r'\d+(\.\d+)?\s*(toán|lý|hóa|anh|văn)',
        r'quy đổi.*(hsa|tsa|đgnl|đgtd)',
        r'điểm ưu tiên',
        r'(kv1|kv2|kv3|kv2-nt).*(điểm|tính)',
        r'tính.*(học phí|hp)\s+\d+\s*(tín chỉ|tc)',
        r'học phí.*(học phần|\d+\s*tc|\d+\s*tín chỉ)',
        r'(hsa|tsa)\s+\d+.*(quy đổi|bằng|tương đương)',
    ],
    'B2': [
        r'ngành nào.*phù hợp',
        r'(nên|có thể).*(đăng ký|chọn) ngành',
        r'gợi ý ngành',
        r'với điểm.*(nên|có thể|đăng ký)',
        r'(đỗ|trúng tuyển).*(ngành|đâu)',
        r'em có thể vào.*ngành',
        r'ngành nào em.*(đỗ|vào được)',
    ],
    'C': [
        r'(cách|làm thế nào|hướng dẫn).*(đăng ký|nộp|nhập học)',
        r'hồ sơ.*(cần|gồm|bao gồm)',
        r'(bước|thủ tục)',
        r'(deadline|hạn nộp|thời hạn).*(hồ sơ|đăng ký)',
        r'(học bổng|hỗ trợ tài chính).*(điều kiện|xét|cách|làm sao)',
        r'(ký túc xá|ktx).*(đăng ký|thủ tục|cách)',
        r'(nhập học|khai giảng|bắt đầu học)',
        r'(lịch|thời gian|khi nào).*(tuyển sinh|nhập học|xét tuyển|công bố)',
        r'phương thức.*(là gì|như thế nào|gồm|có mấy)',
        r'chỉ tiêu\s+20(25|26)(?!\s*\d{7})',   # FIX: chỉ tiêu năm → C (không có mã ngành)
        r'lịch tuyển sinh\s+20(25|26)',
        r'(phương thức|pt[1-5])\s+(là gì|như thế nào)',
        r'điều kiện\s+(pt[1-5]|phương thức)',
    ],
    'D': [
        r'(so sánh|khác nhau|giống nhau).*(ngành|phương thức)',
        r'(ngành|pt)\s+\w+\s+(và|vs|hay)\s+\w+',
        r'nên chọn.*(ngành|phương thức).*(hay|hoặc)',
        r'\w+\s+hay\s+\w+.*(ngành|học)',
    ],
    'E': [
        r'^(xin chào|chào|hello|hi|cảm ơn|thanks)',
        r'bạn (là|có thể|giúp)',
        r'^(ok|được rồi|hiểu rồi|cảm ơn)',
        r'(chatbot|trợ lý|bot).*(là gì|tên gì)',
    ]
}

def fast_route(query):
    """
    Route nhanh bằng regex — không gọi LLM.
    Thứ tự ưu tiên: A2 > B2 > B1 > C > D > A1 > E
    """
    query_lower = query.lower()

    # Guard 1: điểm chuẩn nhóm ngành (nhiều ngành) → A2
    if re.search(r'(điểm chuẩn|dc)\s+(cntt|cơ khí|kinh tế|ngôn ngữ|du lịch|dệt)', query_lower):
        if not re.search(r'(ngành|mã)\s*\d{7}', query_lower):
            return 'A2'

    # Guard 2: "chỉ tiêu 2025/2026" không có mã ngành → C
    if re.search(r'chỉ tiêu\s+20(25|26)', query_lower):
        if not re.search(r'\d{7}', query_lower):
            return 'C'

    # Guard 3: "tính học phí N tín chỉ" → B1
    if re.search(r'tính.*(học phí|hp).*\d+\s*(tc|tín chỉ)', query_lower):
        return 'B1'

    for intent in ['A2', 'B2', 'B1', 'C', 'D', 'A1', 'E']:
        for pattern in FAST_PATTERNS.get(intent, []):
            if re.search(pattern, query_lower):
                return intent
    return None  # Fallback to LLM router
```

---

## PHẦN 4: QUERY REWRITE

### 4.1 Prompt rewrite

```
Chuẩn hóa câu hỏi tuyển sinh HaUI. Mở rộng viết tắt, thêm ngữ cảnh.

Từ điển viết tắt:
cntt → Công nghệ thông tin | ktpm → Kỹ thuật phần mềm
khmt → Khoa học máy tính | httt → Hệ thống thông tin
attt → An toàn thông tin | cđt → Cơ điện tử | oto → Ô tô
tđh / tự động → Điều khiển và tự động hóa
đgnl / hsa → Đánh giá năng lực ĐHQG Hà Nội (HSA)
đgtd / tsa / bk → Đánh giá tư duy ĐHBK Hà Nội (TSA)
hb / học bạ → xét kết quả học bạ (PT4)
thpt → thi tốt nghiệp THPT (PT3)
kv1/kv2/kv3 → khu vực ưu tiên
ut1/ut2 → đối tượng ưu tiên

Quy tắc thêm ngữ cảnh năm (NĂM HIỆN TẠI: 2026):
- Hỏi về lịch tuyển sinh, chỉ tiêu, nhập học mà không có năm → thêm "năm 2026"
- Hỏi về điểm chuẩn mà không có năm → thêm "điểm chuẩn gần nhất (2025)"
- Hỏi về học phí, KTX, học bổng mà không có năm → thêm "năm học 2025-2026"
- Không có tên trường → thêm "tại HaUI"
- Giữ nguyên số điểm, mã ngành

Trả về 1 câu query đã được chuẩn hóa (không giải thích).
Query gốc: {query}
```

### 4.2 Multi-query expansion

```python
def expand_query(query, intent):
    if intent in ['A2', 'B2']:
        prompt = f"""Tạo 2 câu hỏi liên quan bổ sung cho query sau, dùng để tìm kiếm tài liệu tuyển sinh HaUI.
Mỗi câu trên 1 dòng. Không đánh số. Không giải thích.
Query gốc: {query}"""
        result = call_llm(prompt)
        variants = [q.strip() for q in result.strip().split('\n') if q.strip()]
        return [query] + variants[:2]
    return [query]
```

---

## PHẦN 5: RETRIEVAL VÀ RERANKING

### 5.1 Pre-filter metadata

```python
def build_filter(query, intent, entities):
    filters = {}
    query_lower = query.lower()

    if intent == 'A1' and entities.get('ma_nganh'):
        filters['ma_nganh'] = entities['ma_nganh']

    if intent in ['A1', 'A2'] and entities.get('nhom_nganh'):
        filters['nhom_nganh'] = entities['nhom_nganh']

    if intent == 'B1':
        if any(kw in query_lower for kw in ['học phí', 'tín chỉ', 'tc', 'n_tchp', 'cách tính']):
            filters['loai__in'] = ['hoc_phi']
        else:
            filters['loai__in'] = ['diem_chuan', 'diem_uu_tien', 'diem_quy_doi']

    if intent == 'C':
        if any(kw in query_lower for kw in ['học phí', 'mức thu', 'đơn giá', 'tín chỉ', 'cách tính hp']):
            filters['loai__in'] = ['hoc_phi', 'huong_dan', 'chinh_sach']
        elif any(kw in query_lower for kw in ['ký túc xá', 'ktx', 'phòng ở']):
            filters['loai__in'] = ['ky_tuc_xa']
        elif any(kw in query_lower for kw in ['học bổng', 'hỗ trợ tài chính', 'miễn giảm']):
            filters['loai__in'] = ['hoc_bong']
        elif any(kw in query_lower for kw in ['lịch', 'thời gian', 'khi nào', 'deadline',
                                               'tuyển sinh 2026', 'chỉ tiêu 2026']):
            # FIX: thêm 'chi_tieu_tong' để retrieve chi_tieu_tuyen_sinh_2026.json
            filters['loai__in'] = ['lich_tuyen_sinh', 'chi_tieu_tong', 'huong_dan']
        elif any(kw in query_lower for kw in ['phương thức', 'xét tuyển thẳng', 'pt1', 'pt2', 'pt3', 'pt4', 'pt5']):
            filters['loai__in'] = ['huong_dan', 'faq', 'chinh_sach']
        elif any(kw in query_lower for kw in ['nhập học', 'hồ sơ', 'bước', 'đăng ký']):
            filters['loai__in'] = ['huong_dan', 'faq']
        else:
            filters['loai__in'] = ['huong_dan', 'faq', 'chinh_sach', 'hoc_phi',
                                   'ky_tuc_xa', 'hoc_bong', 'lich_tuyen_sinh', 'chi_tieu_tong']

    # FIX: Dùng 'nam_list__contains' thay vì 'nam_moi_nhat' ==
    # Lý do: chunk điểm chuẩn chứa nhiều năm → filter == bỏ sót chunk đa năm
    if entities.get('nam'):
        nam = int(entities['nam'])
        if nam <= 2025:
            filters['nam_list__contains'] = nam
        # Nam 2026: điểm chuẩn chưa có → không filter theo năm (retrieve 2025 làm tham chiếu)

    if entities.get('to_hop'):
        filters['to_hop__contains'] = entities['to_hop'][0]

    return filters
```

### 5.2 Hybrid search + RRF

```python
def hybrid_search(query_vec, query_text, filters, top_k=10):
    vector_results = vector_store.search(query_vec, top_k=top_k*2, filter=filters)
    
    tokens = underthesea.word_tokenize(query_text)
    bm25_scores = bm25.get_scores(tokens)
    bm25_top = sorted(
        [(i, s) for i, s in enumerate(bm25_scores) if s > 0],
        key=lambda x: -x[1]
    )[:top_k*2]
    bm25_top = [(i, s) for i, s in bm25_top if check_filter(chunks[i], filters)]
    
    rrf_scores = {}
    k = 60
    for rank, (doc_id, _) in enumerate([(r.id, r) for r in vector_results]):
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1/(k + rank + 1)
    for rank, (doc_idx, _) in enumerate(bm25_top):
        doc_id = chunks[doc_idx]['id']
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1/(k + rank + 1)
    
    merged = sorted(rrf_scores.items(), key=lambda x: -x[1])[:20]
    return [get_chunk(doc_id) for doc_id, _ in merged]
```

### 5.3 Reranker

```python
def rerank(query, candidates, top_k=5):
    response = requests.post(
        f"{RERANKER_URL}/rerank",
        json={'query': query, 'texts': [c['text'] for c in candidates]}
    )
    scores = response.json()['scores']
    ranked = sorted(zip(candidates, scores), key=lambda x: -x[1])[:top_k]
    return [c for c, s in ranked]
```

### 5.4 Top-k theo intent

```python
TOP_K_CONFIG = {
    'A1': {'vector': 5,  'bm25': 5,  'rerank_top': 3},
    'A2': {'vector': 15, 'bm25': 10, 'rerank_top': 8},
    'B1': {'vector': 8,  'bm25': 8,  'rerank_top': 5},
    'B2': {'vector': 15, 'bm25': 12, 'rerank_top': 8},
    'C':  {'vector': 8,  'bm25': 6,  'rerank_top': 5},  # FIX: tăng từ 6/5/4 (C cover nhiều loại hơn)
    'D':  {'vector': 10, 'bm25': 8,  'rerank_top': 6},
}
```

---

## PHẦN 6: SELF-REFLECT

```python
SELF_REFLECT_PROMPT = """Kiểm tra: các đoạn văn sau có đủ thông tin để trả lời câu hỏi không?

Câu hỏi: {query}

Đoạn văn retrieved:
{context_preview}

Trả lời ĐÚNG 1 trong:
SUFFICIENT - đủ thông tin
PARTIAL - có một phần, cần hỏi thêm người dùng
MISSING - thiếu hoàn toàn, cần chuyển sang fallback"""

def self_reflect(query, chunks):
    context_preview = '\n---\n'.join([c['text'][:300] for c in chunks[:3]])
    result = call_llm(SELF_REFLECT_PROMPT.format(
        query=query, 
        context_preview=context_preview
    ), max_tokens=10)
    
    if 'SUFFICIENT' in result:
        return 'ok', chunks
    elif 'PARTIAL' in result:
        return 'partial', chunks
    else:
        return 'missing', []
```

---

## PHẦN 7: ENTITY EXTRACTION

```python
ENTITY_PATTERNS = {
    'ma_nganh': r'\b7[0-9]{6}\b',
    'diem': r'\b([0-9]{1,2}(\.[0-9]{1,2})?)\s*(điểm|đ\b)',
    'to_hop': r'\b(A00|A01|B00|C02|D01|D04|D06|D07|D14|D15|DD2|X06|X07|X25|X27)\b',
    'khu_vuc': r'\b(KV1|KV2-NT|KV2|KV3)\b',
    'nam': r'\b(2023|2024|2025|2026)\b',
    'phuong_thuc': r'\b(PT[1-6])\b',
}

NGANH_ALIASES = {
    # CNTT
    'cntt': 'Công nghệ thông tin',
    'công nghệ thông tin': 'Công nghệ thông tin',
    'ktpm': 'Kỹ thuật phần mềm',
    'kỹ thuật phần mềm': 'Kỹ thuật phần mềm',
    'khmt': 'Khoa học máy tính',
    'khoa học máy tính': 'Khoa học máy tính',
    'httt': 'Hệ thống thông tin',
    'attt': 'An toàn thông tin',
    'an toàn thông tin': 'An toàn thông tin',
    'đa phương tiện': 'Công nghệ đa phương tiện',
    'mạng máy tính': 'Mạng máy tính và truyền thông dữ liệu',
    # Cơ khí / điện
    'cơ điện tử': 'Công nghệ kỹ thuật cơ điện tử',
    'cơ điện tử ô tô': 'Công nghệ kỹ thuật cơ điện tử ô tô',
    'robot': 'Robot và trí tuệ nhân tạo',
    'robot ai': 'Robot và trí tuệ nhân tạo',
    'tự động hóa': 'Công nghệ kỹ thuật điều khiển và tự động hóa',
    'tđh': 'Công nghệ kỹ thuật điều khiển và tự động hóa',
    'điện tử viễn thông': 'Công nghệ kỹ thuật điện tử - viễn thông',
    'điện điện tử': 'Công nghệ kỹ thuật điện, điện tử',
    'cơ khí': 'Công nghệ kỹ thuật cơ khí',
    'ô tô': 'Công nghệ kỹ thuật ô tô',
    'khuôn mẫu': 'Công nghệ kỹ thuật khuôn mẫu',
    'năng lượng tái tạo': 'Năng lượng tái tạo',
    'y sinh': 'Công nghệ kỹ thuật điện tử y sinh',
    'sản xuất thông minh': 'Kỹ thuật sản xuất thông minh',
    'kỹ thuật nhiệt': 'Công nghệ kỹ thuật nhiệt',        # FIX: thêm mới
    'cơ khí động lực': 'Kỹ thuật cơ khí động lực',       # FIX: thêm mới
    'hệ thống công nghiệp': 'Kỹ thuật hệ thống công nghiệp', # FIX: thêm mới
    # Kinh tế
    'kế toán': 'Kế toán',
    'kiểm toán': 'Kiểm toán',
    'marketing': 'Marketing',
    'logistics': 'Logistics và quản lý chuỗi cung ứng',
    'quản trị kinh doanh': 'Quản trị kinh doanh',
    'qtkt': 'Quản trị kinh doanh',
    'tài chính ngân hàng': 'Tài chính – Ngân hàng',
    'nhân lực': 'Quản trị nhân lực',
    'phân tích dữ liệu': 'Phân tích dữ liệu kinh doanh',
    'kinh tế đầu tư': 'Kinh tế đầu tư',                  # FIX: thêm mới
    'quản trị văn phòng': 'Quản trị văn phòng',           # FIX: thêm mới
    # Ngôn ngữ / Du lịch
    'tiếng anh': 'Ngôn ngữ Anh',
    'ngôn ngữ anh': 'Ngôn ngữ Anh',
    'tiếng trung': 'Ngôn ngữ Trung Quốc',
    'ngôn ngữ trung': 'Ngôn ngữ Trung Quốc',
    'tiếng nhật': 'Ngôn ngữ Nhật',
    'tiếng hàn': 'Ngôn ngữ Hàn Quốc',
    'ngôn ngữ học': 'Ngôn ngữ học',                       # FIX: thêm mới
    'trung quốc học': 'Trung Quốc học',                   # FIX: thêm mới
    'du lịch': 'Du lịch',
    'khách sạn': 'Quản trị khách sạn',
    'nhà hàng': 'Quản trị nhà hàng và dịch vụ ăn uống',
    'lữ hành': 'Quản trị dịch vụ du lịch và lữ hành',
    # Hoá / Thực phẩm / Dệt may
    'hoá học': 'Công nghệ kỹ thuật hóa học',
    'hóa học': 'Công nghệ kỹ thuật hóa học',
    'môi trường': 'Công nghệ kỹ thuật môi trường',        # FIX: thêm mới
    'thực phẩm': 'Công nghệ thực phẩm',
    'hóa dược': 'Hóa dược',
    'dệt may': 'Công nghệ dệt, may',
    'vật liệu dệt': 'Công nghệ vật liệu dệt, may',        # FIX: thêm mới
    'thời trang': 'Thiết kế thời trang',
}

# Ánh xạ từ khoá → nhóm ngành (dùng cho A2 filter)
NHOM_KEYWORDS = {
    'cntt': 'CNTT',
    'công nghệ thông tin': 'CNTT',
    'it': 'CNTT',
    'lập trình': 'CNTT',
    'phần mềm': 'CNTT',
    'cơ khí': 'Cơ khí',
    'ô tô': 'Cơ khí',
    'điện': 'Cơ khí',
    'robot': 'Cơ khí',
    'tự động hóa': 'Cơ khí',
    'cơ điện tử': 'Cơ khí',
    'kinh tế': 'Kinh tế',
    'kế toán': 'Kinh tế',
    'tài chính': 'Kinh tế',
    'marketing': 'Kinh tế',
    'logistics': 'Kinh tế',
    'ngôn ngữ': 'Ngôn ngữ',
    'tiếng': 'Ngôn ngữ',
    'trung quốc': 'Ngôn ngữ',
    'du lịch': 'Du lịch',
    'khách sạn': 'Du lịch',
    'nhà hàng': 'Du lịch',
    'thực phẩm': 'Thực phẩm',
    'hóa dược': 'Thực phẩm',
    'hóa học': 'Thực phẩm',
    'dệt may': 'Dệt may',
    'thời trang': 'Dệt may',
}

def extract_entities(query):
    entities = {}
    query_norm = query.lower()

    for key, pattern in ENTITY_PATTERNS.items():
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            entities[key] = match.group(0)

    for alias, full_name in NGANH_ALIASES.items():
        if alias in query_norm:
            entities['ten_nganh'] = full_name
            break

    for kw, nhom in NHOM_KEYWORDS.items():
        if kw in query_norm:
            entities['nhom_nganh'] = nhom
            break

    return entities
```

---

## PHẦN 8: TỔNG HỢP PIPELINE

```python
async def handle_query(user_query):
    # 1. Fast route
    intent = fast_route(user_query)
    
    # 2. LLM route (nếu fast route không match)
    if intent is None:
        intent = await llm_route(user_query)
    
    # 3. Short-circuit cho intent E, F
    if intent == 'E':
        return generate_smalltalk(user_query)
    if intent == 'F':
        return FALLBACK_MESSAGE
    
    # 4. Entity extraction
    entities = extract_entities(user_query)
    
    # 5. Query rewrite (tự động thêm ngữ cảnh năm phù hợp — mặc định 2026)
    clean_query = await rewrite_query(user_query)
    
    # 6. Multi-query expansion (A2, B2)
    queries = expand_query(clean_query, intent)
    
    # 7. HyDE
    hyde_doc = await generate_hyde(clean_query, intent)
    hyde_vec = embed_query(hyde_doc)
    query_vec = embed_query(clean_query)
    final_vec = 0.7 * query_vec + 0.3 * hyde_vec
    
    # 8. Build pre-filter
    filters = build_filter(clean_query, intent, entities)
    
    # 9. Hybrid search
    cfg = TOP_K_CONFIG[intent]
    candidates = hybrid_search(
        final_vec, clean_query, filters,
        top_k=max(cfg['vector'], cfg['bm25'])
    )
    
    # 10. Rerank
    top_docs = rerank(clean_query, candidates, top_k=cfg['rerank_top'])
    
    # 11. Self-reflect
    status, docs = self_reflect(clean_query, top_docs)
    
    if status == 'missing':
        return CONTEXT_MISSING_MESSAGE
    
    # 12. Build context string
    context = '\n\n---\n\n'.join([d['text'] for d in docs])
    
    # 13. Generate
    response = await generate(
        system_prompt=SYSTEM_PROMPT.format(context=context),
        query=user_query,
        intent=intent
    )
    
    return response
```

---

## PHẦN 9: CHECKLIST KIỂM TRA CHẤT LƯỢNG

Trước khi deploy, kiểm tra các test case sau:

### Nhóm điểm chuẩn
- [ ] "Điểm chuẩn CNTT 2025" → trả về 23.09, ghi rõ "điểm chuẩn chung PT2+PT3+PT5"
- [ ] "Điểm chuẩn CNTT 2024 PT3" → trả về 25.22, ghi rõ "riêng PT3 năm 2024"
- [ ] "Tất cả ngành CNTT điểm chuẩn" → bảng đầy đủ tất cả ngành CNTT (route A2)
- [ ] "Điểm chuẩn các ngành kinh tế" → bảng đủ 10+ ngành kinh tế (route A2)
- [ ] "Điểm chuẩn 2026" → cảnh báo chưa công bố, tham khảo 2025

### Nhóm tính toán
- [ ] Tổng 22.0, KV1 → cộng thẳng 22.0 + 0.75 = 22.75 (không dùng giảm dần vì 22.0 < 22.5)
- [ ] Tổng 24.0, KV2-NT → giảm dần [(30-24)/7.5]×0.5 = 0.40, kết quả 24.40
- [ ] HSA 95 → quy đổi 23.50, sau đó tính ưu tiên
- [ ] HSA 93 → quy đổi đúng 23.01 (không nội suy, tra bảng đầy đủ)
- [ ] HSA 91 → quy đổi đúng 22.75 (không nội suy)
- [ ] PT2 với IELTS 6.0 → ĐQĐCC = 9.5
- [ ] "Tính học phí 3 tín chỉ K20 đại trà" → route B1, HP = 3×1.5×700.000 = 3.150.000 đ

### Nhóm tổ hợp
- [ ] "Ngành nào thi Toán Lý Anh" → liệt kê tất cả ngành có tổ hợp A01
- [ ] "Học Ngôn ngữ Hàn cần thi gì" → D01 và DD2

### Nhóm thủ tục
- [ ] "Đăng ký PT5" → đúng 6 bước
- [ ] "Hồ sơ nhập học" → đầy đủ theo file huong_dan_nhap_hoc
- [ ] "Lịch tuyển sinh 2026" → route C, trả về bảng lịch (không fallback)
- [ ] "Phương thức xét tuyển HaUI" → đủ 5 phương thức
- [ ] "Chỉ tiêu 2026" → route C, trả về tổng chỉ tiêu từ chi_tieu_tuyen_sinh_2026.json (8.300 + 750 + 250 + 120 = 9.420)

### Nhóm học phí / KTX / học bổng
- [ ] "Học phí ngành CNTT K20" → 700.000 đ/TC (đại trà), 1.000.000 (tiếng Anh)
- [ ] "Học phí 3 tín chỉ K20" → HP = 3×1.5×700.000 = 3.150.000 đ (route B1)
- [ ] "Cách tính học phí" → retrieve chunk cach_tinh_hoc_phi, trả về công thức HP = N_TCHP × H_LHP × ĐG
- [ ] "Ký túc xá giá bao nhiêu" → bảng đầy đủ 6 loại phòng + 2 cơ sở
- [ ] "Điều kiện học bổng KKHT" → TBC ≥ 2.5, rèn luyện Tốt, ≥ 15 TC
- [ ] "Học bổng Nguyễn Thanh Bình" → đủ 7 đối tượng, mức 100-150%

### Nhóm edge case
- [ ] Thiếu tổ hợp → hỏi lại (không hỏi 2 câu cùng lúc)
- [ ] Hỏi về điểm chuẩn 2026 → cảnh báo chưa công bố, dùng 2025 tham chiếu
- [ ] Tổng điểm > 30 → phát hiện lỗi input
- [ ] "Học bổng trường ABC" → từ chối lịch sự (intent F)
- [ ] "Ngành hóa học HaUI" → retrieve đúng cong_nghe_ky_thuat_hoa_hoc.md (không bị bỏ sót)
- [ ] "Ngành môi trường HaUI" → retrieve đúng cong_nghe_ky_thuat_moi_truong.md

---