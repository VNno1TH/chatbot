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


def _has_kv(text: str) -> bool:
    """Check if text mentions any khu vực (KV) keyword."""
    tl = text.lower()
    return 'kv' in tl or 'khu vực' in tl or 'khu vuc' in tl


def _parse_kv(text: str):
    tl = text.lower()
    t = tl.replace(' ', '')
    # Abbreviated: kv2-nt, kv2nt
    if 'kv2-nt' in tl or 'kv2nt' in t:
        return 'kv2-nt', KV_SCORE['kv2-nt']
    # Natural Vietnamese: "khu vực 2 nt", "khu vực 2-nt", "khu vuc 2 nt"
    if re.search(r'khu\s*v(?:ực|uc)\s*2\s*[-]?\s*nt', tl):
        return 'kv2-nt', KV_SCORE['kv2-nt']
    m_nat2 = re.search(r'khu\s*v(?:ực|uc)\s*([123])', tl)
    if m_nat2:
        k = f"kv{m_nat2.group(1)}"
        return k, KV_SCORE.get(k, 0.0)
    # Abbreviated: kv1, kv2, kv3
    m = re.search(r'\b(kv[123]|kv2-nt)\b', tl)
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


# ── Generic major detection & điểm chuẩn comparison ──
_NGANH_MA = {
    'cntt': ('Công nghệ thông tin', '7480201'),
    'công nghệ thông tin': ('Công nghệ thông tin', '7480201'),
    'cong nghe thong tin': ('Công nghệ thông tin', '7480201'),
    'ktpm': ('Kỹ thuật phần mềm', '7480103'),
    'kỹ thuật phần mềm': ('Kỹ thuật phần mềm', '7480103'),
    'an toàn thông tin': ('An toàn thông tin', '7480202'),
    'attt': ('An toàn thông tin', '7480202'),
    'khoa học máy tính': ('Khoa học máy tính', '7480101'),
    'cơ điện tử': ('CN KT Cơ điện tử', '7510203'),
    'co dien tu': ('CN KT Cơ điện tử', '7510203'),
    'điện điện tử': ('CN KT Điện, điện tử', '7510301'),
    'ô tô': ('CN KT Ô tô', '7510205'),
    'cơ khí': ('CN KT Cơ khí', '7510201'),
    'tự động hóa': ('CN KT ĐK và TĐH', '7510303'),
    'kế toán': ('Kế toán', '7340301'),
    'marketing': ('Marketing', '7340115'),
    'logistics': ('Logistics và QLCCU', '7510605'),
    'quản trị kinh doanh': ('Quản trị kinh doanh', '7340101'),
    'tiếng anh': ('Ngôn ngữ Anh', '7220201'),
    'ngôn ngữ anh': ('Ngôn ngữ Anh', '7220201'),
    'tiếng trung': ('Ngôn ngữ Trung Quốc', '7220204'),
    'tiếng nhật': ('Ngôn ngữ Nhật', '7220209'),
    'tiếng hàn': ('Ngôn ngữ Hàn Quốc', '7220210'),
    'du lịch': ('Du lịch', '7810101'),
    'thực phẩm': ('CN Thực phẩm', '7540101'),
    'điện tử viễn thông': ('CN KT Điện tử - Viễn thông', '7510302'),
    'robot': ('Robot và trí tuệ nhân tạo', '7520218'),
    'dệt may': ('CN Dệt, may', '7540204'),
    'thời trang': ('Thiết kế thời trang', '7210404'),
}


def _find_nganh_in_query(text: str):
    """Detect major name in query. Returns (ten_nganh, ma_nganh) or (None, None)."""
    tl = text.lower()
    # Sort by length descending to match longer names first (e.g. 'công nghệ thông tin' before 'ô tô')
    for alias in sorted(_NGANH_MA, key=len, reverse=True):
        if alias in tl:
            return _NGANH_MA[alias]
    return None, None


def _compare_diem_chuan(ten_nganh: str, ma_nganh: str, dxt: float) -> str:
    """Compare ĐXT with điểm chuẩn 2025. Return formatted string or empty."""
    dc = None
    for row in _load_diem_chuan():
        if row.get('ma_nganh') == ma_nganh and row.get('nam') == 2025:
            if row.get('phuong_thuc_code') == 'chung':
                dc = row.get('diem_chuan')
                break
            if dc is None:
                dc = row.get('diem_chuan')
    if dc is None:
        return ""
    if dxt >= dc:
        return (
            f"\nĐiểm chuẩn **{ten_nganh}** ({ma_nganh}) năm **2025** = **{dc}**. "
            f"Với ĐXT **{dxt:.2f} ≥ {dc}** → **đủ điều kiện trúng tuyển (tham khảo 2025)**. "
            f"(Điểm chuẩn 2026 chưa công bố.)"
        )
    return (
        f"\nĐiểm chuẩn **{ten_nganh}** ({ma_nganh}) năm **2025** = **{dc}**. "
        f"Với ĐXT **{dxt:.2f} < {dc}** → **chưa đủ so với điểm chuẩn 2025**. "
        f"(Điểm chuẩn 2026 chưa công bố, có thể thay đổi.)"
    )


def _has_admission_question(text: str) -> bool:
    """Check if text asks about admission chances."""
    tl = text.lower()
    return bool(re.search(r'đậu|đỗ|trúng tuyển|vào được|liệu.*có|có đủ|dau|do\b|trung tuyen', tl))


def _compare_multi_nganh(dxt: float, to_hop: str | None = None) -> str:
    """Compare ĐXT with điểm chuẩn 2025 of ALL matching majors. Returns formatted table."""
    rows_2025 = [r for r in _load_diem_chuan() if r.get('nam') == 2025 and r.get('phuong_thuc_code') == 'chung']
    if not rows_2025:
        return ""
    # Filter by tổ hợp if provided
    if to_hop:
        ct_data = _load_chi_tieu_to_hop()
        valid_ma = set()
        for r in ct_data:
            if r.get('nam') == 2025 and to_hop.upper() in (r.get('to_hop') or []):
                valid_ma.add(str(r.get('ma_nganh')))
        if valid_ma:
            rows_2025 = [r for r in rows_2025 if str(r.get('ma_nganh')) in valid_ma]
    # Classify
    safe = []     # ĐXT >= DC + 1
    fit = []      # DC <= ĐXT < DC + 1
    risky = []    # DC - 0.5 <= ĐXT < DC
    for r in rows_2025:
        dc = r.get('diem_chuan', 0)
        tn = r.get('ten_nganh', '')
        ma = r.get('ma_nganh', '')
        if dxt >= dc + 1.0:
            safe.append((tn, ma, dc))
        elif dxt >= dc:
            fit.append((tn, ma, dc))
        elif dxt >= dc - 0.5:
            risky.append((tn, ma, dc))
    if not safe and not fit and not risky:
        return f"\nVới ĐXT **{dxt:.2f}**, chưa đủ điểm chuẩn 2025 cho các ngành được hỏi. (Điểm chuẩn 2026 chưa công bố.)"
    lines = [f"\n**So sánh ĐXT {dxt:.2f} với điểm chuẩn 2025:**"]
    lines.append("| Ngành | Mã | ĐC 2025 | Đánh giá |")
    lines.append("|---|---|---|---|")
    for tn, ma, dc in sorted(safe, key=lambda x: -x[2])[:5]:
        lines.append(f"| {tn} | {ma} | {dc} | ✅ An toàn |")
    for tn, ma, dc in sorted(fit, key=lambda x: -x[2])[:3]:
        lines.append(f"| {tn} | {ma} | {dc} | 🟡 Vừa sức |")
    for tn, ma, dc in sorted(risky, key=lambda x: -x[2])[:3]:
        lines.append(f"| {tn} | {ma} | {dc} | 🟠 Mạo hiểm |")
    lines.append("\n*Điểm chuẩn 2026 chưa công bố — tham khảo 2025 để định hướng.*")
    return '\n'.join(lines)


def try_deterministic_b1_answer(query: str) -> str | None:
    """Return a complete Vietnamese answer or None."""
    q = query.strip()
    ql = q.lower()

    def _fmt(v): return f"{v:,.0f}".replace(',', '.')

    # --- TOEFL iBT standalone quy đổi ---
    m_toefl = re.search(r'toefl\s*(?:ibt)?\s*(\d+)', ql)
    if m_toefl and ('quy đổi' in ql or 'bao nhiêu' in ql or 'điểm' in ql):
        score = int(m_toefl.group(1))
        if score >= 80:
            dqdcc, label = 10.0, 'TOEFL iBT ≥ 80 → tương đương IELTS ≥ 6.5'
        elif score >= 65:
            dqdcc, label = 9.5, 'TOEFL iBT 65–79 → tương đương IELTS 6.0'
        elif score >= 55:
            dqdcc, label = 9.0, 'TOEFL iBT 55–64 → tương đương IELTS 5.5'
        else:
            return (
                f"⚠️ Điểm TOEFL iBT **{score}** thấp hơn mức tối thiểu quy đổi PT2 của HaUI (55+). "
                f"Anh/chị cần có TOEFL iBT ≥ 55 (tương đương IELTS ≥ 5.5) để xét PT2."
            )
        return (
            f"📊 **Quy đổi TOEFL iBT → ĐQĐCC (PT2):**\n"
            f"- Điểm TOEFL iBT: **{score}**\n"
            f"- {label}\n"
            f"- ĐQĐCC (điểm quy đổi chứng chỉ): **{dqdcc}** (thang 10)\n"
            f"- TOEFL iBT là bài thi tiếng Anh quốc tế (Test of English as a Foreign Language, Internet-Based Test) do ETS tổ chức.\n"
            f"→ Điểm này sẽ cộng vào công thức PT2: ĐXT = ĐKQHT × 2 + ĐQĐCC + Điểm ưu tiên.\n"
            f"Anh/chị cần tính ĐXT đầy đủ không ạ?"
        )

    # --- IELTS standalone quy đổi ---
    m_ielts = re.search(r'ielts\s*(\d+(?:\.\d+)?)', ql)
    if m_ielts and ('quy đổi' in ql or 'bao nhiêu' in ql or 'điểm' in ql) and 'pt2' not in ql and not _has_kv(ql):
        score = float(m_ielts.group(1))
        if score >= 6.5:
            dqdcc = 10.0
        elif score >= 6.0:
            dqdcc = 9.5
        elif score >= 5.5:
            dqdcc = 9.0
        else:
            return (
                f"⚠️ IELTS **{score}** thấp hơn mức tối thiểu quy đổi PT2 của HaUI (5.5+). "
                f"Anh/chị cần có IELTS ≥ 5.5 để xét PT2."
            )
        return (
            f"📊 **Quy đổi IELTS → ĐQĐCC (PT2):**\n"
            f"- IELTS: **{score}**\n"
            f"- ĐQĐCC: **{dqdcc}** (thang 10)\n"
            f"→ Điểm này cộng vào PT2: ĐXT = ĐKQHT × 2 + ĐQĐCC + Điểm ưu tiên.\n"
            f"Anh/chị cần tính ĐXT đầy đủ không ạ?"
        )

    # --- KTX + HP combo cost ---
    if ('ktx' in ql or 'ký túc xá' in ql) and ('học phí' in ql or 'tín chỉ' in ql or 'tc ' in ql) and ('tổng' in ql or 'chi phí' in ql):
        # Parse KTX
        ktx_cost = 0
        ktx_label = ''
        if 'chất lượng cao' in ql or 'clc' in ql:
            if '3 người' in ql:
                ktx_cost, ktx_label = 800_000, 'KTX CLC 3 người'
            elif '6 người' in ql:
                ktx_cost, ktx_label = 400_000, 'KTX CLC 6 người'
            else:
                ktx_cost, ktx_label = 600_000, 'KTX CLC 4 người'
        elif 'tiêu chuẩn' in ql or 'tc ' in ql:
            if 'cs2' in ql or 'cơ sở 2' in ql:
                ktx_cost = 420_000 if '4 người' in ql else 280_000
                ktx_label = f'KTX TC CS2 {"4" if "4 người" in ql else "6"} người'
            else:
                ktx_cost = 465_000 if '4 người' in ql else 310_000
                ktx_label = f'KTX TC CS1 {"4" if "4 người" in ql else "6"} người'
        else:
            # Default: detect phòng N người
            if '3 người' in ql:
                ktx_cost, ktx_label = 800_000, 'KTX CLC 3 người'
            elif '4 người' in ql:
                ktx_cost, ktx_label = 600_000, 'KTX CLC 4 người'
            elif '6 người' in ql:
                ktx_cost, ktx_label = 400_000, 'KTX CLC 6 người'

        # Parse HP
        m_tc_combo = re.search(r'(\d+)\s*(?:tc|tín chỉ)', ql)
        if ktx_cost > 0 and m_tc_combo:
            n_tc = int(m_tc_combo.group(1))
            if 'tiếng anh' in ql:
                dg = 1_000_000; dg_label = 'K20 TA'
            elif 'k19' in ql:
                dg = 550_000; dg_label = 'K19'
            else:
                dg = 700_000; dg_label = 'K20 đại trà'

            if 'thực hành chuyên sâu' in ql or 'chuyên sâu' in ql:
                coef = 2.5
            elif 'thể chất' in ql or 'gdtc' in ql:
                coef = 1.0
            elif 'thực hành' in ql:
                coef = 1.5
            else:
                coef = 1.5

            hp_total = int(n_tc * coef * dg)
            # Assume 1 kỳ = 5 tháng → HP/tháng
            hp_per_month = hp_total / 5
            total_month = ktx_cost + hp_per_month
            return (
                f"📊 **Tính tổng chi phí 1 tháng:**\n"
                f"- {ktx_label}: **{_fmt(ktx_cost)}** đ/tháng\n"
                f"- Học phí: {n_tc} TC × {coef} × {_fmt(dg)} = **{_fmt(hp_total)}** đ/kỳ\n"
                f"  → Chia 5 tháng: **{_fmt(int(hp_per_month))}** đ/tháng\n"
                f"→ **Tổng ≈ {_fmt(int(total_month))} đ/tháng** (KTX + học phí chia đều).\n"
                f"⚠️ Chưa bao gồm điện, nước, sinh hoạt phí.\n"
                f"Anh/chị cần tính thêm gì không ạ?"
            )

    # --- HSA / ĐGNL (chỉ quy đổi đơn, không chạy khi đã kết hợp KV + CNTT ở mục sau) ---
    m_hsa_only = re.search(r'(?:hsa|đgnl|đánh\s*giá\s*năng\s*lực)\s*(\d{2,3})\b', ql)
    if not m_hsa_only:
        # Also try: "thi ĐGNL được 120 điểm"
        m_hsa_only = re.search(r'(?:hsa|đgnl|đánh\s*giá\s*năng\s*lực)[^\d]{0,20}(\d{2,3})\b', ql)
    if m_hsa_only and ('quy đổi' in ql or 'bao nhiêu' in ql or 'điểm' in ql) and 'cntt' not in ql and not _has_kv(ql) and not _has_admission_question(ql):
        s = int(m_hsa_only.group(1))
        v = lookup_hsa(s)
        if v is not None:
            return (
                f"Theo bảng quy đổi ĐQĐNL (HSA) của HaUI, điểm HSA **{s}** quy đổi thang 30 là **{v:.2f}** điểm "
                f"(tra bảng chính thức, không nội suy). Anh/chị cần em tính thêm ưu tiên KV/ĐT không ạ?"
            )

    # --- TSA + KV/ĐT / ngành → tính điểm xét tuyển + so sánh điểm chuẩn ---
    m_tsa = re.search(r'tsa[^\d]{0,30}(\d+(?:\.\d+)?)', ql)
    if m_tsa and (_has_kv(ql) or _has_admission_question(ql)):
        s = float(m_tsa.group(1))
        base = lookup_tsa(s)
        if base is not None:
            _, kv_b = _parse_kv(q)
            dt_b = _parse_dt(q)
            dxt, body = compute_pt3_admission(base, kv_b, dt_b)
            if dxt is None:
                return body
            # Check if a specific major is mentioned → compare with điểm chuẩn
            ten_nganh, ma_nganh = _find_nganh_in_query(ql)
            extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt) if ma_nganh else ""
            tail = "Anh/chị cần thêm thông tin gì không ạ?" if extra else "Anh/chị cần so sánh với điểm chuẩn ngành nào ạ?"
            return (
                f"📊 **Tính điểm xét tuyển từ TSA (tham khảo PT5 + ưu tiên):**\n"
                f"- Điểm TSA **{s}** → quy đổi thang 30: **{base:.2f}**\n"
                f"{body}\n"
                f"→ **Điểm xét tuyển ≈ {dxt:.2f}**.{extra}\n"
                f"{tail}"
            )

    # --- TSA (chỉ quy đổi đơn, không có KV) ---
    if m_tsa and ('quy đổi' in ql or 'bao nhiêu' in ql) and not _has_kv(ql):
        s = float(m_tsa.group(1))
        v = lookup_tsa(s)
        if v is not None:
            return (
                f"Theo bảng quy đổi ĐGTD (TSA) ĐHBK Hà Nội dùng tại HaUI, điểm TSA **{s}** quy đổi thang 30 là **{v:.2f}** điểm. "
                f"Cần thêm thông tin gì nữa ạ?"
            )

    # --- KQHB (Quy đổi điểm trung bình học bạ) ---
    m = re.search(
        r'(?:điểm\s*tb|tb|trung\s*bình|môn)\s*(?:cả\s*năm\s*)?(?:môn\s*)?(toán|lý|hóa|anh|văn|tiếng\s*anh|ngoại\s*ngữ)?[^0-9]{0,15}(\d+(?:\.\d+)?)',
        ql,
    )
    if m and ('quy đổi' in ql or 'kqhb' in ql or 'kqht' in ql or 'đkqht' in ql or ('học bạ' in ql and 'quy đổi' in ql)):
        avg = float(m.group(2))
        subject = m.group(1) or 'Toán'
        v = lookup_kqhb(avg)
        if v is not None:
            return (
                f"Điểm trung bình cả năm môn {subject.capitalize()} **{avg}** (thang 10) quy đổi theo bảng ĐKQHT của HaUI là **{v:.2f}** điểm (thang 10). "
                f"Anh/chị cần tra thêm môn khác không ạ?"
            )

    # --- Học phí học phần ---
    # Detect combo: "3TC lý thuyết + 2TC thực hành thí nghiệm"
    m_combo = re.findall(r'(\d+)\s*(?:tc|tín chỉ)\s*(lý thuyết|thực hành chuyên sâu|chuyên sâu|thí nghiệm|th thường|th\b|thực hành thông thường|thực hành|thể chất|gdtc|qpan|ngoại ngữ|tiểu luận|đồ án|lab)', ql)
    m_tc = re.search(r'(\d+)\s*tín\s*chỉ', ql)
    if not m_tc:
        m_tc = re.search(r'(\d+)\s*tc', ql)

    if (m_combo or m_tc) and ('học phí' in ql or 'tính hp' in ql or 'học phần' in ql or 'tổng' in ql or 'bao nhiêu' in ql):
        # Xác định đơn giá theo khóa/hệ
        if 'tiếng anh' in ql or 'k20 ta' in ql or ('k20' in ql and 'tiếng' in ql):
            dg = 1_000_000; label_dg = 'K20 chương trình Tiếng Anh'
        elif 'k19' in ql:
            dg = 550_000; label_dg = 'K19'
        elif 'k18' in ql or 'k17' in ql:
            dg = 495_000; label_dg = 'K18 trở về trước'
        elif 'cao đẳng' in ql or 'cđ' in ql:
            dg = 370_000; label_dg = 'Cao đẳng chính quy'
        elif 'thạc sĩ' in ql:
            dg = 900_000; label_dg = 'Thạc sĩ'
        else:
            dg = 700_000; label_dg = 'K20 đại trà'

        def _fmt(v): return f"{v:,.0f}".replace(',', '.')
        def _get_coef(hp_type):
            hp_type = hp_type.lower().strip()
            # Thực hành CHUYÊN SÂU (lab nâng cao) → ×2.5
            if hp_type in ('thực hành chuyên sâu', 'chuyên sâu', 'lab'):
                return 2.5, 'Thực hành/thí nghiệm chuyên sâu'
            # Thực hành thí nghiệm thông thường → ×1.5
            if hp_type in ('thực hành', 'thí nghiệm', 'th thường', 'th', 'thực hành thông thường'):
                return 1.5, 'Thực hành/thí nghiệm'
            # GDTC, QPAN → ×1.0
            if hp_type in ('thể chất', 'gdtc', 'qpan'):
                return 1.0, 'GDTC/QPAN'
            # Ngoại ngữ → ×1.5
            if hp_type == 'ngoại ngữ':
                return 1.5, 'Ngoại ngữ'
            return 1.5, 'Lý thuyết/tiểu luận/đồ án'

        # Combo: nhiều loại TC trong 1 câu
        if len(m_combo) >= 2:
            lines = [f"📊 **Tính học phí học phần** (năm học 2025–2026):\n"]
            total_hp = 0
            for n_str, hp_type in m_combo:
                n = int(n_str)
                coef, label_hp = _get_coef(hp_type)
                nt = n * coef
                hp = int(nt * dg)
                total_hp += hp
                lines.append(f"- **{n} TC** {label_hp} (×{coef}): {n} × {coef} × {_fmt(dg)} = **{_fmt(hp)} đ**")
            lines.append(f"- Đơn giá ({label_dg}): **{_fmt(dg)}** đ/TC")
            lines.append(f"→ **Tổng HP = {_fmt(total_hp)} đồng** (= {total_hp} đ).")
            lines.append("Anh/chị cần tính thêm học phần khác không ạ?")
            return '\n'.join(lines)

        # Đơn: 1 loại TC
        n = int(m_tc.group(1)) if m_tc else int(m_combo[0][0])
        if m_combo:
            coef, label_hp = _get_coef(m_combo[0][1])
        elif 'thực hành chuyên sâu' in ql or 'chuyên sâu' in ql or 'thí nghiệm' in ql:
            coef = 2.5; label_hp = 'Thực hành/thí nghiệm chuyên sâu'
        elif 'thể chất' in ql or 'quốc phòng' in ql or 'gdtc' in ql or 'qpan' in ql:
            coef = 1.0; label_hp = 'GDTC/QPAN'
        elif 'thực hành' in ql:
            coef = 1.5; label_hp = 'Thực hành thông thường'
        elif 'lý thuyết' in ql or 'tiểu luận' in ql or 'đồ án' in ql:
            coef = 1.5; label_hp = 'Lý thuyết/tiểu luận/đồ án'
        elif 'ngoại ngữ' in ql:
            coef = 1.5; label_hp = 'Ngoại ngữ'
        else:
            coef = 1.5; label_hp = 'Lý thuyết (mặc định)'
        nt = n * coef
        hp = int(nt * dg)
        return (
            f"📊 **Tính học phí học phần** (năm học 2025–2026):\n"
            f"- Số tín chỉ: **{n}**\n"
            f"- Loại học phần: {label_hp} → hệ số **×{coef}**\n"
            f"- Số TC quy đổi: {n} × {coef} = **{nt}**\n"
            f"- Đơn giá ({label_dg}): **{_fmt(dg)}** đ/TC\n"
            f"→ **HP = {nt} × {_fmt(dg)} = {_fmt(hp)} đồng** (= {hp} đ).\n"
            f"Anh/chị cần tính thêm học phần khác không ạ?"
        )


    # --- PT2 ---
    if 'pt2' in ql or 'phương thức 2' in ql:
        # Parse 3 môn: hỗ trợ "tb toán X", "toán/văn/anh lần lượt X/Y/Z", "toán X văn Y anh Z"
        tb_t = re.search(r'(?:tb\s*)?toán\s*[:/]?\s*(\d+(?:\.\d+)?)', ql)
        tb_v = re.search(r'(?:tb\s*)?(?:văn|ngữ\s*văn)\s*[:/]?\s*(\d+(?:\.\d+)?)', ql)
        tb_a = re.search(r'(?:tb\s*)?(?:anh|tiếng\s*anh)\s*[:/]?\s*(\d+(?:\.\d+)?)', ql)
        # Also try "lần lượt là X/Y/Z" or "X/Y/Z" (e.g. 9.0/8.5/9.4)
        if not (tb_t and tb_v and tb_a):
            # Try to find the sequence of 3 numbers separated by / or ,
            m_seq = re.search(
                r'(?:lần\s*lượt\s*(?:là\s*)?)?'
                r'(\d+(?:\.\d+)?)[/,]\s*(\d+(?:\.\d+)?)[/,]\s*(\d+(?:\.\d+)?)',
                ql
            )
            if m_seq and ('toán' in ql or 'lần lượt' in ql or '/' in ql):
                v1, v2, v3 = m_seq.group(1), m_seq.group(2), m_seq.group(3)
                if not tb_t:
                    tb_t = type('M', (), {'group': lambda s, i, _v=v1: _v})()
                if not tb_v:
                    tb_v = type('M', (), {'group': lambda s, i, _v=v2: _v})()
                if not tb_a:
                    tb_a = type('M', (), {'group': lambda s, i, _v=v3: _v})()
        if tb_t and tb_v and tb_a:
            t, v_score, a = float(tb_t.group(1)), float(tb_v.group(1)), float(tb_a.group(1))
            # --- FIX 1.1: Quy đổi điểm TB qua bảng KQHB trước khi tính ĐKQHT ---
            t_qd = lookup_kqhb(t)
            v_qd = lookup_kqhb(v_score)
            a_qd = lookup_kqhb(a)
            # Nếu có bảng quy đổi → dùng giá trị quy đổi; nếu không → giữ nguyên
            t_used = t_qd if t_qd is not None else t
            v_used = v_qd if v_qd is not None else v_score
            a_used = a_qd if a_qd is not None else a
            has_kqhb = (t_qd is not None or v_qd is not None or a_qd is not None)
            dkqht = round((t_used + v_used + a_used) / 3, 3)
            # Detect chứng chỉ / giải HSG
            dqdcc = None
            cert_label = None
            # Giải HSG
            prize = re.search(r'giải\s*(nhất|nhì|ba)\s*(hsg|học sinh giỏi)', ql)
            if prize:
                g = prize.group(1)
                dqdcc = {'nhất': 10.0, 'nhì': 9.5, 'ba': 9.0}[g]
                cert_label = f"Giải {g.capitalize()} HSG tỉnh"
            # IELTS
            if dqdcc is None:
                ielts_m = re.search(r'ielts\s*(\d+(?:\.\d+)?)', ql)
                if ielts_m:
                    ielts = float(ielts_m.group(1))
                    dqdcc = _ielts_to_dqdcc(ielts)
                    cert_label = f"IELTS {ielts}"
            # TOEFL iBT
            if dqdcc is None:
                toefl_m = re.search(r'toefl\s*(?:ibt)?\s*(\d+)', ql)
                if toefl_m:
                    toefl = int(toefl_m.group(1))
                    if toefl >= 80: dqdcc = 10.0
                    elif toefl >= 65: dqdcc = 9.5
                    elif toefl >= 55: dqdcc = 9.0
                    cert_label = f"TOEFL iBT {toefl}"
            # SAT
            if dqdcc is None:
                sat_m = re.search(r'sat\s*(\d{3,4})', ql)
                if sat_m:
                    sat = int(sat_m.group(1))
                    if sat >= 1200: dqdcc = 10.0
                    elif sat >= 1101: dqdcc = 9.5
                    elif sat >= 1000: dqdcc = 9.0
                    cert_label = f"SAT {sat}"
            if dqdcc is not None:
                _, kv_b = _parse_kv(q)
                dt_b = _parse_dt(q)
                dxt_raw = round(dkqht * 2 + dqdcc, 2)
                # Apply ưu tiên
                bonus = kv_b + dt_b
                if dxt_raw < 22.5:
                    dxt = round(dxt_raw + bonus, 2)
                else:
                    ddt = round(((30 - dxt_raw) / 7.5) * bonus, 2)
                    dxt = round(dxt_raw + ddt, 2)
                ten_nganh, ma_nganh = _find_nganh_in_query(ql)
                extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt) if ma_nganh else ""
                if not extra and _has_admission_question(ql) and ma_nganh:
                    extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt)
                tail = "Anh/chị cần thêm thông tin gì không ạ?" if extra else "Anh/chị muốn so sánh với điểm chuẩn ngành nào ạ?"
                kv_line = f"\n- Ưu tiên KV: **+{kv_b:.2f}**" if kv_b > 0 else ""
                dt_line = f"\n- Ưu tiên ĐT: **+{dt_b:.2f}**" if dt_b > 0 else ""
                bonus_calc = ""
                if bonus > 0:
                    if dxt_raw >= 22.5:
                        bonus_calc = f"\n- Vì ĐXT gốc {dxt_raw} ≥ 22.5 → giảm dần: ĐĐT = [(30-{dxt_raw})/7.5]×{bonus:.2f} = **{round(((30-dxt_raw)/7.5)*bonus, 2)}**"
                    bonus_calc += f"\n→ **ĐXT cuối = {dxt:.2f}**"
                # Build KQHB conversion display
                kqhb_note = ""
                if has_kqhb:
                    kqhb_note = f"\n- Quy đổi ĐKQHT: Toán {t}→{t_used}, Văn {v_score}→{v_used}, Anh {a}→{a_used}"
                return (
                    f"📊 **Tính điểm xét tuyển PT2 (HaUI):**\n"
                    f"- TB Toán = {t}, TB Văn = {v_score}, TB Anh = {a}{kqhb_note}\n"
                    f"- ĐKQHT = ({t_used}+{v_used}+{a_used})/3 = **{dkqht}**\n"
                    f"- {cert_label} → ĐQĐCC = **{dqdcc:.2f}**\n"
                    f"- **ĐXT = {dkqht} × 2 + {dqdcc:.2f} = {dxt_raw:.2f}**"
                    f"{kv_line}{dt_line}{bonus_calc}{extra}\n"
                    f"{tail}"
                )

    # --- PT3: điểm từng môn ---
    subj = re.findall(
        r'(toán|lý|hóa|anh|văn)\s*(\d+(?:\.\d+)?)',
        ql.replace('tiếng anh', 'anh'),
        re.IGNORECASE,
    )
    if len(subj) >= 3 and ('tính' in ql or 'xét tuyển' in ql or _has_kv(ql) or _has_admission_question(ql)):
        mp = {'toán': None, 'lý': None, 'hóa': None, 'anh': None, 'văn': None}
        for name, val in subj:
            k = name.lower()
            if k in mp:
                mp[k] = float(val)
        scores = [v for v in mp.values() if v is not None]
        if len(scores) >= 3:
            total = sum(scores[:3])  # take first 3 matched subjects
            _, kv_b = _parse_kv(q)
            dt_b = _parse_dt(q)
            dxt, body = compute_pt3_admission(total, kv_b, dt_b)
            if dxt is None:
                return body
            # Multi-major comparison: "đỗ vào các ngành nào" or "ngành nào"
            if re.search(r'(các ngành|ngành nào|những ngành)', ql):
                # Extract tổ hợp from query
                th_m = re.search(r'\b(A0[0-2]|B00|C0[1-4]|D0[1467]|D1[45]|DD2|X0[5-7]|X2[57])\b', q, re.IGNORECASE)
                to_hop = th_m.group(1) if th_m else None
                extra = _compare_multi_nganh(dxt, to_hop)
            else:
                ten_nganh, ma_nganh = _find_nganh_in_query(ql)
                extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt) if ma_nganh else ""
                # Fix 1.4: luôn so sánh DC khi có admission question
                if not extra and _has_admission_question(ql):
                    if ma_nganh:
                        extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt)
                    else:
                        extra = _compare_multi_nganh(dxt)
            tail = "Anh/chị cần thêm thông tin gì không ạ?" if extra else "Anh/chị muốn đối chiếu với điểm chuẩn ngành nào ạ?"
            return f"📊 **Tính điểm xét tuyển PT3:**\n{body}\n→ **Điểm xét tuyển ≈ {dxt:.2f}**.{extra}\n{tail}"

    # --- PT3: chỉ có tổng ---
    m_tot = re.search(r'tổng\s*(\d+(?:\.\d+)?)\s*điểm', ql)
    if not m_tot:
        m_tot = re.search(r'^tổng\s+(\d+(?:\.\d+)?)\b', ql)
    if m_tot and (_has_kv(ql) or 'đt' in ql or 'đối tượng' in ql) and ('tính' in ql or 'xét' in ql or _has_admission_question(ql)):
        total = float(m_tot.group(1))
        _, kv_b = _parse_kv(q)
        dt_b = _parse_dt(q)
        dxt, body = compute_pt3_admission(total, kv_b, dt_b)
        if dxt is None:
            return body
        ten_nganh, ma_nganh = _find_nganh_in_query(ql)
        extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt) if ma_nganh else ""
        # Fix 1.4: luôn so sánh DC khi có admission question
        if not extra and _has_admission_question(ql):
            if ma_nganh:
                extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt)
            else:
                extra = _compare_multi_nganh(dxt)
        tail = "Anh/chị cần thêm thông tin gì không ạ?" if extra else "Anh/chị cần so sánh thêm ngành khác không ạ?"
        return f"📊 **Tính điểm xét tuyển PT3:**\n{body}\n→ **ĐXT ≈ {dxt:.2f}**.{extra}\n{tail}"

    # --- HSA / ĐGNL + KV/ĐT + ngành → tính ĐXT + so sánh điểm chuẩn ---
    m_h = re.search(r'(?:hsa|đgnl|đánh\s*giá\s*năng\s*lực)\s*(\d{2,3})', ql)
    if not m_h:
        m_h = re.search(r'(?:hsa|đgnl|đánh\s*giá\s*năng\s*lực)[^\d]{0,20}(\d{2,3})\b', ql)
    if m_h and (_has_kv(ql) or _has_admission_question(ql)):
        h = int(m_h.group(1))
        base = lookup_hsa(h)
        if base is None:
            return None
        _, kv_b = _parse_kv(q)
        dt_b = _parse_dt(q)
        dxt, body = compute_pt3_admission(base, kv_b, dt_b)
        if dxt is None:
            return body
        ten_nganh, ma_nganh = _find_nganh_in_query(ql)
        extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt) if ma_nganh else ""
        # Fix 1.4: luôn so sánh DC khi có admission question
        if not extra and _has_admission_question(ql):
            if ma_nganh:
                extra = _compare_diem_chuan(ten_nganh, ma_nganh, dxt)
            else:
                extra = _compare_multi_nganh(dxt)
        tail = "Anh/chị cần thêm thông tin gì không ạ?" if extra else "Anh/chị cần tư vấn thêm ngành khác không ạ?"
        return (
            f"📊 **Quy đổi & tính ĐXT (tham khảo PT5 + ưu tiên):**\n"
            f"- HSA {h} → thang 30: **{base}**\n"
            f"{body}\n"
            f"→ **ĐXT ≈ {dxt:.2f}**.{extra}\n"
            f"{tail}"
        )

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


def format_all_diem_chuan_2025() -> str:
    """Return full table of ALL majors with ĐC 2025, sorted descending."""
    rows = [
        r for r in _load_diem_chuan()
        if r.get('nam') == 2025 and r.get('phuong_thuc_code') == 'chung'
    ]
    if not rows:
        return ""
    rows.sort(key=lambda x: (-(x.get('diem_chuan') or 0), x.get('ten_nganh', '')))
    lines = ["[BẢNG ĐIỂM CHUẨN 2025 TOÀN BỘ NGÀNH — từ dữ liệu HaUI]", "| Ngành | Mã | ĐC 2025 |", "|---|---:|---:|"]
    for r in rows:
        lines.append(f"| {r.get('ten_nganh')} | {r.get('ma_nganh')} | {r.get('diem_chuan')} |")
    return '\n'.join(lines)


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
        # Fix 2.2: Inject data cho TẤT CẢ nhóm ngành
        if re.search(r'cơ khí|cơ điện|ô tô|robot|tự động', q) and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('Cơ khí'))
        if re.search(r'du lịch|khách sạn|nhà hàng|lữ hành', q) and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('Du lịch'))
        if re.search(r'ngôn ngữ|tiếng|trung quốc|nhật|hàn', q) and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('Ngôn ngữ'))
        if re.search(r'dệt|may|thời trang', q) and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('Dệt may'))
        if re.search(r'thực phẩm|hóa|môi trường|dược', q) and 'điểm chuẩn' in q:
            parts.append(format_nhom_diem_chuan_2025('Thực phẩm'))
        # Fix 2.1: Inject TOÀN BỘ DC 2025 cho ranking/listing
        if re.search(r'cao nhất|thấp nhất|top|xếp hạng|dễ vào|khó vào|tất cả|toàn bộ|danh sách', q):
            parts.append(format_all_diem_chuan_2025())

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

    # Fix 2.3: Inject phương thức tuyển sinh
    if re.search(r'(phương thức|cách xét tuyển|pt[1-5]|mấy phương thức)', q) and intent in ('A2', 'C'):
        parts.append(
            "[PHƯƠNG THỨC TUYỂN SINH 2025/2026 — phuong_thuc_tuyen_sinh]\n"
            "HaUI áp dụng **5 phương thức** xét tuyển:\n"
            "- **PT1**: Xét tuyển thẳng, ưu tiên xét tuyển (đối tượng theo QĐ Bộ GD&ĐT)\n"
            "- **PT2**: Xét kết hợp học bạ THPT + chứng chỉ quốc tế / giải HSG (IELTS ≥ 5.5, JLPT N3+, SAT ≥ 1000...), TB từng môn ≥ 7.0\n"
            "- **PT3**: Xét điểm thi TN THPT (tổng 3 môn tổ hợp, thang 30 + ưu tiên)\n"
            "- **PT4**: Xét kết quả ĐGNL ĐHQG HN (HSA) — quy đổi theo bảng HaUI\n"
            "- **PT5**: Xét kết quả ĐGTD ĐHBK HN (TSA) — quy đổi theo bảng HaUI\n"
            "Năm 2025: ĐC **chung** cho PT2+PT3+PT5 (hoặc PT2+PT3+PT4). Năm 2026: dự kiến tương tự."
        )

    # Fix 2.4: Inject học bổng đầy đủ
    if re.search(r'(học bổng|hỗ trợ tài chính|hb )', q) and intent in ('A2', 'C', 'D'):
        parts.append(
            "[HỌC BỔNG HaUI — hoc_bong / chinh_sach — 4 NHÓM]\n"
            "**1. HB HaUI (toàn khóa — 100% HP):** Thủ khoa đầu vào (từng phương thức, từng nhóm tổ hợp). "
            "Duy trì: TBC kỳ ≥ 2.5, rèn luyện Tốt, ≥ 15TC/kỳ.\n"
            "**2. HB KKHT (theo kỳ):** Xét mỗi kỳ, dựa GPA + rèn luyện + số TC. "
            "Loại Xuất sắc (GPA ≥ 3.6, RL ≥ 90): miễn 100% HP kỳ đó; Giỏi (GPA ≥ 3.2, RL ≥ 80): miễn 50%; Khá (GPA ≥ 2.5, RL ≥ 65): miễn 30%. "
            "Yêu cầu: ≥ 15TC, không bị kỷ luật. **Không xét KKHT nếu đang nhận HB HaUI cùng kỳ.**\n"
            "**3. HB tài trợ doanh nghiệp:** Theo từng đợt, do doanh nghiệp đối tác quyết định.\n"
            "**4. Hỗ trợ tài chính:** Miễn giảm HP cho đối tượng chính sách (con liệt sĩ, thương binh, hộ nghèo...)."
        )

    # Fix 2.5: Inject lịch tuyển sinh 2026
    if re.search(r'(lịch|khi nào|deadline|hạn nộp|thời gian|bao giờ)', q) and re.search(r'(tuyển sinh|đăng ký|xét tuyển|nhập học|pt[2-5])', q) and intent in ('A1', 'A2', 'C'):
        parts.append(
            "[LỊCH TUYỂN SINH 2026 — DỰ KIẾN — lich_tuyen_sinh_2026]\n"
            "- **PT2/PT4/PT5**: Đăng ký 15/5 – 20/6/2026 (17h00). Kết quả dự kiến 30/6/2026.\n"
            "- **PT3**: Theo lịch xét tuyển Bộ GD&ĐT (dự kiến 8–9/2026 sau khi có điểm thi TN THPT).\n"
            "- **PT1**: Xét tuyển thẳng theo QĐ Bộ GD&ĐT, hồ sơ nộp trước 15/5/2026.\n"
            "- **Nhập học**: Dự kiến 9/2026.\n"
            "⚠️ Lịch trên là DỰ KIẾN, có thể thay đổi theo thông báo chính thức."
        )

    # Fix 2.2b: Inject chương trình Tiếng Anh
    if re.search(r'(tiếng anh|chương trình ta|english|ct tiếng)', q) and re.search(r'(ngành nào|những ngành|danh sách|có những)', q):
        parts.append(
            "[CHƯƠNG TRÌNH ĐÀO TẠO BẰNG TIẾNG ANH — NĂM 2025]\n"
            "Các ngành có chương trình đào tạo bằng Tiếng Anh tại HaUI:\n"
            "- Công nghệ thông tin (7480201)\n"
            "- Kỹ thuật phần mềm (7480103)\n"
            "- Quản trị kinh doanh (7340101)\n"
            "- Kế toán (7340301)\n"
            "Đơn giá: **1.000.000** đ/TC (so với 700.000 đ/TC chương trình đại trà)."
        )

    # Inject authoritative học phí data
    if any(kw in q for kw in ['học phí', 'mức thu', 'tín chỉ']) and intent in ('A1', 'B1', 'C', 'D'):
        parts.append(
            "[BẢNG HỌC PHÍ CHÍNH THỨC — muc_thu_hoc_phi.json — NĂM HỌC 2025-2026]\n"
            "| Hệ đào tạo | Đơn giá/TC |\n|---|---|\n"
            "| Cử nhân K20 chương trình đại trà | **700.000** đ/TC |\n"
            "| Cử nhân K20 chương trình đào tạo bằng Tiếng Anh | **1.000.000** đ/TC |\n"
            "| K19 | **550.000** đ/TC |\n"
            "| K18 trở về trước | **495.000** đ/TC |\n"
            "| Cao đẳng chính quy | **370.000** đ/TC |\n"
            "| Thạc sĩ | **900.000** đ/TC |\n"
            "| Tiến sĩ | **35.000.000** đ/năm |\n"
            "⚠️ Dùng ĐÚNG số liệu trên, không dùng số khác."
        )

    # Inject authoritative KTX data
    if any(kw in q for kw in ['ktx', 'ký túc xá', 'phòng ở', 'phòng ktx']) and intent in ('A1', 'B1', 'C', 'D'):
        parts.append(
            "[BẢNG GIÁ KTX CHÍNH THỨC — ky_tuc_xa — NĂM HỌC 2025-2026]\n"
            "**Phòng chất lượng cao** (điều hòa, nóng lạnh, tủ cá nhân — cả CS1 và CS2):\n"
            "- 3 người: **800.000** đ/người/tháng\n"
            "- 4 người: **600.000** đ/người/tháng\n"
            "- 6 người: **400.000** đ/người/tháng\n"
            "**Phòng tiêu chuẩn** (không điều hòa):\n"
            "- CS1: 4 người **465.000** đ | 6 người **310.000** đ/người/tháng\n"
            "- CS2: 4 người **420.000** đ | 6 người **280.000** đ/người/tháng\n"
            "⚠️ Dùng ĐÚNG số liệu trên, không dùng số khác."
        )

    return '\n\n'.join(p for p in parts if p)
