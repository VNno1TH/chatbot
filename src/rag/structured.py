"""
Structured lookups & deterministic scoring from official HaUI JSON sources.
Used to ground RAG answers and short-circuit B1 when parsing succeeds.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache

from src.config import DATA_DIR
_BASE = DATA_DIR
_DIEM_CHUAN_PATH = os.path.join(_BASE, 'diem_chuan_2023_2024_2025.json')
_DIEM_QUY_DOI_PATH = os.path.join(_BASE, 'diem_quy_doi.json')
_CHI_TIEU_TO_HOP_PATH = os.path.join(_BASE, 'chi_tieu_to_hop_2025.json')

KV_SCORE = {'kv1': 0.75, 'kv2-nt': 0.50, 'kv2nt': 0.50, 'kv2': 0.25, 'kv3': 0.00}
# UT1: ĐT01–03 (+2.0), UT2: ĐT04–06 (+1.0)
UT1_SET = {1, 2, 3}
UT2_SET = {4, 5, 6}


@lru_cache(maxsize=1)
def _load_diem_chuan():
    if not os.path.exists(_DIEM_CHUAN_PATH):
        return []
    with open(_DIEM_CHUAN_PATH, encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_quy_doi():
    if not os.path.exists(_DIEM_QUY_DOI_PATH):
        return {}
    with open(_DIEM_QUY_DOI_PATH, encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_chi_tieu_to_hop():
    if not os.path.exists(_CHI_TIEU_TO_HOP_PATH):
        return []
    with open(_CHI_TIEU_TO_HOP_PATH, encoding='utf-8') as f:
        return json.load(f)


def lookup_hsa(score: int):
    data = _load_quy_doi().get('quy_doi_HSA', {})
    for row in data.get('bang', []):
        if row['tu'] <= score <= row['den']:
            return row['diem_quy_doi']
    return None


def lookup_tsa(score: float):
    data = _load_quy_doi().get('quy_doi_TSA', {})
    for row in data.get('bang', []):
        if row['tu'] <= score <= row['den']:
            return row['diem_quy_doi']
    return None


def lookup_kqhb(avg: float):
    data = _load_quy_doi().get('quy_doi_KQHB', {})
    for row in data.get('bang', []):
        if row['tu'] <= avg <= row['den']:
            return row['diem_quy_doi']
    return None


def _parse_kv(text: str):
    t = text.lower().replace(' ', '')
    if 'kv2-nt' in text.lower() or 'kv2nt' in t:
        return 'kv2-nt', KV_SCORE['kv2-nt']
    m = re.search(r'\b(kv[123]|kv2-nt)\b', text.lower())
    if not m:
        return None, 0.0
    k = m.group(1).replace(' ', '')
    if k == 'kv2-nt':
        return k, KV_SCORE['kv2-nt']
    return k, KV_SCORE.get(k, 0.0)


def _parse_dt(text: str):
    tl = text.lower()
    m = re.search(r'đt\s*(\d{1,2})\b|đối\s*tượng\s*(\d{1,2})\b|dt\s*(\d{1,2})\b', tl)
    if not m:
        return 0.0
    d = int(next(g for g in m.groups() if g))
    if d in UT1_SET:
        return 2.0
    if d in UT2_SET:
        return 1.0
    return 0.0


def compute_pt3_admission(total: float, kv_bonus: float, dt_bonus: float):
    uu = kv_bonus + dt_bonus
    lines = [
        f"Tổng điểm 3 môn (thang 30): **{total:.2f}**",
        f"Ưu tiên khu vực + đối tượng (cộng dồn): **+{uu:.2f}**",
    ]
    if total > 30:
        return None, "⚠️ Tổng điểm vượt quá 30 (thang 30). Vui lòng kiểm tra lại."
    if total < 22.5:
        dxt = round(total + uu, 2)
        lines.append(f"Vì {total:.2f} < 22.5 → cộng thẳng ưu tiên: **ĐXT = {total:.2f} + {uu:.2f} = {dxt:.2f}**")
        return dxt, '\n'.join(lines)
    ddt = (30 - total) / 7.5 * uu
    dxt = round(total + ddt, 2)
    lines.append(f"Vì {total:.2f} ≥ 22.5 → công thức giảm dần:")
    lines.append(f"ĐĐT = [(30 − {total:.2f}) / 7.5] × {uu:.2f} = **{ddt:.2f}**")
    lines.append(f"**ĐXT = {total:.2f} + {ddt:.2f} = {dxt:.2f}**")
    return dxt, '\n'.join(lines)


def _ielts_to_dqdcc(score: float) -> float | None:
    if score >= 6.5:
        return 10.0
    if score >= 6.0:
        return 9.5
    if score >= 5.5:
        return 9.0
    return None


def try_deterministic_b1_answer(query: str) -> str | None:
    """Return a complete Vietnamese answer or None."""
    q = query.strip()
    ql = q.lower()

    # --- HSA (chỉ quy đổi đơn, không chạy khi đã kết hợp KV + CNTT ở mục sau) ---
    m_hsa_only = re.search(r'hsa\s*(\d{2,3})\b', ql)
    if m_hsa_only and ('quy đổi' in ql or 'bao nhiêu' in ql) and 'cntt' not in ql and 'kv' not in ql:
        s = int(m_hsa_only.group(1))
        v = lookup_hsa(s)
        if v is not None:
            return (
                f"Theo bảng quy đổi ĐQĐNL (HSA) của HaUI, điểm HSA **{s}** quy đổi thang 30 là **{v:.2f}** điểm "
                f"(tra bảng chính thức, không nội suy). Anh/chị cần em tính thêm ưu tiên KV/ĐT không ạ?"
            )

    # --- TSA ---
    m = re.search(r'tsa\s*(\d+(?:\.\d+)?)', ql)
    if m and ('quy đổi' in ql or 'bao nhiêu' in ql):
        s = float(m.group(1))
        v = lookup_tsa(s)
        if v is not None:
            return (
                f"Theo bảng quy đổi ĐGTD (TSA) ĐHBK Hà Nội dùng tại HaUI, điểm TSA **{s}** quy đổi thang 30 là **{v:.2f}** điểm. "
                f"Cần thêm thông tin gì nữa ạ?"
            )

    # --- KQHB Toán ---
    m = re.search(
        r'môn\s*toán[^\d]{0,10}(\d+(?:\.\d+)?)|trung\s*bình\s*môn\s*toán[^\d]{0,10}(\d+(?:\.\d+)?)|toán\s*(\d+(?:\.\d+)?)',
        ql,
    )
    if m and 'quy đổi' in ql and 'học bạ' in ql:
        avg = float(next(g for g in m.groups() if g))
        v = lookup_kqhb(avg)
        if v is not None:
            return (
                f"Điểm trung bình cả năm môn Toán **{avg}** (thang 10) quy đổi theo bảng ĐKQHT của HaUI là **{v:.2f}** điểm (thang 10). "
                f"Anh/chị cần tra thêm môn khác không ạ?"
            )

    # --- Học phí học phần ---
    m_tc = re.search(r'(\d+)\s*tín\s*chỉ', ql)
    if m_tc and 'học phí' in ql:
        n = int(m_tc.group(1))
        if 'tiếng anh' in ql or 'k20 ta' in ql or ('k20' in ql and 'tiếng' in ql):
            dg = 1_000_000
        else:
            dg = 700_000
        if 'thực hành chuyên sâu' in ql or 'chuyên sâu' in ql:
            coef = 2.5
        elif 'lý thuyết' in ql:
            coef = 1.5
        elif 'thể chất' in ql or 'quốc phòng' in ql:
            coef = 1.0
        else:
            coef = 1.5
        nt = n * coef
        hp = int(nt * dg)
        return (
            f"Áp dụng công thức **HP = N_TCHP × H_LHP × ĐG** (năm học 2025–2026):\n"
            f"- Số tín chỉ: {n}\n"
            f"- Hệ số nhóm học phần: ×{coef}\n"
            f"- N_TCHP = {n} × {coef} = **{nt}**\n"
            f"- Đơn giá K20 ({'chương trình Tiếng Anh' if dg == 1_000_000 else 'đại trà'}): **{dg:,}** đ/tín chỉ\n"
            f"→ **HP = {hp:,} đồng**.\n"
            f"Anh/chị cần tính thêm học phần khác không ạ?"
        )

    # --- PT2 ---
    if 'pt2' in ql or 'phương thức 2' in ql:
        tb_t = re.search(r'tb\s*toán\s*(\d+(?:\.\d+)?)', ql)
        tb_l = re.search(r'tb\s*lý\s*(\d+(?:\.\d+)?)', ql)
        tb_a = re.search(r'tb\s*anh\s*(\d+(?:\.\d+)?)', ql)
        if tb_t and tb_l and tb_a:
            t, l, a = float(tb_t.group(1)), float(tb_l.group(1)), float(tb_a.group(1))
            dkqht = round((t + l + a) / 3, 3)
            prize = re.search(r'giải\s*(nhất|nhì|ba)\s*hsg', ql)
            if prize:
                g = prize.group(1)
                dqdcc2 = {'nhất': 10.0, 'nhì': 9.5, 'ba': 9.0}[g]
                dxt = round(dkqht * 2 + dqdcc2, 2)
                return (
                    f"📊 **Tính điểm xét tuyển PT2 (HaUI):**\n"
                    f"- ĐKQHT = (TB Toán + TB Lý + TB Anh) / 3 = ({t}+{l}+{a})/3 = **{dkqht}**\n"
                    f"- Giải {g.capitalize()} HSG môn Toán cấp tỉnh → ĐQĐCC = **{dqdcc2:.2f}**\n"
                    f"- **ĐXT = {dkqht} × 2 + {dqdcc2:.2f} = {dxt:.2f}** điểm.\n"
                    f"Anh/chị muốn so sánh với điểm chuẩn ngành nào ạ?"
                )
            ielts_m = re.search(r'ielts\s*(\d+(?:\.\d+)?)', ql)
            if ielts_m:
                ielts = float(ielts_m.group(1))
                dqdcc = _ielts_to_dqdcc(ielts)
                if dqdcc is None:
                    return None
                dxt = round(dkqht * 2 + dqdcc, 2)
                return (
                    f"📊 **Tính điểm xét tuyển PT2 (HaUI):**\n"
                    f"- ĐKQHT = ({t}+{l}+{a})/3 = **{dkqht}**\n"
                    f"- IELTS {ielts} → ĐQĐCC = **{dqdcc:.2f}**\n"
                    f"- **ĐXT = {dkqht} × 2 + {dqdcc:.2f} = {dxt:.2f}** điểm.\n"
                    f"Anh/chị cần tính thêm ưu tiên hoặc so với điểm chuẩn không ạ?"
                )

    # --- PT3: điểm từng môn ---
    subj = re.findall(
        r'(toán|lý|hóa|anh|văn)\s*(\d+(?:\.\d+)?)',
        ql.replace('tiếng anh', 'anh'),
        re.IGNORECASE,
    )
    if len(subj) >= 3 and ('tính' in ql or 'xét tuyển' in ql):
        mp = {'toán': None, 'lý': None, 'hóa': None, 'anh': None, 'văn': None}
        for name, val in subj:
            k = name.lower()
            if k in mp:
                mp[k] = float(val)
        if mp['toán'] is not None and mp['lý'] is not None and mp.get('anh') is not None:
            total = mp['toán'] + mp['lý'] + mp['anh']
            _, kv_b = _parse_kv(q)
            dt_b = _parse_dt(q)
            dxt, body = compute_pt3_admission(total, kv_b, dt_b)
            if dxt is None:
                return body
            return f"📊 **Tính điểm xét tuyển PT3:**\n{body}\n→ **Điểm xét tuyển ≈ {dxt:.2f}**.\nAnh/chị muốn đối chiếu với điểm chuẩn ngành nào ạ?"

    # --- PT3: chỉ có tổng ---
    m_tot = re.search(r'tổng\s*(\d+(?:\.\d+)?)\s*điểm', ql)
    if not m_tot:
        m_tot = re.search(r'^tổng\s+(\d+(?:\.\d+)?)\b', ql)
    if m_tot and ('kv' in ql or 'đt' in ql or 'đối tượng' in ql) and ('tính' in ql or 'xét' in ql):
        total = float(m_tot.group(1))
        _, kv_b = _parse_kv(q)
        dt_b = _parse_dt(q)
        dxt, body = compute_pt3_admission(total, kv_b, dt_b)
        if dxt is None:
            return body
        extra = ""
        if 'cơ điện tử' in ql or 'co dien tu' in ql:
            dc = None
            for row in _load_diem_chuan():
                if row.get('ma_nganh') == '7510203' and row.get('nam') == 2025 and row.get('phuong_thuc_code') == 'chung':
                    dc = row.get('diem_chuan')
                    break
            if dc is not None:
                if dxt >= dc:
                    extra = f"\nĐiểm chuẩn **Cơ điện tử** (7510203) 2025 = **{dc}** → **ĐXT {dxt:.2f} ≥ {dc}** (vừa đủ / đủ tham khảo năm 2025)."
                else:
                    extra = f"\nĐiểm chuẩn Cơ điện tử 2025 = **{dc}** → chưa đủ so với ĐXT {dxt:.2f}."
        return f"📊 **Tính điểm xét tuyển PT3:**\n{body}\n→ **ĐXT ≈ {dxt:.2f}**.{extra}\nAnh/chị cần so sánh thêm ngành khác không ạ?"

    # --- HSA + KV + đỗ CNTT ---
    m_h = re.search(r'hsa\s*(\d{2,3})', ql)
    if m_h and 'kv' in ql and 'cntt' in ql:
        h = int(m_h.group(1))
        base = lookup_hsa(h)
        if base is None:
            return None
        _, kv_b = _parse_kv(q)
        dt_b = _parse_dt(q)
        dxt, body = compute_pt3_admission(base, kv_b, dt_b)
        if dxt is None:
            return body
        dc = None
        for row in _load_diem_chuan():
            if row.get('ma_nganh') == '7480201' and row.get('nam') == 2025:
                dc = row.get('diem_chuan')
                break
        extra = ""
        if dc is not None:
            extra = f"\nĐiểm chuẩn ngành CNTT (7480201) **2025** = **{dc}**. Với ĐXT **{dxt:.2f}** → **{'đủ điều kiện trúng tuyển tham khảo' if dxt >= dc else 'chưa đủ so với điểm chuẩn 2025'}** (điểm 2026 chưa công bố)."
        return f"📊 **Quy đổi & tính ĐXT (tham khảo PT3 + ưu tiên):**\n- HSA {h} → thang 30: **{base}**\n{body}\n→ **ĐXT ≈ {dxt:.2f}**.{extra}\nAnh/chị cần tư vấn thêm ngành khác không ạ?"

    return None


def format_diem_chuan_snippet(ma_nganh: str, nam: int, pt: str | None) -> str:
    all_rows = [r for r in _load_diem_chuan() if r.get('ma_nganh') == ma_nganh and r.get('nam') == nam]
    if not all_rows:
        return ""
    chung = [r for r in all_rows if r.get('phuong_thuc_code') == 'chung']
    if chung:
        rows = chung
    elif pt:
        rows = [r for r in all_rows if r.get('phuong_thuc_code') == pt] or all_rows
    else:
        rows = all_rows
    lines = [f"[DỮ LIỆU CHÍNH THỨC — điểm chuẩn JSON năm {nam}]"]
    for r in rows[:8]:
        pt_code = r.get('phuong_thuc_code')
        lines.append(
            f"- {r.get('ten_nganh')} (mã {r.get('ma_nganh')}), PT {pt_code}: **{r.get('diem_chuan')}** ({r.get('thang_diem')} thang)"
        )
    return '\n'.join(lines)


def format_nhom_diem_chuan_2025(nhom: str) -> str:
    rows = [
        r for r in _load_diem_chuan()
        if r.get('nam') == 2025 and r.get('nhom_nganh') == nhom
        and r.get('phuong_thuc_code') == 'chung'
    ]
    if not rows:
        return ""
    rows.sort(key=lambda x: (-(x.get('diem_chuan') or 0), x.get('ten_nganh', '')))
    lines = [f"[BẢNG ĐIỂM CHUẨN 2025 — nhóm {nhom} — từ dữ liệu HaUI]", "| Ngành | Mã | ĐC 2025 |", "|---|---:|---:|"]
    for r in rows:
        lines.append(f"| {r.get('ten_nganh')} | {r.get('ma_nganh')} | {r.get('diem_chuan')} |")
    return '\n'.join(lines)


def format_majors_with_tohop(code: str) -> str:
    code = code.upper()
    data = _load_chi_tieu_to_hop()
    picked = [r for r in data if code in (r.get('to_hop') or []) and r.get('nam') == 2025]
    if not picked:
        return ""
    lines = [f"[NGÀNH XÉT TUYỂN TỔ HỢP {code} — năm 2025]", "| Ngành | Mã | Chỉ tiêu |", "|---|---:|---:|"]
    for r in sorted(picked, key=lambda x: x.get('ten_nganh', '')):
        lines.append(f"| {r.get('ten_nganh')} | {r.get('ma_nganh')} | {r.get('chi_tieu')} |")
    return '\n'.join(lines)


def _chi_tieu_row_by_ma(ma: str):
    for r in _load_chi_tieu_to_hop():
        if r.get('nam') == 2025 and str(r.get('ma_nganh')) == str(ma):
            return r
    return None


def resolve_ma_chi_tieu(query: str) -> str | None:
    """Xác định mã ngành khi hỏi chỉ tiêu (tránh nhầm Cơ điện tử 7510203 vs Điện điện tử 7510301)."""
    ql = re.sub(r'\s+', ' ', query.lower()).strip()
    if not re.search(r'chỉ\s*tiêu|chi\s*tieu', ql):
        return None
    rows = [r for r in _load_chi_tieu_to_hop() if r.get('nam') == 2025]
    rows.sort(key=lambda r: -len(r.get('ten_nganh') or ''))
    qflat = ql.replace(',', '')
    for r in rows:
        tn = (r.get('ten_nganh') or '').lower()
        if len(tn) < 6:
            continue
        if tn in ql or tn.replace(',', '') in qflat:
            return r.get('ma_nganh')
    if re.search(r'cơ\s*điện\s*tử', ql) and re.search(r'ô\s*tô|o\s*to', ql):
        return '75102033'
    if re.search(r'cơ\s*điện\s*tử|co\s*dien\s*tu', ql):
        return '7510203'
    if (re.search(r'điện\s*điện\s*tử|điện,\s*điện\s*tử', ql) or 'dien dien tu' in ql) and not re.search(r'cơ\s*điện', ql):
        return '7510301'
    if 'cntt' in ql and 'đa phương tiện' not in ql:
        return '7480201'
    if 'logistics' in ql or 'chuỗi cung ứng' in ql:
        return '7510605'
    return None


def format_chi_tieu_snippet(ma: str) -> str:
    r = _chi_tieu_row_by_ma(ma)
    if not r:
        return ""
    return (
        f"[CHỈ TIÊU 2025 — chi_tieu_to_hop_2025.json]\n"
        f"- **{r.get('ten_nganh')}** (mã **{r.get('ma_nganh')}**): chỉ tiêu **{r.get('chi_tieu')}** sinh viên.\n"
        f"- Không nhầm với ngành khác cùng từ khóa \"điện tử\" (ví dụ Điện–Điện tử 7510301 có chỉ tiêu khác)."
    )


def try_deterministic_kb_answer(query: str) -> str | None:
    """Câu hỏi tra cứu ngắn: chỉ tiêu, IELTS PT2, tỷ lệ việc làm — trả lời khớp dữ liệu nguồn."""
    ql = query.lower()

    ma_ct = resolve_ma_chi_tieu(query)
    if ma_ct:
        r = _chi_tieu_row_by_ma(ma_ct)
        if r:
            return (
                f"Ngành **{r.get('ten_nganh')}** (mã **{r.get('ma_nganh')}**) năm **2025** có chỉ tiêu **{r.get('chi_tieu')}** sinh viên. "
                f"Anh/chị cần thêm điểm chuẩn hoặc tổ hợp xét tuyển không ạ?"
            )

    if re.search(r'ielts', ql) and (re.search(r'pt2|phương thức\s*2|phuong thuc 2', ql) or 'xét tuyển pt2' in ql or 'điều kiện' in ql):
        return (
            "Theo **Phương thức 2 (PT2)** HaUI năm 2025: chứng chỉ **IELTS Academic ≥ 5,5** (còn hiệu lực) là một trong các chứng chỉ quốc tế được chấp nhận. "
            "Ngoài ra, thí sinh cần **điểm TB từng môn** trong tổ hợp xét tuyển (lớp 10, 11, 12) **≥ 7,0** và đáp ứng điều kiện HSG cấp tỉnh hoặc chứng chỉ theo quy chế. "
            "Anh/chị cần em tra bảng quy đổi IELTS → điểm ĐQĐCC không ạ?"
        )

    if re.search(r'tỷ\s*lệ|ty\s*le|tỉ\s*lệ', ql) and re.search(r'việc\s*làm|viec\s*lam|tốt\s*nghiệp|tot\s*nghiep', ql):
        return (
            "Theo số liệu quy mô đào tạo HaUI (tham khảo công khai): "
            "**92,14%** sinh viên **chính quy** có việc làm trong **12 tháng** sau tốt nghiệp; "
            "riêng sinh viên **đại học chính quy: 92,78%**; cao đẳng chính quy: **90,61%**. "
            "Anh/chị cần thêm số liệu ngành cụ thể không ạ?"
        )

    return None


def lookup_major_tohop_chitieu(ten_keywords: list[str]) -> str | None:
    data = _load_chi_tieu_to_hop()

    def ten_norm(s):
        return re.sub(r'\s+', '', s.lower())

    for r in data:
        if r.get('nam') != 2025:
            continue
        tn = r.get('ten_nganh', '')
        if all(ten_norm(k) in ten_norm(tn) for k in ten_keywords if k):
            th = ', '.join(r.get('to_hop') or [])
            return (
                f"Ngành **{tn}** (mã **{r.get('ma_nganh')}**) xét tuyển các tổ hợp: **{th}**. "
                f"Chỉ tiêu **2025**: **{r.get('chi_tieu')}** sinh viên. Anh/chị cần thêm điểm chuẩn hoặc chương trình đào tạo không ạ?"
            )
    return None


def enrich_context(query: str, intent: str, entities: dict) -> str:
    """Append authoritative snippets so the LLM cannot miss JSON-backed facts."""
    q = query.lower()
    parts = []

    ma = entities.get('ma_nganh')
    if not ma and 'cntt' in q:
        ma = '7480201'
    nam_m = re.search(r'\b(2023|2024|2025)\b', query)
    nam = int(nam_m.group(1)) if nam_m else 2025
    pt = None
    if re.search(r'\bpt3\b|thi\s*thpt|điểm\s*thi\s*thpt', q):
        pt = 'PT3'
    elif re.search(r'\bpt2\b', q):
        pt = 'PT2'
    elif re.search(r'\bpt4\b', q):
        pt = 'PT4'
    elif re.search(r'\bpt5\b|đgtd|đánh\s*giá\s*tư\s*duy', q):
        pt = 'PT5'

    if intent == 'A1' and ma and ('điểm chuẩn' in q or q.strip().startswith('dc ') or re.search(r'\bdc\b', q)):
        s = format_diem_chuan_snippet(ma, nam, pt)
        if s:
            parts.append(s)

    ma_ct = resolve_ma_chi_tieu(query)
    if ma_ct and ('chỉ tiêu' in q or 'chi tieu' in q):
        s = format_chi_tieu_snippet(ma_ct)
        if s:
            parts.append(s)

    if intent == 'C' and re.search(r'ielts', q) and re.search(r'pt2|phương thức\s*2|điều kiện', q):
        parts.append(
            "[PT2 — phuong_thuc_tuyen_sinh_2025]\n"
            "Điều kiện chứng chỉ: **IELTS Academic ≥ 5,5** (còn hiệu lực); "
            "TB từng môn trong tổ hợp (lớp 10–12) **≥ 7,0**; kèm HSG cấp tỉnh hoặc chứng chỉ trong danh mục."
        )

    if re.search(r'tỷ\s*lệ|ty\s*le|tỉ\s*lệ', q) and re.search(r'việc\s*làm|viec\s*lam', q):
        parts.append(
            "[TỶ LỆ VIỆC LÀM — quy_mo_dao_tao.md]\n"
            "- SV chính quy (12 tháng sau TN): **92,14%**\n"
            "- SV ĐH chính quy: **92,78%** | SV CĐ chính quy: **90,61%**"
        )

    if intent == 'A2':
        if 'cntt' in q and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('CNTT'))
        if 'kinh tế' in q and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('Kinh tế'))

    if intent == 'A2' and re.search(r'ngành nào.*(toán|lý).*anh|toán.*lý.*anh|tổ hợp\s*a01', q):
        parts.append(
            "**Gợi ý tra cứu:** Tổ hợp **A01** = Toán – Vật lí – Tiếng Anh (không phải A00; A00 = Toán – Lý – Hóa)."
        )
        parts.append(format_majors_with_tohop('A01'))

    if 'nhật' in q and ('tổ hợp' in q or 'chỉ tiêu' in q) and 'hàn' not in q:
        ans = lookup_major_tohop_chitieu(['Ngôn ngữ', 'Nhật'])
        if ans:
            parts.append('[XÁC NHẬN TỪ chi_tieu_to_hop_2025.json]\n' + ans)

    if 'bao nhiêu sinh viên' in q or ('quy mô' in q and 'sinh viên' in q):
        parts.append(
            "[QUY MÔ — gioi_thieu / dữ liệu tuyển sinh]\n"
            "Tổng số sinh viên đang theo học tại HaUI khoảng **32.000 – 34.000** người; "
            "sinh viên đại học chính quy khoảng **25.447** (số liệu tham khảo từ thông tin công khai của trường)."
        )

    return '\n\n'.join(p for p in parts if p)
