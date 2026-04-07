"""
chunking.py — All chunking functions following the technical guide v2.2
Transforms raw JSON/Markdown data into self-contained chunks with metadata.
"""
import os
import re
import json
from collections import defaultdict


# ═══════════════════════════════════════════════════════════
#  1. CHUNKING JSON — điểm chuẩn (nhóm theo ngành)
# ═══════════════════════════════════════════════════════════

def chunk_diem_chuan(records):
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
            if year == 2025:
                r = year_recs[0]
                pt_list = ', '.join(r.get('cac_phuong_thuc_ap_dung', []))
                lines.append(f"Năm {year} (điểm chuẩn chung): {r['diem_chuan']} điểm (thang {r['thang_diem']})")
                if pt_list:
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


# ═══════════════════════════════════════════════════════════
#  2. CHUNKING JSON — chỉ tiêu và tổ hợp
# ═══════════════════════════════════════════════════════════

def chunk_chi_tieu_to_hop(records, to_hop_map):
    chunks = []
    for r in records:
        to_hop_expanded = []
        for code in r.get('to_hop', []):
            mon = to_hop_map.get(code, [])
            to_hop_expanded.append(f"{code} ({'-'.join(mon)})")

        text = f"""# Chỉ tiêu & tổ hợp: {r['ten_nganh']} (mã {r['ma_nganh']})
Nhóm ngành: {r.get('nhom', '')}
Chỉ tiêu 2025: {r['chi_tieu']} sinh viên
Tổ hợp xét tuyển: {', '.join(to_hop_expanded)}
Phương thức: {', '.join(r.get('phuong_thuc', []))}
"""
        chunks.append({
            'text': text,
            'metadata': {
                'source': 'chi_tieu',
                'loai': 'chi_tieu_to_hop',
                'ma_nganh': r['ma_nganh'],
                'ten_nganh': r['ten_nganh'],
                'nhom_nganh': r.get('nhom', ''),
                'to_hop': r.get('to_hop', []),
                'phuong_thuc': r.get('phuong_thuc', []),
                'chi_tieu': r['chi_tieu'],
                'nam': 2025
            }
        })
    return chunks


# ═══════════════════════════════════════════════════════════
#  3. CHUNKING JSON — chỉ tiêu 2026
# ═══════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════
#  4. CHUNKING JSON — điểm ưu tiên và quy đổi
# ═══════════════════════════════════════════════════════════

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
        {'text': kv_text, 'metadata': {'loai': 'diem_uu_tien', 'loai_con': 'khu_vuc', 'nam': 2026, 'source': 'diem_uu_tien'}},
        {'text': dt_text, 'metadata': {'loai': 'diem_uu_tien', 'loai_con': 'doi_tuong', 'nam': 2026, 'source': 'diem_uu_tien'}}
    ]


def chunk_diem_quy_doi(data):
    chunks = []
    for key in ['quy_doi_HSA', 'quy_doi_TSA', 'quy_doi_KQHB']:
        qd = data[key]
        bang = qd['bang']

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
                'ki_thi': qd['ki_thi'],
                'source': 'diem_quy_doi'
            }
        })
    return chunks


# ═══════════════════════════════════════════════════════════
#  5. CHUNKING Markdown — ngành học
# ═══════════════════════════════════════════════════════════

def chunk_nganh_md(filepath, content):
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


NGANH_EXTRA_FILES = [
    'cong_nghe_ky_thuat_hoa_hoc.md',
    'cong_nghe_ky_thuat_moi_truong.md',
    'cong_nghe_thuc_pham.md',
    'hoa_duoc.md',
    'cong_nghe_det_may.md',
    'cong_nghe_vat_lieu_det_may.md',
    'thiet_ke_thoi_trang.md',
]


# ═══════════════════════════════════════════════════════════
#  6. CHUNKING Markdown — FAQ & hướng dẫn
# ═══════════════════════════════════════════════════════════

def chunk_faq_md(content, source_name='faq'):
    chunks = []
    qa_pattern = re.findall(r'\*\*Q:(.*?)\*\*(.*?)(?=\n---|\Z)', content, re.DOTALL)
    for q, a in qa_pattern:
        text = f"Câu hỏi: {q.strip()}\nTrả lời: {a.strip()}"
        chunks.append({
            'text': text,
            'metadata': {'loai': 'faq', 'source': source_name}
        })
    return chunks


def chunk_huong_dan_md(content, source_name):
    sections = re.split(r'\n### ', content)
    chunks = []
    for section in sections[1:]:
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


# ═══════════════════════════════════════════════════════════
#  7. CHUNKING JSON — học phí
# ═══════════════════════════════════════════════════════════

def chunk_hoc_phi(data):
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


# ═══════════════════════════════════════════════════════════
#  8. CHUNKING Markdown — chính sách (chunk theo ##)
# ═══════════════════════════════════════════════════════════

def chunk_policy_md(content, source_name, loai='chinh_sach'):
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


def chunk_cach_tinh_hoc_phi(content, source_name='cach_tinh_hoc_phi'):
    return chunk_policy_md(content, source_name, loai='hoc_phi')


# ═══════════════════════════════════════════════════════════
#  9. CHUNKING đặc biệt — học bổng
# ═══════════════════════════════════════════════════════════

def chunk_hoc_bong(content):
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


# ═══════════════════════════════════════════════════════════
#  FILE → LOAI MAP
# ═══════════════════════════════════════════════════════════

POLICY_FILE_MAP = {
    'ky_tuc_xa.md':                    'ky_tuc_xa',
    'hoc_bong.md':                     'hoc_bong',
    'gioi_thieu_truong.md':            'gioi_thieu',
    'quy_mo_dao_tao.md':               'gioi_thieu',
    'lich_tuyen_sinh_2026.md':         'lich_tuyen_sinh',
    'chinh_sach_uu_tien.md':           'diem_uu_tien',
    'van_bang.md':                     'chinh_sach',
    'phuong_thuc_tuyen_sinh_2025.md':  'huong_dan',
    'cach_tinh_hoc_phi_2025_2026.md':  'hoc_phi',
}


# ═══════════════════════════════════════════════════════════
#  10. DISPATCHER — chunk tất cả file
# ═══════════════════════════════════════════════════════════

def chunk_all_files(project_dir):
    """
    Dispatch đúng function chunking cho từng file trong project.
    Trả về list tất cả chunks (có metadata đầy đủ).
    """
    all_chunks = []
    nganh_base = os.path.join(project_dir, 'nganh')

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

    # --- Markdown ngành (scan all nganh subdirs) ---
    if os.path.exists(nganh_base):
        for root, dirs, files in os.walk(nganh_base):
            for fname in files:
                if fname.endswith('.md'):
                    fpath = os.path.join(root, fname)
                    with open(fpath, encoding='utf-8') as f:
                        content = f.read()
                    all_chunks.extend(chunk_nganh_md(fname, content))

    # --- FAQ & Hướng dẫn ---
    for fname in os.listdir(project_dir):
        fpath = os.path.join(project_dir, fname)
        if not fname.endswith('.md') or not os.path.isfile(fpath):
            continue
        with open(fpath, encoding='utf-8') as f:
            content = f.read()
        if fname.startswith('faq_'):
            all_chunks.extend(chunk_faq_md(content, fname.replace('.md', '')))
        elif fname.startswith('huong_dan_'):
            all_chunks.extend(chunk_huong_dan_md(content, fname.replace('.md', '')))

    # --- Học bổng (chunking đặc biệt) ---
    hb_path = os.path.join(project_dir, 'hoc_bong.md')
    if os.path.exists(hb_path):
        with open(hb_path, encoding='utf-8') as f:
            all_chunks.extend(chunk_hoc_bong(f.read()))

    # --- Cách tính học phí ---
    cach_tinh_path = os.path.join(project_dir, 'cach_tinh_hoc_phi_2025_2026.md')
    if os.path.exists(cach_tinh_path):
        with open(cach_tinh_path, encoding='utf-8') as f:
            all_chunks.extend(chunk_cach_tinh_hoc_phi(f.read()))

    # --- File chính sách / giới thiệu ---
    for fname, loai in POLICY_FILE_MAP.items():
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
