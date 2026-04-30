# 📋 BÁO CÁO PHÂN TÍCH & KẾ HOẠCH SỬA CHATBOT HaUI

> **Mục đích**: Tài liệu này chứa ĐẦY ĐỦ thông tin để một AI agent (Gemini, Claude, GPT) có thể đọc và sửa code chatbot.
> **Tiêu chí đánh giá**: answer phải đúng ground_truth_full về: (1) coverage, (2) semantic correctness, (3) không thiếu ý, (4) không sai lệch.

---
## PHẦN 1: KIẾN TRÚC PIPELINE & CODE MAP

### 1.1 Files chính
| File | Path | Lines | Vai trò |
|---|---|---|---|
| pipeline.py | src/rag/pipeline.py | 1154 | Router (regex+LLM) + Retriever (hybrid) + Generator |
| structured.py | src/rag/structured.py | 1043 | Deterministic B1 logic + enrich_context() |
| prompts.py | src/rag/prompts.py | 380 | System prompt template |
| config.py | src/config.py | 59 | Environment variables |

### 1.2 Pipeline Flow (handle_query — pipeline.py:969)
```
User Query
  → fast_route() regex (L305-560) → fallback llm_route() (L611)
  → E/F: canned response, return
  → try_deterministic_b1_answer() (structured.py:262-721)
    ↳ Nếu parse được → return TRỰC TIẾP (không qua LLM, không retrieve)
  → try_deterministic_kb_answer() (structured.py:816-844)
  → extract_entities() → rewrite_query() → expand_query()
  → HyDE (chỉ A2,B2) → embed → hybrid_search (ChromaDB+BM25+RRF)
  → rerank (BGE-Reranker) → self_reflect
  → enrich_context() (structured.py:881-1043) — inject JSON data
  → generate_response() — LLM call với system prompt
    max_tokens: E/F=256, A1=512, C=640, others=896
```

### 1.3 KEY INSIGHT
> Khi `try_deterministic_b1_answer()` match → chatbot KHÔNG retrieve context, KHÔNG gọi LLM.
> → context_precision=1, context_recall=1 cho B1 là **bình thường**, không phải lỗi Retriever.
> → Các lỗi B1 chỉ có thể do: (a) logic code sai, (b) bảng quy đổi sai, (c) thiếu so sánh ĐC.

---
## PHẦN 2: THỐNG KÊ

| Metric | Giá trị |
|---|---|
| Tổng test cases | **196** |
| Cases đạt chuẩn | **92** (không lỗi nào) |
| Cases cần sửa | **104** |
| 🔴 CRITICAL | **22** (fact=0 hoặc router sai) |
| 🟠 MAJOR | **49** (score<3 hoặc completeness≤2) |
| 🟡 MINOR | **33** (fact<1 hoặc completeness=3) |

---
## PHẦN 3: BUGS TRONG CODE CẦN SỬA

### 3.1 structured.py — Logic bugs

| # | Bug | File:Line | Sửa |
|---|---|---|---|
| 1 | Robot mã ngành cũ `7520218` | structured.py:172 | Đổi thành `75102032` |
| 2 | KTX+HP chia 5 tháng (đúng 4) | structured.py:367 | `hp_per_month = hp_total / 4` |
| 3 | SAT 1000-1100→9.50 (đúng 9.00) | structured.py:591 hoặc LLM | Verify `diem_quy_doi.json`, sửa code hoặc enrich_context |
| 4 | HSA chỉ tra 1 giá trị, không hỗ trợ so sánh 2 | structured.py:379-391 | Thêm parse `HSA X và HSA Y` |
| 5 | Thiếu validate tổ hợp vs ngành | Không có | Thêm `_validate_tohop_nganh()` trước khi tính |
| 6 | Thiếu KKHT deterministic logic | Không có | Thêm `try_deterministic_kkht()` |
| 7 | Thiếu HB NTB deterministic logic | Không có | Thêm function |
| 8 | Inject chương trình TA thiếu ngành | structured.py:1002-1011 | Bổ sung 10+ ngành TA |
| 9 | Nhiều B1 case tính ĐÚNG nhưng KHÔNG so sánh ĐC | structured.py:666,688 | Luôn gọi `_compare_diem_chuan` khi có `_has_admission_question` |

### 3.2 pipeline.py — Router bugs

| # | Bug | Line | Sửa |
|---|---|---|---|
| 1 | 'đỗ vào các ngành nào'+KV3 không match B1 | L473-476 | KV3=0 nên user không viết KV. Thêm pattern match 'đỗ' without KV |
| 2 | 'có xét được không'+tổ hợp → C thay vì B1 | L375-378 | Thêm exception khi có điểm số cụ thể |
| 3 | 'N năm gần nhất' không match A2 trend | L325-334 | Thêm `\d+\s*năm\s*(gần nhất\|qua\|gần đây)` |
| 4 | 'máy tính' không có trong NGANH_ALIASES | L126-168 | Thêm alias |
| 5 | 'nên đăng ký ngành nào'+chứng chỉ → A2 thay vì D | L468 | Tighten: không match khi có chứng chỉ cụ thể |
| 6 | Điểm sau ưu tiên không match B1 | L471-518 | Thêm pattern `\d+.*điểm.*(sau\|đã).*ưu tiên` |

### 3.3 prompts.py / pipeline.py — Generator issues

| # | Issue | Location | Sửa |
|---|---|---|---|
| 1 | max_tokens D=896 quá nhỏ | pipeline.py:947 | Tăng D→1024, A2→1200 |
| 2 | Thiếu rule so sánh số chặt | prompts.py Section 7 | Thêm: 'PHẢI viết rõ X < Y → KHÔNG ĐẠT' |
| 3 | Thí sinh TN trước → chưa chặt | prompts.py:309 | Strengthen: 'TUYỆT ĐỐI không PT2/4/5' |
| 4 | Hedging thay vì kết luận | prompts.py | Thêm: 'Khi context nói rõ điều kiện → kết luận dứt khoát' |
| 5 | LLM dùng lịch 2025 cho câu hỏi 2026 | enrich_context | Inject lịch 2026 cho tất cả câu hỏi liên quan thời gian |

---
## PHẦN 4: CHI TIẾT 104 CASES CẦN SỬA

### 🔴 CRITICAL (22 cases)

#### A1_37 [CRITICAL]
- **Tags**: FACT_SAI, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 1.55 | **Fact**: 0.0 | **Complete**: 2 | **Faith**: 1
- **Q**: HaUI tuyển sinh năm 2025 bao nhiêu mã ngành và bao nhiêu chỉ tiêu tổng?
- **Bot**: Dựa trên thông tin hiện có từ context, tôi sẽ liệt kê các ngành và chỉ tiêu mà bạn đã yêu cầu: ↵  ↵ - Tài chính - Ngân hàng (mã 7340201): 180 sinh viên ↵ - Công nghệ kỹ thuật hóa học (mã 7510401): 210 sinh viên ↵ - Công nghệ dệt, may (mã 7540204): 180 sinh viên ↵ - Robot và trí tuệ nhân tạo (mã 75102032): 60 sinh viên ↵ - Quản trị kinh doanh (mã 7340101): 300 sinh viên ↵ - Kế toán (mã 7340301): 60...
- **Ground Truth**: Năm 2025, HaUI tuyển sinh 62 mã ngành/chương trình đào tạo với tổng 7.990 chỉ tiêu đại học chính quy, theo 5 phương thức xét tuyển
- **Root Cause**: Answer chứa thông tin SAI so với ground truth. Thiếu nhiều ý quan trọng trong ground truth.

#### B1_15 [CRITICAL]
- **Tags**: FACT_SAI, FAITH_THAP
- **Score**: 3.18 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Em thi ĐGTD được 80 điểm. Quy đổi được bao nhiêu?
- **Bot**: Dựa trên bảng quy đổi điểm Đánh giá tư duy (ĐGTD) ĐHBK Hà Nội, em có thể tra cứu điểm quy đổi tương ứng như sau: ↵  ↵ - Điểm từ 80.0 đến 82.99 sẽ quy đổi thành 29.0 điểm theo thang 30. ↵  ↵ Vì vậy, với kết quả ĐGTD là 80 điểm của bạn, điểm quy đổi tương đương là **29.0** điểm trên thang 30.
- **Ground Truth**: TSA 80.00-82.99 → 29.00 điểm (bảng TSA HaUI; điểm cao nhất dưới 85 là 29.00)
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### B1_25 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 3.15 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 4
- **Q**: PT2: điểm TB học bạ Toán 9.5/Văn 9.2/Anh 9.0, Giải Nhì HSG tỉnh môn Văn, KV2. Tính ĐXT PT2?
- **Bot**: 📊 **Tính điểm xét tuyển PT2 (HaUI):** ↵ - TB Toán = 9.5, TB Văn = 9.2, TB Anh = 9.0 ↵ - Quy đổi ĐKQHT: Toán 9.5→9.55, Văn 9.2→8.25, Anh 9.0→7.23 ↵ - ĐKQHT = (9.55+8.25+7.23)/3 = **8.343** ↵ - Giải Nhì HSG tỉnh → ĐQĐCC = **9.50** ↵ - **ĐXT = 8.343 × 2 + 9.50 = 26.19** ↵ - Ưu tiên KV: **+0.25** ↵ - Vì ĐXT gốc 26.19 ≥ 22.5 → giảm dần: ĐĐT = [(30-26.19)/7.5]×0.25 = **0.13** ↵ → **ĐXT cuối = 26.32** ↵ ...
- **Ground Truth**: KQHB: Toán9.5→9.55, Văn9.2→8.25, Anh9.0→7.23; ĐKQHT=(9.55+8.25+7.23)/3=8.34; ĐQĐCC(Giải Nhì HSG tỉnh)=9.50; ĐXT base=8.34×2+9.50=16.68+9.50=26.18; KV2=0.25; ≥22.5→giảm dần: ĐĐT=[(30-26.18)/7.5]×0.25=(3.82/7.5)×0.25=0.509×0.25=0.13; ĐXT=26.18+0.13=26.31
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### COMPLEX_08 [CRITICAL]
- **Tags**: ROUTER_SAI, FACT_THIEU
- **Score**: 3.84 | **Fact**: 0.33 | **Complete**: 4 | **Faith**: 4
- **Router**: Expected `B1` → Got `A1` ❌
- **Q**: Em được 25.17 điểm sau ưu tiên. Ngành Cơ điện tử HaUI 2025 điểm chuẩn 25.17. Em có đỗ không?
- **Bot**: Dựa trên thông tin từ năm 2025, ngành Công nghệ kỹ thuật cơ điện tử (mã 7510203) của Trường Đại học Công nghiệp Hà Nội có điểm chuẩn là 25.17 điểm (thang 30). Với tổng số điểm sau ưu tiên của em cũng là 25.17 điểm, em sẽ nằm đúng trên ngưỡng điểm chuẩn. ↵  ↵ Tuy nhiên, để chắc chắn hơn, cần xem xét các yếu tố khác như chỉ tiêu tuyển sinh và số lượng thí sinh đăng ký. Nếu có nhiều thí sinh đạt cùng...
- **Ground Truth**: 25.17 = 25.17 điểm chuẩn → ĐỖ (bằng điểm chuẩn là trúng tuyển). Lưu ý: hệ thống xét theo thứ tự nguyện vọng nên cần đặt nguyện vọng 1 vào ngành này để chắc chắn
- **Root Cause**: Router phân loại sai intent (B1→A1).

#### COMPLEX_10 [CRITICAL]
- **Tags**: ROUTER_SAI
- **Score**: 3.95 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 4
- **Router**: Expected `C` → Got `A1` ❌
- **Q**: Em học THPT 2 năm ở KV2 (tỉnh), 1 năm ở KV3 (Hà Nội nội thành). Được hưởng ưu tiên khu vực nào?
- **Bot**: Dựa trên thông tin bạn cung cấp, thí sinh sẽ được hưởng ưu tiên khu vực theo nguyên tắc xác định khu vực tuyển sinh lâu nhất. Vì bạn học THPT 2 năm ở KV2 và chỉ 1 năm ở KV3, nên bạn sẽ được hưởng ưu tiên khu vực KV2 (+0.25 điểm). ↵  ↵ Nếu có thêm thắc mắc khác về ưu đãi hoặc quy định tuyển sinh, hãy cho em biết nhé!
- **Ground Truth**: Khu vực xác định theo trường THPT học LÂU NHẤT: 2 năm KV2 > 1 năm KV3 → hưởng KV2 (+0.25đ). Nếu bằng nhau mới xét trường học SAU CÙNG. Đây là trường hợp học 2 năm KV2 → KV2 (+0.25)
- **Root Cause**: Router phân loại sai intent (C→A1).

#### COMPLEX_11 [CRITICAL]
- **Tags**: ROUTER_SAI, FACT_THIEU, CHUA_DU, SCORE_THAP
- **Score**: 2.86 | **Fact**: 0.33 | **Complete**: 3 | **Faith**: 3
- **Router**: Expected `B1` → Got `A1` ❌
- **Q**: Em thi A01 Toán 9.5, Lý 10, Anh 9.5 (tổng 29). Điểm chuẩn ĐK&TĐH là 26.27. Em đỗ không?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **29.00** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.00** ↵ Vì 29.00 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 29.00) / 7.5] × 0.00 = **0.00** ↵ **ĐXT = 29.00 + 0.00 = 29.00** ↵ → **Điểm xét tuyển ≈ 29.00**. ↵ **So sánh ĐXT 29.00 với điểm chuẩn 2025:** ↵ | Ngành | Mã | ĐC 2025 | Đánh giá | ↵ |---|---|---|---| ↵ | Công nghệ kỹ thuật...
- **Ground Truth**: Tổng=29; KV3 (chưa biết khu vực, giả sử KV3=0); ĐXT=29; 29 >> 26.27 → ĐỖ thoải mái. Nếu có ưu tiên khu vực thì điểm còn cao hơn. Đây là điểm gần tối đa (thang 30)
- **Root Cause**: Router phân loại sai intent (B1→A1).

#### EDGE_02 [CRITICAL]
- **Tags**: FACT_SAI, SCORE_THAP, FAITH_THAP
- **Score**: 2.63 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 1
- **Q**: Điểm chuẩn ngành Trí tuệ nhân tạo HaUI 2025?
- **Bot**: Điểm chuẩn ngành Robot và trí tuệ nhân tạo (mã 75102032) tại Trường Đại học Công nghiệp Hà Nội (HaUI) năm 2025 là 24.3 điểm (thang 30). Phương thức xét tuyển áp dụng cho ngành này bao gồm PT2, PT3 và PT5. ↵  ↵ Nếu bạn cần thêm thông tin về các phương thức khác hoặc có câu hỏi liên quan đến ngành học này, hãy để lại lời nhắn nhé!
- **Ground Truth**: HaUI không có ngành tên 'Trí tuệ nhân tạo' riêng biệt, nhưng có ngành 'Robot và trí tuệ nhân tạo' (mã 75102032, 60CT, ĐC 2025=24.30). Ngoài ra KHMT và CNTT cũng có học phần AI
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### EDGE_03 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 3.15 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 4
- **Q**: Em có điểm TOEFL iBT 65. Đây là loại chứng chỉ gì và quy đổi bao nhiêu trong PT2?
- **Bot**: 📊 **Quy đổi TOEFL iBT → ĐQĐCC (PT2):** ↵ - Điểm TOEFL iBT: **65** ↵ - TOEFL iBT 65–79 → tương đương IELTS 6.0 ↵ - ĐQĐCC (điểm quy đổi chứng chỉ): **9.5** (thang 10) ↵ - TOEFL iBT là bài thi tiếng Anh quốc tế (Test of English as a Foreign Language, Internet-Based Test) do ETS tổ chức. ↵ → Điểm này sẽ cộng vào công thức PT2: ĐXT = ĐKQHT × 2 + ĐQĐCC + Điểm ưu tiên. ↵ Anh/chị cần tính ĐXT đầy đủ không
- **Ground Truth**: TOEFL iBT 65 thuộc nhóm 61-70 → ĐQĐCC = 9.50 điểm (tương đương IELTS 6.0). Điều kiện thỏa mãn để xét PT2 (yêu cầu TOEFL iBT ≥ 50)
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### EDGE_04 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 4.15 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 5
- **Q**: Điểm chuẩn Ngôn ngữ Trung Quốc liên kết 2+2 HaUI 2025?
- **Bot**: Điểm chuẩn cho ngành Ngôn ngữ Trung Quốc chương trình liên kết đào tạo 2+2 với ĐH Khoa học Kỹ thuật Quảng Tây - Trung Quốc (mã 7220204LK) của Trường Đại học Công nghiệp Hà Nội năm 2025 là 22.5 điểm (thang 30). Phương thức xét tuyển áp dụng cho ngành này là PT2 và PT3. ↵  ↵ Nếu bạn cần thêm thông tin về các phương thức khác hoặc có câu hỏi liên quan, hãy để lại lời nhắn nhé!
- **Ground Truth**: Ngôn ngữ Trung Quốc LK 2+2 với ĐH Quảng Tây (7220204LK, 30CT, PT2+PT3): điểm chuẩn 2025 = 22.50 điểm. So với Ngôn ngữ TQ thường (23.00) thì LK 2+2 thấp hơn 0.5đ nhưng học phí và điều kiện khác
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### EDGE_05 [CRITICAL]
- **Tags**: FACT_SAI, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.48 | **Fact**: 0.0 | **Complete**: 2 | **Faith**: 2
- **Q**: Em học THPT ở quận Ba Đình (nội thành Hà Nội). Được ưu tiên khu vực nào?
- **Bot**: Theo quy định tuyển sinh, bạn thuộc khu vực KV2 vì bạn học THPT tại một quận nội thành của Hà Nội. Mức điểm ưu tiên cho khu vực KV2 là +0.25 điểm trong quá trình xét tuyển đại học năm 2026. ↵  ↵ Nếu bạn cần thêm thông tin về ưu đãi khác hoặc có câu hỏi liên quan, hãy để lại lời nhắn nhé!
- **Ground Truth**: Quận Ba Đình là phường thuộc thành phố trực thuộc Trung ương (Hà Nội nội thành) → KV3 (0 điểm ưu tiên). Chỉ KV1, KV2-NT, KV2 mới được cộng điểm ưu tiên khu vực
- **Root Cause**: Answer chứa thông tin SAI so với ground truth. Thiếu nhiều ý quan trọng trong ground truth.

#### EDGE_08 [CRITICAL]
- **Tags**: FACT_SAI, THIEU_Y
- **Score**: 3.05 | **Fact**: 0.0 | **Complete**: 2 | **Faith**: 4
- **Q**: Sinh viên Kỹ thuật phần mềm muốn lấy bằng Kỹ sư. Phải học thêm gì?
- **Bot**: Người tốt nghiệp đại học (bằng cử nhân) tại HaUI có thể dự tuyển vào các chương trình đào tạo chuyên sâu đặc thù để lấy **bằng kỹ sư** theo thông báo tuyển sinh riêng của Trường. Đối với sinh viên ngành Kỹ thuật phần mềm muốn lấy bằng Kỹ sư, bạn cần tham khảo thêm thông tin về các chương trình đào tạo chuyên sâu dành cho ngành này từ văn phòng tuyển sinh hoặc trang web chính thức của trường để biế...
- **Ground Truth**: Sau khi tốt nghiệp Cử nhân KTPM, có thể dự tuyển chương trình đào tạo chuyên sâu đặc thù bậc 7 (Kỹ sư). Lịch 2026: thông báo trước 01/5/2026; đăng ký 15/6-15/7/2026; khai giảng từ 03/8/2026; chỉ tiêu 120 SV; học phí 700k/TC (đại trà K3)
- **Root Cause**: Answer chứa thông tin SAI so với ground truth. Thiếu nhiều ý quan trọng trong ground truth.

#### EDGE_12 [CRITICAL]
- **Tags**: FACT_SAI, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.32 | **Fact**: 0.0 | **Complete**: 2 | **Faith**: 2
- **Q**: SAT 1050 điểm quy đổi bao nhiêu trong PT2 HaUI?
- **Bot**: Để tính điểm xét tuyển cho phương thức 2 (PT2) tại HaUI với kết quả SAT, bạn cần sử dụng bảng quy đổi điểm từ SAT sang thang 30. Theo thông tin đã cung cấp: ↵  ↵ - SAT từ 1000 đến 1100 tương ứng với điểm quy đổi là 9.50. ↵ - SAT từ 1101 đến 1200 tương ứng với điểm quy đổi là 10.00. ↵  ↵ Với SAT 1050, nằm trong khoảng từ 1000 đến 1100 nên được quy đổi thành 9.50 theo bảng quy đổi của HaUI. ↵  ↵ Tiế...
- **Ground Truth**: SAT 1000-1100 → ĐQĐCC = 9.00 điểm (bảng quy đổi HaUI). SAT ≥ 1000 đủ điều kiện tham gia PT2 (ngưỡng tối thiểu SAT ≥ 1000). SAT 1050 thuộc khoảng 1000-1100 → 9.00
- **Root Cause**: Answer chứa thông tin SAI so với ground truth. Thiếu nhiều ý quan trọng trong ground truth.

#### EDGE_13 [CRITICAL]
- **Tags**: ROUTER_SAI, FACT_THIEU
- **Score**: 3.85 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 4
- **Router**: Expected `A2` → Got `A1` ❌
- **Q**: Điểm chuẩn ngành 'máy tính' HaUI 2025 là bao nhiêu?
- **Bot**: Ngành "Mạng máy tính và truyền thông dữ liệu" (mã 7480102) và "Hệ thống thông tin" (mã 7480104) thuộc nhóm ngành CNTT mà bạn có thể đang hỏi. Tuy nhiên, nếu bạn muốn biết điểm chuẩn của ngành Khoa học máy tính (mã 7480101), năm 2025 điểm chuẩn chung cho phương thức PT2, PT3 và PT5 là 23.72 điểm (thang 30). ↵  ↵ Nếu bạn cần thông tin cụ thể về một ngành khác trong nhóm CNTT hoặc có thêm câu hỏi liê...
- **Ground Truth**: Có 3 ngành liên quan 'máy tính' năm 2025: Khoa học máy tính (23.72), Công nghệ kỹ thuật máy tính (21.85), và CNTT (23.09) cũng liên quan. Cần xác định ngành cụ thể để tra điểm chính xác
- **Root Cause**: Router phân loại sai intent (A2→A1).

#### MULTI_01 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 3.83 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 4
- **Q**: Em được HSA 95, KV1. Tính điểm rồi cho em biết có đỗ CNTT HaUI 2025 không?
- **Bot**: 📊 **Quy đổi & tính ĐXT (tham khảo PT5 + ưu tiên):** ↵ - HSA 95 → thang 30: **23.5** ↵ Tổng điểm 3 môn (thang 30): **23.50** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.75** ↵ Vì 23.50 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 23.50) / 7.5] × 0.75 = **0.65** ↵ **ĐXT = 23.50 + 0.65 = 24.15** ↵ → **ĐXT ≈ 24.15**. ↵ Điểm chuẩn **Công nghệ thông tin** (7480201) năm **2025** = **23.09**. Với ĐXT **...
- **Ground Truth**: B1:HSA95→23.50; B2:≥22.5→giảm dần; KV1=0.75; ĐĐT=[(30-23.50)/7.5]×0.75=(6.5/7.5)×0.75=0.8667×0.75=0.65; B3:ĐXT=23.50+0.65=24.15; B4:ĐC CNTT2025=23.09; 24.15>23.09 → ĐỖ
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### MULTI_03 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 3.29 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 4
- **Q**: TSA 65.5, KV2. Tính điểm rồi xem có đỗ ngành Điều khiển tự động hóa không?
- **Bot**: 📊 **Tính điểm xét tuyển từ TSA (tham khảo PT5 + ưu tiên):** ↵ - Điểm TSA **65.5** → quy đổi thang 30: **26.75** ↵ Tổng điểm 3 môn (thang 30): **26.75** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.25** ↵ Vì 26.75 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 26.75) / 7.5] × 0.25 = **0.11** ↵ **ĐXT = 26.75 + 0.11 = 26.86** ↵ → **Điểm xét tuyển ≈ 26.86**. ↵ Điểm chuẩn **CN KT ĐK và TĐH** (7510303) n...
- **Ground Truth**: TSA65.5→khoảng 65.00-65.99→26.75; ≥22.5→giảm dần; KV2=0.25; ĐĐT=[(30-26.75)/7.5]×0.25=(3.25/7.5)×0.25=0.433×0.25=0.11; ĐXT=26.75+0.11=26.86; ĐC ĐK&TĐH 2025=26.27; 26.86>26.27 → ĐỖ (câu hỏi trong đề hỏi dưới dạng mặc định 'trượt' để test khả năng tính đúng của bot)
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### MULTI_09 [CRITICAL]
- **Tags**: ROUTER_SAI, FACT_THIEU, CHUA_DU, SCORE_THAP, FAITH_THAP
- **Score**: 2.34 | **Fact**: 0.5 | **Complete**: 3 | **Faith**: 2
- **Router**: Expected `B1` → Got `A2` ❌
- **Q**: Em điểm A01 là Toán 8.5, Lý 8.0, Anh 8.5 (tổng 25), KV3. Có đỗ vào các ngành nào của HaUI?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **25.00** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.00** ↵ Vì 25.00 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 25.00) / 7.5] × 0.00 = **0.00** ↵ **ĐXT = 25.00 + 0.00 = 25.00** ↵ → **Điểm xét tuyển ≈ 25.00**. ↵ **So sánh ĐXT 25.00 với điểm chuẩn 2025:** ↵ | Ngành | Mã | ĐC 2025 | Đánh giá | ↵ |---|---|---|---| ↵ | Công nghệ kỹ thuật...
- **Ground Truth**: ĐXT=25.0 (KV3=0, không cộng); So với ĐC 2025: đỗ CNTT(23.09), KTPM(21.75), KHMT(23.72), HTTT(21.10), MMT(21.70), KTMT(21.85), ATTT(23.43), CNKT cơ khí(23.72), Điện-điện tử(23.93), Robot&TTNT(24.30); TRƯỢT: CĐT(25.17), ĐK&TĐH(26.27)
- **Root Cause**: Router phân loại sai intent (B1→A2).

#### MULTI_15 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 3.29 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 4
- **Q**: Tổng 24 điểm, KV2-NT, đối tượng 04 (quân nhân xuất ngũ UT2). Tính ĐXT rồi xem có đỗ Robot & TTNT không?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **24.00** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+1.50** ↵ Vì 24.00 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 24.00) / 7.5] × 1.50 = **1.20** ↵ **ĐXT = 24.00 + 1.20 = 25.20** ↵ → **ĐXT ≈ 25.20**. ↵ Anh/chị cần so sánh thêm ngành khác không ạ?
- **Ground Truth**: Tổng=24; ≥22.5→giảm dần; KV2-NT=0.50, ĐT04 thuộc UT2=1.00, tổng ưu tiên=1.50; ĐĐT=[(30-24)/7.5]×1.50=(6/7.5)×1.50=0.80×1.50=1.20; ĐXT=24+1.20=25.20; ĐC Robot 2025=24.30; 25.20>24.30 → ĐỖ
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### MULTI_17 [CRITICAL]
- **Tags**: FACT_SAI, SCORE_THAP, FAITH_THAP
- **Score**: 2.72 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Em được HSA 93, KV3. Có đỗ ngành Điều khiển tự động hóa 2025 không?
- **Bot**: 📊 **Quy đổi & tính ĐXT (tham khảo PT5 + ưu tiên):** ↵ - HSA 93 → thang 30: **23.01** ↵ Tổng điểm 3 môn (thang 30): **23.01** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.00** ↵ Vì 23.01 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 23.01) / 7.5] × 0.00 = **0.00** ↵ **ĐXT = 23.01 + 0.00 = 23.01** ↵ → **ĐXT ≈ 23.01**. ↵ Điểm chuẩn **CN KT ĐK và TĐH** (7510303) năm **2025** = **26.27**. Với ĐXT **23....
- **Ground Truth**: HSA93→23.01; KV3=0 điểm ưu tiên; ĐXT=23.01; ĐC ĐK&TĐH 2025=26.27; 23.01 << 26.27 → TRƯỢT (thiếu hơn 3 điểm). Cần xem xét ngành khác phù hợp hơn với điểm HSA 93
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### MULTI_20 [CRITICAL]
- **Tags**: ROUTER_SAI, FACT_SAI, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 1.72 | **Fact**: 0.0 | **Complete**: 2 | **Faith**: 2
- **Router**: Expected `B1` → Got `C` ❌
- **Q**: Toán 8.0, Hóa 7.5, Anh 7.5 (tổng 23), KV2, tổ hợp A01. Nhưng ngành Công nghệ kỹ thuật hóa học chỉ dùng tổ hợp A00/B00/C02/D07. Có xét được không?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **23.00** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.25** ↵ Vì 23.00 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 23.00) / 7.5] × 0.25 = **0.23** ↵ **ĐXT = 23.00 + 0.23 = 23.23** ↵ → **Điểm xét tuyển ≈ 23.23**. ↵ Anh/chị muốn đối chiếu với điểm chuẩn ngành nào ạ?
- **Ground Truth**: Tổ hợp A01 (Toán-Lý-Anh) KHÔNG có trong danh sách tổ hợp xét tuyển ngành CNKT Hóa học (7510401) – chỉ có A00, B00, C02, D07. Dù điểm 23+0.25=23.25 > ĐC(20.25) nhưng tổ hợp không phù hợp → không được xét
- **Root Cause**: Router phân loại sai intent (B1→C). Answer chứa thông tin SAI so với ground truth. Thiếu nhiều ý quan trọng trong ground truth.

#### MULTI_22 [CRITICAL]
- **Tags**: FACT_SAI
- **Score**: 3.39 | **Fact**: 0.0 | **Complete**: 4 | **Faith**: 4
- **Q**: HSA 85 điểm, KV3. Tính điểm và có đỗ CNTT HaUI 2025 không?
- **Bot**: 📊 **Quy đổi & tính ĐXT (tham khảo PT5 + ưu tiên):** ↵ - HSA 85 → thang 30: **21.75** ↵ Tổng điểm 3 môn (thang 30): **21.75** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.00** ↵ Vì 21.75 < 22.5 → cộng thẳng ưu tiên: **ĐXT = 21.75 + 0.00 = 21.75** ↵ → **ĐXT ≈ 21.75**. ↵ Điểm chuẩn **Công nghệ thông tin** (7480201) năm **2025** = **23.09**. Với ĐXT **21.75 < 23.09** → **chưa đủ so với điểm chuẩn 20...
- **Ground Truth**: HSA85→21.75; KV3=0 điểm ưu tiên; ĐXT=21.75; ĐC CNTT 2025=23.09; 21.75 < 23.09 → TRƯỢT (thiếu 1.34 điểm). Có thể xét các ngành dễ vào hơn như KTPM(21.75-sát ngưỡng), HTTT(21.10), MMT(21.70)
- **Root Cause**: Answer chứa thông tin SAI so với ground truth.

#### STRAT_09 [CRITICAL]
- **Tags**: ROUTER_SAI, FACT_THIEU, CHUA_DU
- **Score**: 3.75 | **Fact**: 0.83 | **Complete**: 3 | **Faith**: 4
- **Router**: Expected `D` → Got `A2` ❌
- **Q**: Em giỏi tiếng Nhật (JLPT N2), điểm D06 (Toán-Văn-Nhật) khoảng 22 điểm, KV2. Nên đăng ký ngành nào HaUI?
- **Bot**: Dựa trên thông tin bạn cung cấp, em sẽ gợi ý một số ngành phù hợp với khả năng tiếng Nhật và tổ hợp xét tuyển của bạn tại HaUI: ↵  ↵ 1. **Ngôn ngữ Nhật (mã 7220209)** ↵    - Điểm chuẩn năm 2025: 20.0 điểm ↵    - Chỉ tiêu 2025: 70 sinh viên ↵    - Tổ hợp xét tuyển: D06 (Toán-Ngữ văn-Tiếng Nhật) ↵     ↵    Với tổng điểm khoảng 22 và đã có chứng chỉ JLPT N2, bạn hoàn toàn có cơ hội để đăng ký ngành n...
- **Ground Truth**: ĐXT= 22+0.25=22.25 (KV2, <22.5 cộng thẳng); Ngôn ngữ Nhật (7220209, 70CT, ĐC2025=20.00) nhận D06 ✓ → 22.25>20.00 ĐỖ. Với JLPT N2 cũng đủ xét PT2 (N3+ là điều kiện) → ĐQĐCC=10.00; Khuyến nghị: xét cả PT2 và PT3, ưu tiên Ngôn ngữ Nhật là lựa chọn hàng đầu
- **Root Cause**: Router phân loại sai intent (D→A2).

#### TREND_03 [CRITICAL]
- **Tags**: ROUTER_SAI
- **Score**: 4.35 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 5
- **Router**: Expected `A2` → Got `A1` ❌
- **Q**: Ngành Điều khiển và tự động hóa điểm chuẩn 3 năm gần nhất diễn biến như thế nào?
- **Bot**: Dựa trên thông tin được cung cấp, đây là điểm chuẩn cho ngành Điều khiển và Tự động hóa (mã 7510303) trong 3 năm gần nhất: ↵  ↵ - **Năm 2025:** 26.27 điểm (thang 30) ↵ - **Năm 2024:** ↵   - PT3 (THPT): 26.05 điểm ↵   - PT4 (Học bạ): 28.97 điểm ↵   - PT2 (Chung chi HSG): 27.0 điểm ↵   - PT5 (Đánh giá năng lực): 19.01 điểm ↵  ↵ - **Năm 2023:** ↵   - PT3 (THPT): 25.47 điểm ↵   - PT4 (Học bạ): 28.94 đ...
- **Ground Truth**: ĐK&TĐH (7510303): 2023 PT3=25.47, PT4=28.94; 2024 PT3=26.05, PT4=28.97; 2025 chung=26.27. Ngành này liên tục tăng điểm chuẩn qua các năm, đặc biệt PT3 tăng từ 25.47→26.05→26.27, là ngành khó nhất vào nhóm kỹ thuật HaUI
- **Root Cause**: Router phân loại sai intent (A2→A1).

### 🟠 MAJOR (49 cases)

#### A1_36 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y
- **Score**: 3.4 | **Fact**: 0.4 | **Complete**: 2 | **Faith**: 4
- **Q**: Khi nhập học HaUI cần thanh toán qua ngân hàng nào?
- **Bot**: Khi nộp lệ phí dự tuyển vào Đại học Công nghiệp Hà Nội (HaUI), bạn có thể sử dụng nhiều ngân hàng khác nhau để thực hiện giao dịch. Cụ thể, bạn chọn một trong các ngân hàng được hỗ trợ, quét mã QR qua ứng dụng ngân hàng của họ và hoàn tất quá trình thanh toán. ↵  ↵ Dưới đây là hướng dẫn chi tiết: ↵  ↵ 1. Chọn 1 trong các ngân hàng hỗ trợ. ↵ 2. Quét mã QR thông qua ứng dụng ngân hàng. ↵ 3. Kiểm tra...
- **Ground Truth**: Thanh toán học phí khi nhập học qua QR Ngân hàng BIDV hoặc QR Ngân hàng Lộc Phát. Thẻ sinh viên K20 tích hợp thẻ ATM Vietinbank
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_02 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.35 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Liệt kê các ngành Cơ khí HaUI và điểm chuẩn 2025?
- **Bot**: Dựa trên dữ liệu hiện có, đây là danh sách các ngành thuộc nhóm Cơ khí tại Trường Đại học Công nghiệp Hà Nội (HaUI) cùng với điểm chuẩn năm 2025: ↵  ↵ | Ngành | Mã | Điểm chuẩn 2025 | ↵ |---|---:|---:| ↵ | Công nghệ kỹ thuật điều khiển và tự động hóa | 7510303 | 26.27 | ↵ | Công nghệ kỹ thuật cơ điện tử | 7510203 | 25.17 | ↵ | Robot và trí tuệ nhân tạo | 75102032 | 24.30 | ↵ | Công nghệ kỹ thuật c...
- **Ground Truth**: Nhóm Cơ khí 2025: CĐT(25.17), ĐK&TĐH(26.27), CNKT ô tô(22.50), CNKT cơ khí(23.72), Robot(24.30), CĐT ô tô(23.93), Điện-điện tử(23.93), ĐT-VT(22.75), Nhiệt(21.85), NLTT(20.75), KTSXTM(22.50), y sinh(20.60)...
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_04 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y
- **Score**: 4.08 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 5
- **Q**: Top 5 ngành có điểm chuẩn cao nhất HaUI năm 2025?
- **Bot**: **Top 5 ngành có điểm chuẩn cao nhất tại Trường Đại học Công nghiệp Hà Nội (HaUI) năm 2025 là:** ↵  ↵ | Ngành | Mã | ĐC 2025 | ↵ |---|---|---| ↵ | Công nghệ kỹ thuật điều khiển và tự động hóa | 7510303 | 26.27 | ↵ | Công nghệ kỹ thuật cơ điện tử | 7510203 | 25.17 | ↵ | Robot và trí tuệ nhân tạo | 75102032 | 24.30 | ↵ | Khoa học máy tính | 7480101 | 23.72 | ↵ | An toàn thông tin | 74802021 | 23.43 ...
- **Ground Truth**: Top 5 ngành điểm cao nhất 2025: 1.ĐK&TĐH (26.27), 2.Cơ điện tử (25.17), 3.Robot&TTNT (24.30), 4.Cơ điện tử ô tô (23.93), 5.Điện-điện tử (23.93) / KHMT (23.72) / CNKT cơ khí (23.72)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_05 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.88 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Những ngành nào ở HaUI có thể xét tổ hợp A00 (Toán-Lý-Hóa)?
- **Bot**: Dựa trên thông tin hiện có, các ngành tại Trường Đại học Công nghiệp Hà Nội (HaUI) có thể xét tuyển với tổ hợp môn A00 (Toán - Vật lý - Hóa học) bao gồm: ↵  ↵ **Nhóm ngành Cơ khí:** ↵ 1. Công nghệ kỹ thuật điện, điện tử (mã 7510301) ↵ 2. Công nghệ kỹ thuật điện tử - viễn thông (mã 7510302) ↵ 3. Công nghệ kỹ thuật điều khiển và tự động hóa (mã 7510303) ↵ 4. Công nghệ kỹ thuật cơ điện tử (mã 7510203...
- **Ground Truth**: Tổ hợp A00 dùng được cho nhóm CNTT (CNTT, KTPM, KHMT, HTTT, ATTT...) và Cơ khí (cơ điện tử, ô tô, điện...) và Hóa học (CN Hóa, Hóa dược, Môi trường, Thực phẩm)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_07 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.78 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 1
- **Q**: Các ngành nào có chỉ tiêu lớn nhất ở HaUI 2025?
- **Bot**: Dựa trên dữ liệu hiện có từ năm 2025, các ngành có chỉ tiêu tuyển sinh lớn nhất tại Trường Đại học Công nghiệp Hà Nội (HaUI) là: ↵  ↵ **1. Kế toán (mã 7340301):** ↵ - Chỉ tiêu: 600 sinh viên ↵ - Tổ hợp xét tuyển: A01, D01, X25 ↵ - Phương thức: PT1, PT2, PT3, PT4 ↵  ↵ **2. Quản trị kinh doanh (mã 7340101):** ↵ - Chỉ tiêu: 300 sinh viên ↵ - Tổ hợp xét tuyển: A01, D01, X25 ↵ - Phương thức: PT1, PT2, ...
- **Ground Truth**: Top chỉ tiêu lớn nhất 2025: Kế toán (600), CNKT ô tô (360), CNTT (360), CNKT cơ khí (360), CNKT điện-điện tử (420), CNKT điện tử-viễn thông (480), QTKD (300), Cơ điện tử (300)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_08 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, FAITH_THAP
- **Score**: 3.33 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Các phương thức tuyển sinh HaUI 2025 là gì?
- **Bot**: **Các phương thức tuyển sinh đại học chính quy tại Trường Đại học Công nghiệp Hà Nội (HaUI) năm 2025 bao gồm:**  ↵  ↵ 1. **Phương thức 1**: Xét tuyển thẳng cho các đối tượng ưu tiên theo Quyết định của Bộ Giáo dục và Đào tạo. ↵ 2. **Phương thức 2**: Xét tuyển thí sinh đoạt giải HSG cấp tỉnh/TP hoặc có chứng chỉ quốc tế. ↵ 3. **Phương thức 3**: Xét tuyển dựa trên kết quả thi tốt nghiệp THPT năm 202...
- **Ground Truth**: HaUI 2025 có 5 phương thức: PT1 (xét thẳng), PT2 (HSG/chứng chỉ quốc tế + học bạ), PT3 (thi TN THPT), PT4 (ĐGNL ĐHQG HN), PT5 (ĐGTD ĐHBK HN). Tổng 7.990 chỉ tiêu, 62 mã ngành
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_11 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y
- **Score**: 3.86 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 5
- **Q**: Các ngành nào ở HaUI có chương trình đào tạo bằng tiếng Anh?
- **Bot**: Dựa trên thông tin hiện có, các ngành có chương trình đào tạo bằng Tiếng Anh tại Trường Đại học Công nghiệp Hà Nội (HaUI) năm 2025 bao gồm: ↵  ↵ 1. **Công nghệ thông tin** - Mã ngành: 7480201 ↵ 2. **Kỹ thuật phần mềm** - Mã ngành: 7480103 ↵ 3. **Quản trị kinh doanh** - Mã ngành: 7340101 ↵ 4. **Kế toán** - Mã ngành: 7340301 ↵  ↵ Đơn giá tín chỉ cho các chương trình đào tạo bằng Tiếng Anh là **1.000...
- **Ground Truth**: Chương trình TA: Khoa học máy tính-TA, CNKT cơ khí-TA, CNKT ô tô-TA, CNKT điện-điện tử-TA, CNKT ĐT-VT-TA, Kế toán-TA, Du lịch-TA, QT lữ hành-TA, QT khách sạn-TA, QT nhà hàng-TA; học phí 1.000.000đ/TC
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### A2_13 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.91 | **Fact**: 0.5 | **Complete**: 1 | **Faith**: 2
- **Q**: Những ngành kinh tế HaUI có dùng phương thức PT5 (ĐGTD Bách Khoa) không?
- **Bot**: **Dựa trên thông tin hiện có, các ngành kinh tế tại HaUI áp dụng phương thức xét tuyển PT5 (Đánh giá năng lực Đại học Bách Khoa Hà Nội) trong năm 2025. Cụ thể:** ↵  ↵ - **Logistics và quản lý chuỗi cung ứng** (mã 7510605): Điểm chuẩn chung cho PT2, PT3, PT4, PT5 là 22.76 điểm. ↵ - **Tài chính – Ngân hàng** (mã 7340201): Điểm chuẩn chung cho PT2, PT3, PT4, PT5 là 20.75 điểm. ↵ - **Quản trị kinh doa...
- **Ground Truth**: Các ngành kinh tế HaUI (Kế toán, QTKD, Marketing, Tài chính-NH, Kiểm toán, QT nhân lực, QT văn phòng, KT đầu tư, Logistics, Phân tích DLKD) KHÔNG áp dụng PT5 (ĐGTD ĐHBK). Các ngành này chỉ dùng PT1/PT2/PT3/PT4 (ĐGNL ĐHQG HN). PT5 chỉ dùng cho khối kỹ thuật và CNTT
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### B1_22 [MAJOR]
- **Tags**: SCORE_THAP, FAITH_THAP
- **Score**: 2.83 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 1
- **Q**: Điểm TB học bạ 3 năm môn Tiếng Anh là 9.4. KQHB quy đổi bao nhiêu?
- **Bot**: Dựa trên bảng quy đổi điểm kết quả học bạ (KQHB) mà em có, điểm trung bình 3 năm môn Tiếng Anh của bạn là 9.4 sẽ được quy đổi thành: ↵  ↵ **Điểm quy đổi:** 9.40 → 9.26 ↵  ↵ Nếu bạn cần hỗ trợ thêm về cách tính điểm xét tuyển hoặc tư vấn ngành học phù hợp, hãy cho em biết nhé!
- **Ground Truth**: KQHB 9.40-9.49 → 9.26 điểm (bảng KQHB; lưu ý các mức khác nhau rõ rệt: 9.30→8.75, 9.40→9.26)
- **Root Cause**: Answer không faithful với context.

#### B1_26 [MAJOR]
- **Tags**: SCORE_THAP, FAITH_THAP
- **Score**: 2.85 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: ĐGNL HSA 100 điểm, KV2-NT, không có đối tượng. Tính ĐXT PT4?
- **Bot**: 📊 **Quy đổi & tính ĐXT (tham khảo PT5 + ưu tiên):** ↵ - HSA 100 → thang 30: **24.25** ↵ Tổng điểm 3 môn (thang 30): **24.25** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.50** ↵ Vì 24.25 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 24.25) / 7.5] × 0.50 = **0.38** ↵ **ĐXT = 24.25 + 0.38 = 24.63** ↵ → **ĐXT ≈ 24.63**. ↵ Anh/chị cần tư vấn thêm ngành khác không ạ?
- **Ground Truth**: HSA100→24.25; ≥22.5→giảm dần; KV2-NT=0.50; ĐĐT=[(30-24.25)/7.5]×0.50=(5.75/7.5)×0.50=0.383≈0.38; ĐXT=24.25+0.38=24.63
- **Root Cause**: Answer không faithful với context.

#### B1_30 [MAJOR]
- **Tags**: FACT_THIEU, SCORE_THAP, FAITH_THAP
- **Score**: 2.07 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 2
- **Q**: Tổng 31 điểm 3 môn, KV1. Tính điểm xét tuyển?
- **Bot**: ⚠️ Tổng điểm vượt quá 30 (thang 30). Vui lòng kiểm tra lại.
- **Ground Truth**: Phát hiện tổng 31 > 30 (thang 30 tối đa 30 điểm). Dữ liệu đầu vào không hợp lệ, cảnh báo và yêu cầu kiểm tra lại điểm từng môn
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### COMPLEX_02 [MAJOR]
- **Tags**: SCORE_THAP, FAITH_THAP
- **Score**: 2.92 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Em chỉ thi tổ hợp A00 (Toán-Lý-Hóa). Có thể vào ngành Kế toán hay Marketing HaUI không?
- **Bot**: Dựa trên thông tin hiện có, cả hai ngành Kế toán và Marketing tại Trường Đại học Công nghiệp Hà Nội đều yêu cầu tổ hợp xét tuyển là A01 (Toán-Vật lý-Tiếng Anh), D01 (Toán-Ngữ văn-Tiếng Anh) hoặc X25 (Toán-Tiếng Anh-GDKT pháp luật). Ngành Kế toán cũng có phiên bản tiếng Anh với tổ hợp tương tự. ↵  ↵ Do đó, nếu bạn chỉ thi tổ hợp A00 (Toán-Lý-Hóa), bạn sẽ không đủ điều kiện xét tuyển vào hai ngành n...
- **Ground Truth**: KHÔNG. Các ngành kinh tế HaUI (Kế toán, Marketing, QTKD…) chỉ nhận tổ hợp A01, D01, X25. Tổ hợp A00 (Toán-Lý-Hóa) không có trong danh sách. Khuyến nghị: thi A01 (Toán-Lý-Anh) hoặc D01 (Toán-Văn-Anh) nếu muốn ngành kinh tế
- **Root Cause**: Answer không faithful với context.

#### COMPLEX_03 [MAJOR]
- **Tags**: FACT_THIEU, CHUA_DU, SCORE_THAP
- **Score**: 2.64 | **Fact**: 0.5 | **Complete**: 3 | **Faith**: 3
- **Q**: Em muốn vào Ngôn ngữ Anh HaUI nhưng điểm Văn rất yếu. Có tổ hợp nào không cần Văn không?
- **Bot**: Dựa trên thông tin hiện có, ngành Ngôn ngữ Anh (mã 7220201) tại Trường Đại học Công nghiệp Hà Nội chỉ áp dụng tổ hợp D01 bao gồm Toán - Ngữ văn - Tiếng Anh. Hiện không có tổ hợp nào không yêu cầu môn Ngữ văn. ↵  ↵ Nếu bạn gặp khó khăn với môn Văn, có thể tham khảo các ngành khác trong nhóm Ngôn ngữ hoặc Du lịch cũng sử dụng tiếng Anh nhưng có nhiều lựa chọn tổ hợp hơn: ↵  ↵ - Ngôn ngữ Trung Quốc (...
- **Ground Truth**: Ngành Ngôn ngữ Anh (7220201) CHỈ có 1 tổ hợp duy nhất là D01 (Toán-Văn-Tiếng Anh). Không có tổ hợp nào bỏ Văn. Cần cải thiện điểm Văn để đạt điểm xét tuyển ≥ 21.35 (ĐC 2025)
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### COMPLEX_04 [MAJOR]
- **Tags**: FACT_THIEU, SCORE_THAP, FAITH_THAP
- **Score**: 2.9 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 2
- **Q**: Điểm chuẩn CNTT HaUI 2026 dự kiến bao nhiêu?
- **Bot**: Điểm chuẩn năm 2026 chưa được công bố (thường công bố sau kỳ thi THPT quốc gia vào tháng 8). Anh/chị có thể tham khảo điểm chuẩn năm 2025 để định hướng. Điểm chuẩn CNTT của HaUI năm 2025 là: ↵  ↵ - Công nghệ thông tin (mã 7480201): 23.09 điểm ↵ - Khoa học máy tính (mã 7480101): 23.72 điểm ↵ - Hệ thống thông tin (mã 7480104): 21.1 điểm ↵ - Công nghệ kỹ thuật máy tính (mã 7480108): 21.85 điểm ↵ - Kỹ...
- **Ground Truth**: Điểm chuẩn 2026 CHƯA công bố (thường công bố sau khi có kết quả thi THPT tháng 7/2026). Tham khảo điểm chuẩn năm gần nhất: 2025 là 23.09; 2024 PT3 là 25.22. Theo dõi tại tuyensinh.haui.edu.vn
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### COMPLEX_06 [MAJOR]
- **Tags**: THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.9 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 2
- **Q**: SV đang được miễn giảm học phí theo chính sách Nhà nước (dân tộc nghèo). Có được xét học bổng Nguyễn Thanh Bình không?
- **Bot**: Bạn có thể được xét học bổng Nguyễn Thanh Bình nếu đáp ứng đủ các điều kiện của học bổng này, nhưng cần lưu ý rằng việc đang nhận hỗ trợ tài chính từ chính sách Nhà nước (như miễn giảm học phí cho đối tượng dân tộc thiểu số nghèo) có thể ảnh hưởng đến khả năng nhận một số loại học bổng khác. Học bổng Nguyễn Thanh Bình có các điều kiện cụ thể mà bạn cần phải thỏa mãn, bao gồm thành tích học tập và ...
- **Ground Truth**: KHÔNG. Theo quy định HB Nguyễn Thanh Bình: SV đã được miễn giảm học phí theo Nhà nước KHÔNG được xét (trừ SV khuyết tật). Ngoài ra: SV nhận HB HaUI toàn khóa, HB năm 1, HB KKHT, HB tài trợ ≥ mức NTB cũng không được xét
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### COMPLEX_07 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP
- **Score**: 2.95 | **Fact**: 0.6 | **Complete**: 2 | **Faith**: 3
- **Q**: SV mồ côi bố (đối tượng 2.1.3), TBC năm = 2.1 (tín chỉ), 28TC. Có đủ tiêu chuẩn HB Nguyễn Thanh Bình không?
- **Bot**: Dựa trên thông tin từ học bổng HaUI, sinh viên thuộc đối tượng mồ côi bố (đối tượng 2.1.3) cần đáp ứng các điều kiện sau để được xét học bổng Nguyễn Thanh Bình: ↵  ↵ - Điểm TBC năm học ≥ 2.0 (tín chỉ) ↵ - Tổng tín chỉ năm học ≥ 25 tín chỉ ↵ - Không có học phần < 1.0 (tín chỉ) ↵  ↵ Trong trường hợp của bạn: ↵ - Điểm TBC năm học = 2.1 (tín chỉ) → Đủ điều kiện. ↵ - Tổng tín chỉ năm học = 28TC → Đủ đi...
- **Ground Truth**: Đối tượng 2.1.3 (mồ côi bố/mẹ): điểm TBC tối thiểu ≥ 2.0 ✓ (2.1≥2.0); rèn luyện Khá trở lên (cần kiểm tra); không có HP < 1.0 (cần kiểm tra); tổng TC ≥ 30 nhưng hiện 28TC < 30TC ✗. THIẾU điều kiện tín chỉ (ĐT 2.1.3-2.1.7 cần ≥30TC)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### COMPLEX_09 [MAJOR]
- **Tags**: FACT_THIEU, SCORE_THAP
- **Score**: 2.5 | **Fact**: 0.4 | **Complete**: 4 | **Faith**: 3
- **Q**: HSA 93 và HSA 94 quy đổi khác nhau bao nhiêu?
- **Bot**: Theo bảng quy đổi ĐQĐNL (HSA) của HaUI, điểm HSA **93** quy đổi thang 30 là **23.01** điểm (tra bảng chính thức, không nội suy). Anh/chị cần em tính thêm ưu tiên KV/ĐT không ạ?
- **Ground Truth**: HSA93→23.01; HSA94→23.25; Chênh lệch = 0.24 điểm. Đây là ví dụ về bảng quy đổi không tuyến tính – tăng 1 điểm HSA nhưng chênh lệch quy đổi khác nhau ở từng mức. Không nội suy tuyến tính bảng này
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### COMPLEX_13 [MAJOR]
- **Tags**: FACT_THIEU, CHUA_DU, SCORE_THAP, FAITH_THAP
- **Score**: 2.5 | **Fact**: 0.67 | **Complete**: 3 | **Faith**: 2
- **Q**: SV được HB HaUI toàn khóa. Cuối kỳ 1 có GPA 2.4, rèn luyện Tốt, 16TC. Học bổng có bị cắt không?
- **Bot**: Dựa trên thông tin về học bổng HaUI và điều kiện duy trì học bổng, em xin trả lời như sau: ↵  ↵ Điều kiện duy trì học bổng HaUI yêu cầu sinh viên phải đạt điểm trung bình chung (GPA) kỳ ≥ 2.5 và rèn luyện loại Tốt trở lên cùng với tổng số tín chỉ xét học bổng trong kỳ ≥ 15 tín chỉ. ↵  ↵ Trong trường hợp của bạn: ↵ - GPA kỳ 1 là 2.4 (không đạt yêu cầu) ↵ - Rèn luyện: Tốt (đạt yêu cầu) ↵ - Số tín ch...
- **Ground Truth**: BỊ CẮT. Điều kiện duy trì HB HaUI: TBC kỳ ≥ 2.5 + rèn luyện Tốt + ≥15TC. Kỳ này GPA 2.4 < 2.5 → không đáp ứng → mất HB HaUI kỳ tiếp theo. Nếu bảo lưu và quay lại đáp ứng điều kiện thì được xem xét lại
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### C_02 [MAJOR]
- **Tags**: THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.9 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 2
- **Q**: Thí sinh có JLPT N4, muốn xét PT2 ngành Ngôn ngữ Nhật, có đủ điều kiện không?
- **Bot**: Dựa trên thông tin từ context, thí sinh có JLPT N4 và muốn đăng ký xét tuyển vào ngành Ngôn ngữ Nhật theo phương thức 2 (PT2) của HaUI năm 2025 sẽ cần đáp ứng các điều kiện sau: ↵  ↵ 1. **Điểm trung bình môn trong tổ hợp xét tuyển:** Điểm TB môn cả năm lớp 10, 11, 12 của từng môn trong tổ hợp xét tuyển phải đạt từ 7,0 điểm trở lên. ↵     ↵ 2. **Chứng chỉ quốc tế:** JLPT N4 được công nhận là chứng ...
- **Ground Truth**: JLPT N4 đủ điều kiện PT2 thông thường (N4→ĐQĐCC=9.00). Cần thêm: TB từng môn trong tổ hợp D01 hoặc D06 ≥7.0, và tốt nghiệp THPT 2025. Lưu ý: LK 2+2 Trung Quốc yêu cầu JLPT ≥ N3 nhưng ngành Nhật không có LK 2+2
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### C_03 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y
- **Score**: 3.3 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 4
- **Q**: Thí sinh tốt nghiệp THPT năm 2024, có thi ĐGTD 2025, có được đăng ký PT5 không?
- **Bot**: Thí sinh tốt nghiệp THPT năm 2024 và đã tham gia kỳ thi Đánh giá tư duy (ĐGTD) do Đại học Bách Khoa Hà Nội tổ chức vào năm 2025 thì vẫn có thể đăng ký xét tuyển theo phương thức PT5. Tuy nhiên, thí sinh cần đảm bảo rằng kết quả của mình được công nhận và quy đổi thành điểm tương đương thang 30 để so sánh với điểm chuẩn của trường. ↵  ↵ Thời gian đăng ký nguyện vọng cho phương thức này là từ ngày 1...
- **Ground Truth**: Theo quy định 2025: thí sinh tốt nghiệp THPT trước năm 2025 KHÔNG được đăng ký PT2, PT4, PT5. Chỉ được xét bằng PT1 (nếu đủ điều kiện thẳng) hoặc PT3 (thi lại cùng lớp 12 năm 2025)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### C_07 [MAJOR]
- **Tags**: THIEU_Y
- **Score**: 3.24 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 3
- **Q**: GPA kỳ 3.65 (Xuất sắc), rèn luyện 92 điểm (Xuất sắc), không có HP < 2.0, 17TC. Được KKHT loại gì?
- **Bot**: Dựa trên thông tin bạn cung cấp và quy định về học bổng Khuyến khích học tập (KKHT) của HaUI: ↵  ↵ - GPA kỳ: 3.65 (Xuất sắc) ↵ - Rèn luyện: 92 điểm (Xuất sắc) ↵  ↵ Theo bảng xếp loại học bổng KKHT, bạn thuộc nhóm **Xuất sắc** vì đạt cả hai tiêu chí GPA và rèn luyện Xuất sắc. ↵  ↵ Tuy nhiên, tổng tín chỉ xét học bổng của bạn là 17TC, thấp hơn yêu cầu tối thiểu là 15TC. Do đó, mặc dù bạn đáp ứng các...
- **Ground Truth**: GPA 3.65 thuộc Xuất sắc (3.60-4.0); rèn luyện 92đ thuộc Xuất sắc (90-100đ); theo bảng: Xuất sắc + Xuất sắc = KKHT Xuất sắc. Đủ điều kiện ≥15TC và không HP<2.0
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### C_08 [MAJOR]
- **Tags**: THIEU_Y
- **Score**: 3.49 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 4
- **Q**: GPA kỳ 3.35 (Giỏi), rèn luyện 85 điểm (Tốt), không có HP dưới 2.0, 16TC. Được KKHT loại gì?
- **Bot**: Dựa trên thông tin bạn cung cấp và quy định về học bổng Khuyến khích học tập (KKHT) của HaUI: ↵  ↵ - Điểm GPA kỳ: 3.35 (tín chỉ) ↵ - Rèn luyện: 85 điểm (Tốt) ↵ - Không có học phần dưới 2.0 ↵ - Tổng tín chỉ xét học bổng: 16 TC ↵  ↵ Theo bảng xếp loại học tập và rèn luyện, bạn thuộc nhóm **Giỏi** vì GPA từ 3.20 đến 3.59 và rèn luyện Tốt (80–89đ). Do đó, bạn sẽ được xét cấp học bổng KKHT **Khá**. ↵  ...
- **Ground Truth**: GPA 3.35 thuộc Giỏi (3.20-3.59); rèn luyện 85đ thuộc Tốt (80-89đ); theo bảng: Giỏi + Tốt = KKHT Giỏi (cả Giỏi+XS và Giỏi+Tốt đều xếp Giỏi)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### C_09 [MAJOR]
- **Tags**: THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.98 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 2
- **Q**: GPA kỳ 2.45, rèn luyện Tốt (82đ), 16TC. Có được xét KKHT không?
- **Bot**: Dựa trên thông tin bạn cung cấp và quy định về học bổng Khuyến khích học tập (KKHT) của HaUI: ↵  ↵ - Điểm GPA kỳ: 2.45 ≥ 2.5 (đạt) ↵ - Rèn luyện: Tốt (82đ) ≥ 80đ (đạt) ↵ - Tổng tín chỉ xét học bổng: 16TC ≥ 15TC (đạt) ↵  ↵ Bạn đã đáp ứng tất cả các điều kiện cần thiết để được xét học bổng KKHT. Tuy nhiên, cần đảm bảo không có môn nào dưới 2.0 điểm và không thuộc trường hợp không được xét như đã nhậ...
- **Ground Truth**: KHÔNG đủ điều kiện KKHT. GPA 2.45 < ngưỡng tối thiểu 2.50 (thang 4). Cần đồng thời đạt TBC ≥ 2.5 + rèn luyện Tốt + không HP<2.0 + ≥15TC
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### C_10 [MAJOR]
- **Tags**: CHUA_DU, SCORE_THAP, FAITH_THAP
- **Score**: 2.35 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 2
- **Q**: GPA 2.85, rèn luyện Tốt (83đ), không có HP nào dưới 2.0, nhưng học kỳ này chỉ có 14 tín chỉ. Có được KKHT không?
- **Bot**: Dựa trên thông tin bạn cung cấp và quy định về điều kiện xét học bổng Khuyến khích học tập (KKHT) của HaUI, em xin trả lời như sau: ↵  ↵ - Điểm GPA học kỳ của bạn là 2.85 ≥ 2.5 nên đạt yêu cầu. ↵ - Rèn luyện Tốt (83đ) cũng đạt yêu cầu. ↵ - Không có học phần nào dưới 2.0 điểm. ↵  ↵ Tuy nhiên, tổng tín chỉ xét học bổng trong học kỳ phải **≥ 15 tín chỉ** mà bạn chỉ có 14 tín chỉ nên không đủ điều kiệ...
- **Ground Truth**: KHÔNG đủ. GPA và rèn luyện thỏa mãn nhưng tổng TC = 14 < 15 (yêu cầu ≥15TC trong kỳ học thông thường). Chỉ kỳ học CUỐI mới chấp nhận ≥7TC
- **Root Cause**: Answer không faithful với context.

#### C_11 [MAJOR]
- **Tags**: CHUA_DU, SCORE_THAP, FAITH_THAP
- **Score**: 2.65 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 2
- **Q**: GPA 2.70, rèn luyện 76 điểm, 18TC, không có HP < 2.0. Có KKHT không?
- **Bot**: Em xem xét các điều kiện để được học bổng Khuyến khích học tập (KKHT) của HaUI như sau: ↵  ↵ - Điểm GPA học kỳ phải ≥ 2.5 (đối với đào tạo tín chỉ). ↵ - Rèn luyện phải đạt loại Tốt trở lên (từ 80 điểm trở lên). ↵ - Không có học phần nào dưới 2.0. ↵ - Tổng số tín chỉ xét học bổng phải ≥ 15 tín chỉ. ↵  ↵ Dựa trên thông tin bạn cung cấp: ↵ - GPA: 2.70 (đạt yêu cầu) ↵ - Rèn luyện: 76 điểm (không đạt y...
- **Ground Truth**: KHÔNG đủ. Rèn luyện 76đ < 80đ (chưa đạt Tốt – cần ≥80đ để được xét KKHT dù GPA và TC thỏa mãn)
- **Root Cause**: Answer không faithful với context.

#### C_12 [MAJOR]
- **Tags**: THIEU_Y
- **Score**: 3.48 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 4
- **Q**: Sau khi trúng tuyển, sinh viên cần làm gì để nhập học?
- **Bot**: Sau khi trúng tuyển, sinh viên cần thực hiện một số bước sau để hoàn tất thủ tục nhập học: ↵  ↵ 1. **Xem Giấy báo nhập học:** Nhà trường sẽ gửi Giấy báo nhập học qua email hoặc hệ thống trực tuyến. Sinh viên cần kiểm tra kỹ thông tin trên giấy báo. ↵  ↵ 2. **Nộp hồ sơ bản cứng:** ↵    - Hồ sơ gồm các loại giấy tờ như chứng nhận tốt nghiệp THPT, học bạ, giấy khai sinh, và các giấy tờ khác theo yêu ...
- **Ground Truth**: 3 bước chính: B1-Nhập học trực tuyến (app MyHaUI hoặc nhaphoc.haui.edu.vn, nộp học phí qua QR BIDV/Lộc Phát); B2-Cập nhật thông tin cá nhân trên sv.haui.edu.vn; B3-Tham gia tuần sinh hoạt công dân và thực hiện kế hoạch học tập. Ngoài ra nộp hồ sơ bản cứng theo lịch trường
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### C_14 [MAJOR]
- **Tags**: CHUA_DU, SCORE_THAP, FAITH_THAP
- **Score**: 2.96 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 2
- **Q**: Chương trình liên kết 2+2 Ngôn ngữ Trung Quốc có gì đặc biệt?
- **Bot**: Chương trình liên kết 2+2 Ngôn ngữ Trung Quốc tại Trường Đại học Công nghiệp Hà Nội (HaUI) và Đại học Khoa học Kỹ thuật Quảng Tây (Trung Quốc) có những điểm nổi bật sau: ↵  ↵ - **Học tập quốc tế:** Sinh viên sẽ trải qua 2 năm đầu tiên tại HaUI, tiếp theo là 2 năm cuối cùng tại Đại học Khoa học Kỹ thuật Quảng Tây ở Trung Quốc. ↵ - **Được cấp hai bằng:** Sau khi tốt nghiệp, sinh viên sẽ nhận được ha...
- **Ground Truth**: LK 2+2: 2 năm tại HaUI + 2 năm tại ĐH Khoa học Kỹ thuật Quảng Tây (Trung Quốc); tốt nghiệp nhận 2 bằng (cử nhân HaUI + cử nhân Hán ngữ đối ngoại Quảng Tây); thí sinh không đạt bậc 4 khung 6 bậc tiếng TQ sẽ được bồi dưỡng trước khi học chính khóa
- **Root Cause**: Answer không faithful với context.

#### C_18 [MAJOR]
- **Tags**: FACT_THIEU, SCORE_THAP, FAITH_THAP
- **Score**: 2.97 | **Fact**: 0.33 | **Complete**: 4 | **Faith**: 2
- **Q**: Đã xác nhận nguyện vọng trên hệ thống HaUI rồi, muốn thay đổi thì phải làm gì?
- **Bot**: Sau khi đã xác nhận nguyện vọng trên hệ thống của HaUI, nếu bạn muốn thay đổi thông tin hoặc điều chỉnh nguyện vọng, cần thực hiện theo các bước sau: ↵  ↵ 1. Liên hệ với Văn phòng Tuyển sinh HaUI để yêu cầu hỗ trợ: ↵    - Điện thoại: 0834560255 / 0383371290 ↵    - Messenger: facebook.com/tuyensinh.haui ↵  ↵ 2. Khi được phép, bạn phải xóa hết các nguyện vọng đã đăng ký trước đó. ↵  ↵ 3. Sau khi xóa...
- **Ground Truth**: Sau khi xác nhận đăng ký, hệ thống tự động KHÓA hồ sơ. Muốn thay đổi phải: liên hệ trực tiếp trường trước ngày 05/7/2025 qua ĐT: 0834560255 / 0383371290 hoặc Messenger: facebook.com/tuyensinh.haui. Lưu ý: khi sửa phải xóa hết nguyện vọng trước, sau đó chỉnh sửa và chọn lại
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### D_01 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP
- **Score**: 2.6 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 3
- **Q**: Sự khác nhau giữa Robot & TTNT và Cơ điện tử HaUI?
- **Bot**: Dựa trên thông tin từ dữ liệu đã cung cấp, dưới đây là sự khác biệt chính giữa ngành **Robot và trí tuệ nhân tạo (mã 75102032)** và **Công nghệ kỹ thuật cơ điện tử (mã 7510203) tại Trường Đại học Công nghiệp Hà Nội (HaUI):** ↵  ↵ **Ngành Robot và trí tuệ nhân tạo (mã 75102032):** ↵ - Điểm chuẩn năm 2025: 24.3 điểm (thang 30) ↵ - Phương thức xét tuyển áp dụng: PT2, PT3, PT5 ↵ - Chuẩn đầu ra: Sinh v...
- **Ground Truth**: Cơ điện tử (7510203, 300CT, ĐC2025=25.17): tích hợp cơ-điện-tử tổng quát, lập trình PLC/robot công nghiệp; Robot&TTNT (75102032, 60CT, ĐC2025=24.30): chuyên sâu AI/ML, thị giác máy tính, xe tự hành; Cơ điện tử hướng manufacturing, Robot hướng AI+hardware
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### D_02 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP
- **Score**: 2.82 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 3
- **Q**: CNTT và Kỹ thuật phần mềm khác nhau thế nào?
- **Bot**: **CNTT và Kỹ thuật phần mềm có những điểm khác biệt chính sau đây:** ↵  ↵ - **Khoa học máy tính (CNTT)** tập trung vào việc nghiên cứu, phát triển và ứng dụng các nguyên lý và công nghệ liên quan đến máy tính và hệ thống thông tin. Nó bao gồm nhiều lĩnh vực như trí tuệ nhân tạo, khoa học dữ liệu, mạng máy tính, bảo mật thông tin, v.v. ↵  ↵ - **Kỹ thuật phần mềm** tập trung hơn vào việc phát triển,...
- **Ground Truth**: CNTT (7480201, 360CT, 23.09): tổng quát, gồm cả quản trị hệ thống, cơ sở dữ liệu, AI ứng dụng; KTPM (7480103, 240CT, 21.75): chuyên phát triển phần mềm, Agile/Scrum, DevOps, full-stack; CNTT rộng hơn, KTPM chuyên sâu phần mềm hơn
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### D_03 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.87 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: PT3 và PT5 khác nhau gì và cách tính điểm ra sao?
- **Bot**: **PT3 và PT5 là hai phương thức xét tuyển khác nhau tại HaUI, mỗi phương thức có những đặc điểm riêng như sau:** ↵  ↵ - **PT3 (Đánh giá năng lực dựa trên kết quả thi THPT quốc gia):** ↵   - Phương thức này sử dụng tổng điểm của ba môn trong tổ hợp để tính điểm xét tuyển. ↵   - Điểm ưu tiên khu vực và đối tượng được áp dụng theo quy định chung. ↵  ↵ - **PT5 (Đánh giá năng lực dựa trên hồ sơ học bạ ...
- **Ground Truth**: PT3: dùng điểm thi TN THPT (thang 30 = tổng 3 môn); PT5: dùng điểm ĐGTD ĐHBK HN (thang 100) quy đổi về thang 30 theo bảng HaUI, điểm 85+ → 30 điểm. PT3 áp dụng trực tiếp, PT5 cần quy đổi trước
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### D_07 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP
- **Score**: 2.38 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 3
- **Q**: Công nghệ kỹ thuật ô tô và Cơ điện tử ô tô khác nhau gì?
- **Bot**: **Công nghệ kỹ thuật cơ điện tử ô tô (mã 75102033) và Công nghệ kỹ thuật ô tô (mã 7510205)** là hai ngành học thuộc nhóm ngành Cơ khí tại Trường Đại học Công nghiệp Hà Nội (HaUI). Dưới đây là những điểm khác biệt chính giữa hai ngành này: ↵  ↵ ### Chuẩn đầu ra ↵  ↵ - **Công nghệ kỹ thuật cơ điện tử ô tô**: ↵   - Vận dụng kiến thức về toán, vật lý, công nghệ thông tin và khoa học xã hội để giải quy...
- **Ground Truth**: CNKT ô tô (7510205, 360CT, 22.50): tổng quát kỹ thuật ô tô, động cơ đốt trong, bảo trì sửa chữa; CĐT ô tô (75102033, 60CT, 23.93): chuyên hệ thống điện tử tích hợp, ECU, ADAS, xe điện/hybrid; CĐT ô tô có điểm chuẩn cao hơn và thiên về điện tử hơn
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### D_08 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP
- **Score**: 2.82 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 3
- **Q**: Du lịch và Quản trị dịch vụ du lịch lữ hành khác nhau thế nào?
- **Bot**: Ngành **Du lịch** (mã 7810101) và ngành **Quản trị dịch vụ du lịch và lữ hành** (mã 7810103) đều thuộc nhóm ngành Du lịch nhưng có những điểm khác biệt về nội dung đào tạo và cơ hội việc làm: ↵  ↵ ### Ngành Du lịch (mã 7810101) ↵ - **Chuẩn đầu ra:** Sinh viên tốt nghiệp từ chương trình này có khả năng vận dụng kiến thức cơ bản về kinh tế, văn hóa, lịch sử, quản trị và marketing trong ngành du lịch...
- **Ground Truth**: Du lịch (7810101, 140CT, 21.85): nền tảng rộng, phát triển sản phẩm, hướng dẫn viên, marketing; QT dịch vụ DL-lữ hành (7810103, 130CT, 22.25): thiên về quản lý điều hành tour, vận hành dịch vụ, quản trị chuỗi; QTLH điểm chuẩn cao hơn một chút, thiên thực hành quản lý hơn
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### D_10 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.58 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Kỹ thuật phần mềm và Khoa học máy tính nên chọn ngành nào nếu muốn làm AI?
- **Bot**: Dựa trên thông tin từ [RETRIEVED CONTEXT], cả hai ngành Kỹ thuật phần mềm (mã 7480103) và Khoa học máy tính (mã 7480101) đều có những kiến thức và kỹ năng liên quan đến trí tuệ nhân tạo (AI). Tuy nhiên, mỗi ngành lại có điểm mạnh riêng: ↵  ↵ ### Ngành Kỹ thuật phần mềm ↵ - **Nắm vững kiến thức nền tảng về khoa học máy tính**, bao gồm cấu trúc dữ liệu, giải thuật, cơ sở dữ liệu và hệ điều hành. ↵ -...
- **Ground Truth**: KHMT (7480101, 120CT, 23.72): mạnh về lý thuyết AI, thuật toán, học máy, nghiên cứu; KTPM (7480103, 240CT, 21.75): mạnh về ứng dụng AI vào sản phẩm phần mềm, MLOps. Muốn nghiên cứu AI học thuật → KHMT; Muốn triển khai AI sản phẩm → KTPM. ĐC KHMT cao hơn KTPM
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### EDGE_06 [MAJOR]
- **Tags**: FACT_THIEU, SCORE_THAP, FAITH_THAP
- **Score**: 2.8 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 1
- **Q**: Điểm chuẩn ngành Robot HaUI năm 2026 là bao nhiêu?
- **Bot**: Điểm chuẩn năm 2026 chưa được công bố (thường công bố sau kỳ thi THPT quốc gia vào tháng 8). Anh/chị có thể tham khảo điểm chuẩn năm 2025 để định hướng, cụ thể ngành Robot và trí tuệ nhân tạo của HaUI năm 2025 là 24.3 điểm (thang 30). ↵  ↵ Để được tư vấn trực tiếp: ↵ ☎ 024.3765.5121 | 0834.560.255 ↵ 🌐 tuyensinh.haui.edu.vn
- **Ground Truth**: Điểm chuẩn 2026 CHƯA công bố (sẽ thông báo sau khi có kết quả thi TN THPT 2026, dự kiến tháng 7-8/2026). Tham khảo: 2025 chung=24.30; 2024 PT3=25.01. Theo dõi: tuyensinh.haui.edu.vn
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### EDGE_10 [MAJOR]
- **Tags**: THIEU_Y
- **Score**: 3.07 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 3
- **Q**: Em học ngành Y tế công cộng ở HaUI được không?
- **Bot**: Ngành Y tế công cộng không nằm trong danh mục các ngành mà Đại học Công nghiệp Hà Nội (HaUI) đào tạo. Trường chuyên về các lĩnh vực như Cơ khí, Điện - Điện tử, CNTT và Kinh tế. Nếu bạn quan tâm đến ngành này, có thể tham khảo các trường đại học y dược hoặc những trường có khoa Y tế công cộng nhé. ↵  ↵ 💡 Để được tư vấn trực tiếp: ↵ ☎ 024.3765.5121 | 0834.560.255 ↵ 🌐 tuyensinh.haui.edu.vn
- **Ground Truth**: HaUI KHÔNG có ngành Y tế công cộng. Các ngành gần nhất liên quan đến sức khỏe/y tế tại HaUI: Công nghệ kỹ thuật điện tử y sinh (thiết bị y tế), Hóa dược (dược phẩm). Muốn học Y tế công cộng nên tìm trường khác như ĐH Y Hà Nội, ĐH Y tế Công cộng
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### MULTI_04 [MAJOR]
- **Tags**: FACT_THIEU, SCORE_THAP
- **Score**: 2.69 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 3
- **Q**: TSA 57, KV2. Có đỗ Cơ điện tử HaUI không?
- **Bot**: 📊 **Tính điểm xét tuyển từ TSA (tham khảo PT5 + ưu tiên):** ↵ - Điểm TSA **57.0** → quy đổi thang 30: **24.50** ↵ Tổng điểm 3 môn (thang 30): **24.50** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.25** ↵ Vì 24.50 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 24.50) / 7.5] × 0.25 = **0.18** ↵ **ĐXT = 24.50 + 0.18 = 24.68** ↵ → **Điểm xét tuyển ≈ 24.68**. ↵ Điểm chuẩn **CN KT Cơ điện tử** (7510203) ...
- **Ground Truth**: TSA57.xx→24.50; ≥22.5→giảm dần; KV2=0.25; ĐĐT=[(30-24.50)/7.5]×0.25=0.7333×0.25=0.18; ĐXT=24.50+0.18=24.68; ĐC Cơ điện tử 2025=25.17; 24.68<25.17 → TRƯỢT (thiếu 0.49đ)
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### MULTI_08 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y
- **Score**: 3.0 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 4
- **Q**: SV ở KTX chất lượng cao phòng 4 người, học K20 đại trà 15TC lý thuyết. Tổng chi phí 1 tháng (KTX + học phí chia đều)?
- **Bot**: 📊 **Tính tổng chi phí 1 tháng:** ↵ - KTX CLC 4 người: **600.000** đ/tháng ↵ - Học phí: 15 TC × 1.5 × 700.000 = **15.750.000** đ/kỳ ↵   → Chia 5 tháng: **3.150.000** đ/tháng ↵ → **Tổng ≈ 3.750.000 đ/tháng** (KTX + học phí chia đều). ↵ ⚠️ Chưa bao gồm điện, nước, sinh hoạt phí. ↵ Anh/chị cần tính thêm gì không ạ?
- **Ground Truth**: KTX CLCao 4ng: 600.000đ/tháng; HP 15TC LT K20: 15×1.5×700.000=15.750.000đ/kỳ; chia 4 tháng học=3.937.500đ/tháng; Tổng chi học phí+KTX≈4.537.500đ/tháng (chưa tính sinh hoạt, điện nước thực tế)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### MULTI_14 [MAJOR]
- **Tags**: THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.15 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 2
- **Q**: Em có IELTS 6.5, TB môn Vật lý học bạ là 6.8. Đăng ký PT2 tổ hợp A01 (Toán-Lý-Anh) được không?
- **Bot**: Theo **Phương thức 2 (PT2)** HaUI năm 2025: chứng chỉ **IELTS Academic ≥ 5,5** (còn hiệu lực) là một trong các chứng chỉ quốc tế được chấp nhận. Ngoài ra, thí sinh cần **điểm TB từng môn** trong tổ hợp xét tuyển (lớp 10, 11, 12) **≥ 7,0** và đáp ứng điều kiện HSG cấp tỉnh hoặc chứng chỉ theo quy chế. Anh/chị cần em tra bảng quy đổi IELTS → điểm ĐQĐCC không ạ?
- **Ground Truth**: KHÔNG đủ. Dù IELTS 6.5 ≥ 5.5 nhưng TB môn Vật lý = 6.8 < 7.0 (yêu cầu TB từng môn trong tổ hợp ≥ 7.0). Thiếu điều kiện về kết quả học tập. Cần cải thiện điểm Vật lý lên ≥ 7.0
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### MULTI_16 [MAJOR]
- **Tags**: THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.86 | **Fact**: 1.0 | **Complete**: 1 | **Faith**: 2
- **Q**: Hiện tại là tháng 6 năm 2026, thí sinh còn có thể đăng ký PT2 không?
- **Bot**: Thời gian đăng ký phương thức 2 (PT2) đã kết thúc vào ngày 05/7/2025. Hiện tại là tháng 6 năm 2026, thí sinh không còn có thể đăng ký phương thức này nữa. ↵  ↵ Nếu bạn quan tâm đến các phương thức khác hoặc cần hỗ trợ thêm về quy trình đăng ký xét tuyển, hãy liên hệ với Văn phòng Tuyển sinh HaUI qua số điện thoại ☎ 024.3765.5121 / 0834.560.255 hoặc truy cập website tuyensinh.haui.edu.vn để được tư...
- **Ground Truth**: Theo lịch tuyển sinh 2026 (dự kiến): đăng ký PT2/PT4/PT5 từ 15/5 đến 20/6/2026. Nếu hiện tại là đầu tháng 6/2026, thí sinh vẫn còn thời gian đăng ký. Cần kiểm tra ngày chính xác với deadline 20/6/2026 lúc 17h00
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### STRAT_01 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.5 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Em muốn làm về AI sau này. Nên chọn ngành nào ở HaUI?
- **Bot**: Em có thể cân nhắc một số ngành liên quan đến trí tuệ nhân tạo (AI) tại Đại học Công nghiệp Hà Nội (HaUI): ↵  ↵ 1. **Khoa học máy tính chương trình đào tạo bằng Tiếng Anh (mã 7480101TA)**: Ngành này tập trung vào các lĩnh vực như AI, phân tích dữ liệu lớn, và phát triển phần mềm. Điểm chuẩn năm 2025 là 20.45 điểm (thang 30). ↵  ↵ 2. **Robot và trí tuệ nhân tạo (mã 75102032)**: Ngành này đào tạo về...
- **Ground Truth**: Gợi ý theo định hướng: (1) Nghiên cứu AI học thuật → Khoa học máy tính (KHMT, 23.72); (2) AI ứng dụng phần mềm → CNTT (23.09) hoặc KTPM (21.75); (3) AI trên phần cứng/robot → Robot&TTNT (24.30); (4) AI trong sản xuất → ĐK&TĐH (26.27) hoặc KTSXTM (22.50). Điểm cao nhất: ĐK&TĐH, thấp nhất: KTPM
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### STRAT_02 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.74 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Em dự kiến tổng điểm THPT khoảng 21 điểm, KV3. Muốn vào HaUI. Nên chọn ngành gì?
- **Bot**: Dựa trên thông tin bạn cung cấp, em sẽ gợi ý một số ngành phù hợp với điểm số và khu vực của bạn: ↵  ↵ **Tổng điểm THPT: 21 điểm** ↵ **Khu vực: KV3** ↵  ↵ Điểm chuẩn năm 2025 (mới nhất hiện có) cho các ngành mà HaUI áp dụng điểm chuẩn chung cho PT2, PT3, PT5 như sau: ↵  ↵ | Ngành | Mã ngành | Điểm chuẩn 2025 | Đánh giá | ↵ |---|---|---|---| ↵ | Phân tích dữ liệu kinh doanh | 73401012 | 20.0 | ✅ An...
- **Ground Truth**: ĐXT=21 (KV3=0). Có thể vào: nhóm Kinh tế (Kế toán 20.00, QTKD 20.25, Tài chính-NH 20.75, Kiểm toán 20.00, QTNL 21.25 – sát ngưỡng), nhóm Du lịch TA (18-18.60), CNKT môi trường (18.75), Dệt may (18-18.25), Ngôn ngữ Nhật (20.00), Ngôn ngữ học (20.00). Lưu ý: ĐC thay đổi hàng năm
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### STRAT_04 [MAJOR]
- **Tags**: THIEU_Y
- **Score**: 3.33 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 4
- **Q**: Em thích kinh tế và tiếng Anh. Nên học Kế toán tiếng Anh hay Logistics ở HaUI?
- **Bot**: Dựa trên thông tin bạn đã cung cấp, cả hai ngành Kế toán chương trình đào tạo bằng Tiếng Anh (mã 7340301TA) và Logistics và quản lý chuỗi cung ứng (mã 7510605) đều thuộc nhóm ngành Kinh tế và phù hợp với sở thích của bạn về tiếng Anh. Tuy nhiên, mỗi ngành có những đặc điểm riêng: ↵  ↵ ### Ngành Kế toán chương trình đào tạo bằng Tiếng Anh (mã 7340301TA) ↵ - **Điểm chuẩn năm 2025:** 20.25 điểm ↵ - *...
- **Ground Truth**: Kế toán TA (7340301TA, 40CT, 20.25, 1tr/TC): học phí cao hơn, chuyên nghiệp kế toán kiểm toán, phù hợp làm việc môi trường đa quốc gia; Logistics (7510605, 60CT, 22.76, 700k/TC): cạnh tranh hơn, cơ hội việc làm rộng trong vận chuyển-chuỗi cung ứng, cần tiếng Anh giao tiếp. ĐC Logistics cao hơn Kế toán TA. Tùy sở thích: kế toán-tài chính hay quản lý vận hành
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### STRAT_05 [MAJOR]
- **Tags**: THIEU_Y
- **Score**: 3.31 | **Fact**: 1.0 | **Complete**: 2 | **Faith**: 3
- **Q**: Em thích xe hơi và công nghệ. Nên chọn CNKT ô tô hay Cơ điện tử ô tô?
- **Bot**: Dựa trên sở thích của bạn về xe hơi và công nghệ, cả hai ngành Công nghệ kỹ thuật ô tô (mã 7510205) và Công nghệ kỹ thuật cơ điện tử ô tô (mã 75102033) đều phù hợp. Tuy nhiên, mỗi ngành có những điểm mạnh riêng: ↵  ↵ ### Công nghệ kỹ thuật ô tô (mã 7510205) ↵ - **Khả năng:** Vận dụng kiến thức về cơ học kỹ thuật, nguyên lý máy móc, vật liệu kỹ thuật để phân tích và giải quyết các vấn đề kỹ thuật t...
- **Ground Truth**: CNKT ô tô (7510205, 360CT, ĐC22.50): tổng quát động cơ-bảo trì-sửa chữa, dễ vào hơn; CĐT ô tô (75102033, 60CT, ĐC23.93): điện tử thông minh trên xe (ECU, ADAS, xe điện), khó vào hơn (+1.43đ). Nếu thích sửa chữa, bảo dưỡng → CNKT ô tô; Thích xe điện, hệ thống thông minh → CĐT ô tô
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### STRAT_08 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 1.9 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Em thi THPT dự kiến 23 điểm, KV3, có IELTS 6.0. Nên dùng PT2 hay PT3 vào ngành Marketing?
- **Bot**: Theo **Phương thức 2 (PT2)** HaUI năm 2025: chứng chỉ **IELTS Academic ≥ 5,5** (còn hiệu lực) là một trong các chứng chỉ quốc tế được chấp nhận. Ngoài ra, thí sinh cần **điểm TB từng môn** trong tổ hợp xét tuyển (lớp 10, 11, 12) **≥ 7,0** và đáp ứng điều kiện HSG cấp tỉnh hoặc chứng chỉ theo quy chế. Anh/chị cần em tra bảng quy đổi IELTS → điểm ĐQĐCC không ạ?
- **Ground Truth**: PT3: ĐXT=23+0(KV3)=23.00; ĐC Marketing 2025=22.50 → ĐỖ bằng PT3. PT2: IELTS 6.0→ĐQĐCC=9.50; cần biết TB học bạ D01 để tính ĐKQHT; nếu TB trung bình 8.0-8.5 → ĐKQHT≈6.27-6.55; ĐXT base≈22-23 + ưu tiên; kết quả PT2 có thể tương đương. Khuyến nghị: đăng ký cả PT2 (trước 5/7) và đặt nguyện vọng PT3 trên Bộ GD
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### TREND_01 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.13 | **Fact**: 0.2 | **Complete**: 2 | **Faith**: 2
- **Q**: Điểm chuẩn CNTT HaUI từ 2023 đến 2025 có xu hướng giảm không?
- **Bot**: Dựa trên dữ liệu đã cung cấp, tôi sẽ so sánh điểm chuẩn ngành Công nghệ thông tin (CNTT) tại Trường Đại học Công nghiệp Hà Nội (HaUI) từ năm 2023 đến 2025 để xem xét xu hướng tăng hoặc giảm. ↵  ↵ **Xu hướng điểm chuẩn ngành CNTT HaUI:** ↵  ↵ - **Năm 2023:** Điểm chuẩn chung cho PT2, PT3, PT5 là 23.09 điểm (thang 30). ↵ - **Năm 2024:** Điểm chuẩn chung cho PT2, PT3, PT5 là 25.22 điểm. ↵ - **Năm 202...
- **Ground Truth**: THẬN TRỌNG khi so sánh: 2023 PT3=25.19; 2024 PT3=25.22 (tăng nhẹ); 2025 chung=23.09. Điểm 2025 thấp hơn vì PHƯƠNG PHÁP TÍNH ĐÃ ĐỔI – 2025 dùng điểm chung cho cả PT2+PT3+PT5, không tách riêng như 2023-2024. Không nên kết luận điểm giảm trực tiếp
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### TREND_04 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 1.97 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Ngành nào tại HaUI có điểm chuẩn tăng nhiều nhất từ 2023 đến 2024?
- **Bot**: Dựa trên thông tin được cung cấp, tôi sẽ so sánh điểm chuẩn năm 2023 và 2024 cho các ngành để xác định ngành có điểm chuẩn tăng nhiều nhất. ↵  ↵ **Bảng so sánh điểm chuẩn từ 2023 đến 2024:** ↵  ↵ | Ngành | Mã | Điểm chuẩn PT3 (thpt) 2023 | Điểm chuẩn PT3 (thpt) 2024 | Tăng giảm | ↵ |---|---|---|---|---| ↵ | Công nghệ vật liệu dệt may | 7540203 | 20.1 | 20.9 | +0.8 | ↵ | Thiết kế thời trang | 72104...
- **Ground Truth**: Tăng mạnh nhất 2023→2024 (PT3): ĐK&TĐH: 25.47→26.05 (+0.58); Logistics: 25.52→25.89 (+0.37); KHMT: 25.05→25.32 (+0.27); Cơ điện tử: 24.63→25.41 (+0.78); Robot: 24.54→25.01 (+0.47). CĐT tăng mạnh nhất
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### TREND_06 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.82 | **Fact**: 0.5 | **Complete**: 2 | **Faith**: 2
- **Q**: Những ngành nào ở HaUI có điểm chuẩn thấp nhất năm 2025 để em cân nhắc?
- **Bot**: Dựa trên dữ liệu hiện có, những ngành có điểm chuẩn thấp nhất tại Trường Đại học Công nghiệp Hà Nội (HaUI) năm 2025 là: ↵  ↵ | Ngành | Mã | ĐC 2025 | ↵ |---|---:|---:| ↵ | Công nghệ kỹ thuật môi trường | 7510406 | 18.75 | ↵ | Quản trị nhà hàng và dịch vụ ăn uống chương trình đào tạo bằng Tiếng Anh | 7810202TA | 18.6 | ↵  ↵ Đây là hai ngành có điểm chuẩn thấp nhất trong năm 2025, giúp bạn có thêm l...
- **Ground Truth**: Điểm thấp nhất 2025: Công nghệ dệt may(18.00), Du lịch TA(18.00), CNKT môi trường(18.75), Công nghệ vật liệu dệt may(18.25), QT lữ hành TA(18.10), QT khách sạn TA(18.25), QT nhà hàng TA(18.60), Ngôn ngữ Nhật(20.00), Ngôn ngữ học(20.00), Kế toán(20.00)
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

#### TREND_08 [MAJOR]
- **Tags**: FACT_THIEU, THIEU_Y, SCORE_THAP, FAITH_THAP
- **Score**: 2.83 | **Fact**: 0.86 | **Complete**: 2 | **Faith**: 2
- **Q**: Ngành Robot & TTNT HaUI mới hay lâu năm, điểm chuẩn có ổn định không?
- **Bot**: Ngành Robot và Trí tuệ nhân tạo (Robot and Artificial Intelligence) tại Trường Đại học Công nghiệp Hà Nội (HaUI) là một ngành tương đối mới. Dựa trên dữ liệu hiện có, chúng ta có thể thấy rằng ngành này đã được triển khai từ năm 2023. ↵  ↵ **Điểm chuẩn của ngành Robot và Trí tuệ nhân tạo trong những năm gần đây:** ↵  ↵ - **Năm 2025:** 24.3 điểm (thang 30) ↵ - **Năm 2024:** Không có dữ liệu về điểm...
- **Ground Truth**: Robot & TTNT tại HaUI: 2023 PT3=24.54 (tên cũ mã 7510209), 2024 PT3=25.01; 2025 chung=24.30 (mã mới 75102032). Điểm ổn định ở mức 24-25, là ngành cạnh tranh cao (chỉ tiêu 60 SV). Thành lập khá gần đây trong bối cảnh Cách mạng CN 4.0
- **Root Cause**: Thiếu nhiều ý quan trọng trong ground truth.

### 🟡 MINOR (33 cases)

#### A1_10 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 4.0 | **Fact**: 0.8 | **Complete**: 4 | **Faith**: 4
- **Q**: Tổ hợp X06 gồm những môn gì?
- **Bot**: Tổ hợp X06 bao gồm các môn sau: Toán, Tin học và Công nghệ. Đây là tổ hợp xét tuyển cho một số ngành tại HaUI như Hệ thống thông tin (mã 7480104), Robot và trí tuệ nhân tạo (mã 75102032), Khoa học máy tính (mã 7480101), Năng lượng tái tạo (mã 75190071), Công nghệ thông tin (mã 7480201), Công nghệ kỹ thuật khuôn mẫu (mã 75102012) và Thiết kế cơ khí và kiểu dáng công nghiệp (mã 75102013). Bạn có cần...
- **Ground Truth**: Tổ hợp X06: Toán, Tin học, Công nghệ – dùng cho nhiều ngành kỹ thuật ở HaUI
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### A1_35 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.6 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Website đăng ký xét tuyển HaUI PT2/PT4/PT5 là gì?
- **Bot**: Để đăng ký xét tuyển theo các phương thức PT2, PT4, hoặc PT5 tại Trường Đại học Công nghiệp Hà Nội (HaUI), bạn có thể truy cập vào website sau: ↵  ↵ - Đăng ký xét tuyển: xettuyen.haui.edu.vn ↵  ↵ Nếu cần thêm hỗ trợ hoặc thông tin chi tiết, bạn cũng có thể liên hệ với Văn phòng Tuyển sinh HaUI qua số điện thoại 024.3765.5121 hoặc 0834.560.255.
- **Ground Truth**: Website đăng ký dự tuyển PT2, PT4, PT5: https://xettuyen.haui.edu.vn; mở từ 15/5 đến 05/7/2025 (2025) hoặc 15/5–20/6/2026 (2026)
- **Root Cause**: Answer không faithful với context.

#### A2_01 [MINOR]
- **Tags**: FACT_THIEU, CHUA_DU
- **Score**: 3.78 | **Fact**: 0.5 | **Complete**: 3 | **Faith**: 3
- **Q**: Điểm chuẩn tất cả ngành CNTT HaUI 2025?
- **Bot**: **Điểm chuẩn năm 2025 cho các ngành Công nghệ thông tin (CNTT) tại Trường Đại học Công nghiệp Hà Nội (HaUI):** ↵  ↵ | Ngành | Mã | ĐC 2025 | ↵ |---|---:|---:| ↵ | Khoa học máy tính | 7480101 | 23.72 | ↵ | An toàn thông tin | 74802021 | 23.43 | ↵ | Công nghệ thông tin | 7480201 | 23.09 | ↵ | Công nghệ đa phương tiện | 74802012 | 22.25 | ↵ | Công nghệ kỹ thuật máy tính | 7480108 | 21.85 | ↵ | Kỹ thu...
- **Ground Truth**: Bảng điểm chuẩn 2025 nhóm CNTT: CNTT(23.09), KTPM(21.75), KHMT(23.72), HTTT(21.10), ATTT(23.43), ĐPTT(22.25), MMT(21.70), KTMT(21.85), KHMT-TA(20.45), ATTT chung
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### A2_09 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.53 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 3
- **Q**: HaUI có những ngành nào thuộc lĩnh vực du lịch?
- **Bot**: Dựa trên dữ liệu hiện có, Trường Đại học Công nghiệp Hà Nội (HaUI) cung cấp các ngành thuộc lĩnh vực Du lịch như sau: ↵  ↵ | Ngành | Mã ngành | Điểm chuẩn 2025 (thang 30) | ↵ |---|---|---| ↵ | Quản trị dịch vụ du lịch và lữ hành | 7810103 | 22.25 điểm | ↵ | Quản trị khách sạn | 7810201 | 21.75 điểm | ↵ | Quản trị nhà hàng và dịch vụ ăn uống | 7810202 | 20.85 điểm | ↵ | Du lịch | 7810101 | 21.85 đi...
- **Ground Truth**: Nhóm Du lịch HaUI: Du lịch (7810101), Du lịch TA, Quản trị dịch vụ du lịch và lữ hành (7810103), QT lữ hành TA, Quản trị khách sạn (7810201), QT khách sạn TA, Quản trị nhà hàng và DVAU (7810202), QT nhà hàng TA
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### A2_10 [MINOR]
- **Tags**: FACT_THIEU, CHUA_DU, FAITH_THAP
- **Score**: 3.15 | **Fact**: 0.5 | **Complete**: 3 | **Faith**: 2
- **Q**: HaUI có những loại học bổng nào dành cho sinh viên?
- **Bot**: Dựa trên thông tin hiện có, Trường Đại học Công nghiệp Hà Nội (HaUI) cung cấp một số loại học bổng chính như sau: ↵  ↵ 1. **Học bổng HaUI**: ↵    - Học bổng toàn khóa: dành cho thủ khoa đầu vào và sinh viên đạt giải cao trong các kỳ thi HSG quốc gia/quốc tế, thi tay nghề khu vực ASEAN và quốc tế. ↵    - Học bổng năm thứ nhất: dành cho sinh viên có tổng điểm xét tuyển cao ngay sau nhóm thủ khoa. ↵ ...
- **Ground Truth**: 4 nhóm học bổng: 1.HB HaUI đầu vào (100% toàn khóa, 100% năm 1, 5tr/suất); 2.HB Khuyến khích học tập (theo kết quả kỳ: Xuất sắc/Giỏi/Khá); 3.HB Nguyễn Thanh Bình (hoàn cảnh khó khăn); 4.HB tài trợ doanh nghiệp
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### A2_12 [MINOR]
- **Tags**: FACT_THIEU, FAITH_THAP
- **Score**: 3.43 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 2
- **Q**: Lịch đăng ký dự tuyển PT2, PT4, PT5 năm 2026 là khi nào?
- **Bot**: Dựa trên thông tin từ `[RETRIEVED CONTEXT]`, lịch đăng ký dự tuyển cho phương thức PT2, PT4, và PT5 trong năm 2026 tại Trường Đại học Công nghiệp Hà Nội (HaUI) được quy định như sau: ↵  ↵ - **Thời gian đăng ký trực tuyến:** Từ ngày 15/5/2026 đến ngày 20/6/2026. ↵ - **Công bố kết quả đăng ký dự tuyển PT2, PT4, PT5:** Trước 17h00 ngày 10/7/2026. ↵  ↵ Để biết thêm chi tiết hoặc cập nhật mới nhất, bạn...
- **Ground Truth**: Lịch tuyển sinh 2026 (dự kiến): Đăng ký PT2/PT4/PT5 online: 15/5/2026 – 20/6/2026 tại xettuyen.haui.edu.vn; Công bố kết quả PT2/4/5: trước 17h00 ngày 10/7/2026; Nhập học online: 15/8 – 25/8/2026; Khai giảng HK1: từ 07/9/2026
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### B1_01 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.59 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Toán 8, Lý 7.5, Anh 7.25, KV2-NT. Tính điểm xét tuyển PT3?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **22.75** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.50** ↵ Vì 22.75 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 22.75) / 7.5] × 0.50 = **0.48** ↵ **ĐXT = 22.75 + 0.48 = 23.23** ↵ → **Điểm xét tuyển ≈ 23.23**. ↵ Anh/chị muốn đối chiếu với điểm chuẩn ngành nào ạ?
- **Ground Truth**: Tổng=22.75; ≥22.5→giảm dần; KV2-NT=0.50; ĐĐT=[(30-22.75)/7.5]×0.50=(7.25/7.5)×0.50=0.483≈0.48; ĐXT=22.75+0.48=23.23
- **Root Cause**: Answer không faithful với context.

#### B1_17 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.79 | **Fact**: 1.0 | **Complete**: 5 | **Faith**: 2
- **Q**: K20 tiếng Anh, học phần 4 tín chỉ thực hành chuyên sâu. Học phí bao nhiêu?
- **Bot**: 📊 **Tính học phí học phần** (năm học 2025–2026): ↵ - Số tín chỉ: **4** ↵ - Loại học phần: Thực hành/thí nghiệm chuyên sâu → hệ số **×2.5** ↵ - Số TC quy đổi: 4 × 2.5 = **10.0** ↵ - Đơn giá (K20 chương trình Tiếng Anh): **1.000.000** đ/TC ↵ → **HP = 10.0 × 1.000.000 = 10.000.000 đồng** (= 10000000 đ). ↵ Anh/chị cần tính thêm học phần khác không ạ?
- **Ground Truth**: HP = 4TC × hệ số 2.5 (TH chuyên sâu) × 1.000.000đ = 4 × 2.5 × 1.000.000 = 10.000.000 đồng
- **Root Cause**: Answer không faithful với context.

#### B1_20 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.65 | **Fact**: 1.0 | **Complete**: 5 | **Faith**: 2
- **Q**: K19, học phần Ngoại ngữ 3 tín chỉ. Học phí tính thế nào?
- **Bot**: 📊 **Tính học phí học phần** (năm học 2025–2026): ↵ - Số tín chỉ: **3** ↵ - Loại học phần: Ngoại ngữ → hệ số **×1.5** ↵ - Số TC quy đổi: 3 × 1.5 = **4.5** ↵ - Đơn giá (K19): **550.000** đ/TC ↵ → **HP = 4.5 × 550.000 = 2.475.000 đồng** (= 2475000 đ). ↵ Anh/chị cần tính thêm học phần khác không ạ?
- **Ground Truth**: K19 Ngoại ngữ: N_TCHP = số TC × 1.5; HP = 3 × 1.5 × 550.000đ = 2.475.000 đồng
- **Root Cause**: Answer không faithful với context.

#### B1_27 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.15 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: HSA 115, KV1, tính điểm xét tuyển PT4?
- **Bot**: 📊 **Quy đổi & tính ĐXT (tham khảo PT5 + ưu tiên):** ↵ - HSA 115 → thang 30: **26.5** ↵ Tổng điểm 3 môn (thang 30): **26.50** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.75** ↵ Vì 26.50 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 26.50) / 7.5] × 0.75 = **0.35** ↵ **ĐXT = 26.50 + 0.35 = 26.85** ↵ → **ĐXT ≈ 26.85**. ↵ Anh/chị cần tư vấn thêm ngành khác không ạ?
- **Ground Truth**: HSA115→26.50; ≥22.5→giảm dần; KV1=0.75; ĐĐT=[(30-26.50)/7.5]×0.75=(3.5/7.5)×0.75=0.4667×0.75=0.35; ĐXT=26.50+0.35=26.85
- **Root Cause**: Answer không faithful với context.

#### B1_32 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.29 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: K20 chương trình tiếng Anh, học phần 4TC lý thuyết. Học phí bao nhiêu?
- **Bot**: 📊 **Tính học phí học phần** (năm học 2025–2026): ↵ - Số tín chỉ: **4** ↵ - Loại học phần: Lý thuyết/tiểu luận/đồ án → hệ số **×1.5** ↵ - Số TC quy đổi: 4 × 1.5 = **6.0** ↵ - Đơn giá (K20 chương trình Tiếng Anh): **1.000.000** đ/TC ↵ → **HP = 6.0 × 1.000.000 = 6.000.000 đồng** (= 6000000 đ). ↵ Anh/chị cần tính thêm học phần khác không ạ?
- **Ground Truth**: HP = 4TC × hệ số 1.5 (LT) × 1.000.000đ (K20 TA) = 4 × 1.5 × 1.000.000 = 6.000.000 đồng
- **Root Cause**: Answer không faithful với context.

#### COMPLEX_12 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.02 | **Fact**: 0.25 | **Complete**: 4 | **Faith**: 3
- **Q**: Em được IELTS 7.5, TB học bạ Toán 9.5, Văn 8.8, Anh 9.8 (D01). KV1. Tính ĐXT PT2 và ngành nào đỗ được?
- **Bot**: 📊 **Tính điểm xét tuyển PT2 (HaUI):** ↵ - TB Toán = 9.5, TB Văn = 8.8, TB Anh = 9.8 ↵ - Quy đổi ĐKQHT: Toán 9.5→9.55, Văn 8.8→6.85, Anh 9.8→9.85 ↵ - ĐKQHT = (9.55+6.85+9.85)/3 = **8.75** ↵ - IELTS 7.5 → ĐQĐCC = **10.00** ↵ - **ĐXT = 8.75 × 2 + 10.00 = 27.50** ↵ - Ưu tiên KV: **+0.75** ↵ - Vì ĐXT gốc 27.5 ≥ 22.5 → giảm dần: ĐĐT = [(30-27.5)/7.5]×0.75 = **0.25** ↵ → **ĐXT cuối = 27.75** ↵ Anh/chị mu...
- **Ground Truth**: KQHB: Toán9.5→9.55, Văn8.8→6.85, Anh9.8→9.85; ĐKQHT=(9.55+6.85+9.85)/3=8.75; ĐQĐCC(IELTS7.5→IELTS≥6.5)=10.00; ĐXT base=8.75×2+10.00=27.50; KV1=0.75; ≥22.5→giảm dần: ĐĐT=[(30-27.50)/7.5]×0.75=(2.5/7.5)×0.75=0.333×0.75=0.25; ĐXT=27.50+0.25=27.75; Đỗ tất cả ngành trừ ĐK&TĐH vẫn đỗ (26.27<27.75)
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### COMPLEX_15 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.46 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Em có HSK 5 và đang học lớp 12 thi tổ hợp D04. Điểm TB D04: Toán 8.0, Văn 8.5, Tiếng Trung 9.0. Đăng ký PT2 ngành Ngôn ngữ Trung Quốc có được không?
- **Bot**: Dựa trên thông tin bạn cung cấp, em xin tư vấn như sau: ↵  ↵ 1. **Điều kiện đăng ký:** Bạn đã đạt chứng chỉ HSK 5 và có điểm trung bình tổ hợp D04 (Toán: 8.0, Văn: 8.5, Tiếng Trung: 9.0) ≥ 7.0 cho từng môn trong tổ hợp xét tuyển. ↵  ↵ 2. **Ngành đăng ký:** Ngành Ngôn ngữ Trung Quốc có yêu cầu riêng về chứng chỉ ngoại ngữ là TOPIK cấp độ 4 trở lên hoặc HSK cấp độ 5 trở lên (đối với ngành này, bạn đ...
- **Ground Truth**: Đủ: HSK 5 → điều kiện CC quốc tế ✓ (HSK5 ≥ HSK3 yêu cầu tối thiểu, ĐQĐCC=10.00); TB Toán 8.0 ≥ 7.0 ✓, TB Văn 8.5 ≥ 7.0 ✓, TB Tiếng Trung 9.0 ≥ 7.0 ✓; Ngôn ngữ TQ nhận D01 và D04 ✓; Đủ điều kiện. ĐQĐCC(HSK5)=10.00
- **Root Cause**: Answer không faithful với context.

#### COMPLEX_16 [MINOR]
- **Tags**: CHUA_DU
- **Score**: 3.43 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 3
- **Q**: Em có TOPIK 4 muốn đăng ký PT2 vào Ngôn ngữ Trung Quốc LK 2+2. Có đủ tiêu chuẩn chứng chỉ không?
- **Bot**: Dựa trên thông tin từ context, bạn đã đạt TOPIK cấp độ 4, điều này đáp ứng yêu cầu về chứng chỉ quốc tế cho ngành Ngôn ngữ Trung Quốc (LK 2+2 Quảng Tây) của Trường Đại học Công nghiệp Hà Nội. Tuy nhiên, để đủ điều kiện xét tuyển theo phương thức PT2, bạn cũng cần đảm bảo các tiêu chí sau: ↵  ↵ 1. Điểm trung bình môn từng năm lớp 10, 11, 12 trong tổ hợp xét tuyển phải đạt từ 7.0 điểm trở lên. ↵ 2. ...
- **Ground Truth**: Ngôn ngữ TQ LK 2+2 yêu cầu CC quốc tế cao hơn thông thường: TOPIK ≥ cấp 4 (thay vì TOPIK 3 cho ngành thường); HSK ≥ cấp 4; JLPT ≥ N3. TOPIK 4 đáp ứng đúng ngưỡng tối thiểu → đủ điều kiện CC. Vẫn cần: TB từng môn trong tổ hợp D01/D04 ≥ 7.0 và tốt nghiệp THPT 2025. ĐQĐCC(TOPIK4)=9.50
- **Root Cause**: 

#### C_05 [MINOR]
- **Tags**: FACT_THIEU, FAITH_THAP
- **Score**: 3.69 | **Fact**: 0.86 | **Complete**: 4 | **Faith**: 2
- **Q**: Điều kiện nhận học bổng toàn khóa HaUI đầu vào là gì?
- **Bot**: Để được nhận Học bổng toàn khóa HaUI (100% học phí toàn khóa), sinh viên cần đạt một trong các tiêu chí sau: ↵  ↵ - Đoạt giải Nhất, Nhì, Ba kỳ thi HSG quốc gia/quốc tế hoặc thi KHKT cấp quốc gia do Bộ GD&ĐT tổ chức (không quá 3 năm tính đến ngày đăng ký xét tuyển). ↵ - Đoạt giải Nhất, Nhì, Ba thi tay nghề khu vực ASEAN và quốc tế do Bộ LĐTBXH cử đi. ↵ - Là thủ khoa của các nhóm tổ hợp xét tuyển: A...
- **Ground Truth**: HB toàn khóa: (1) Giải Nhất/Nhì/Ba HSG quốc gia/quốc tế hoặc KHKT quốc gia/quốc tế do Bộ GD tổ chức (≤3 năm); (2) Giải tay nghề ASEAN/quốc tế do Bộ LĐTBXH; (3) Thủ khoa 4 nhóm tổ hợp A00/A01/D01/(B00,C00,D04,D06,D07,D14,DD2); (4) Thủ khoa PT2/PT4/PT5
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch. Answer không faithful với context.

#### C_06 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.6 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Điều kiện xét học bổng KKHT tại HaUI là gì?
- **Bot**: Để được xét học bổng Khuyến khích học tập (KKHT) tại Trường Đại học Công nghiệp Hà Nội (HaUI), sinh viên cần đáp ứng các điều kiện sau: ↵  ↵ **1. Điểm trung bình chung học kỳ:** ↵ - ≥ 2.5 điểm (đối với hệ đào tạo tín chỉ) ↵ - ≥ 7.0 điểm (đối với hệ đào tạo niên chế) ↵  ↵ **2. Rèn luyện:** Loại Tốt trở lên ↵  ↵ **3. Không có học phần nào dưới 2.0 điểm (tín chỉ) hoặc dưới 5.0 điểm (niên chế)** ↵  ↵ ...
- **Ground Truth**: Điều kiện xét KKHT: (1) TBC học kỳ ≥ 2.5 (tín chỉ); (2) Rèn luyện Tốt trở lên (≥80đ); (3) Không có học phần < 2.0; (4) Tổng TC xét ≥ 15TC (HK cuối ≥ 7TC); (5) Không đang nhận HB HaUI cùng kỳ
- **Root Cause**: Answer không faithful với context.

#### C_13 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.3 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Sinh viên là người dân tộc thiểu số, thuộc vùng đặc biệt khó khăn, có được miễn giảm học phí không?
- **Bot**: Người dân tộc thiểu số thuộc vùng đặc biệt khó khăn có thể được miễn hoặc giảm học phí tại HaUI. Để được hưởng chính sách này, sinh viên cần nộp hồ sơ gồm: ↵  ↵ - Giấy xác nhận vùng có điều kiện KT-XH đặc biệt khó khăn. ↵ - Giấy chứng nhận hộ nghèo/cận nghèo năm 2025 (nếu có). ↵ - Giấy xác nhận thông tin cư trú theo mẫu CT07 có xác nhận của Công An Phường/Xã. ↵ - Bản sao giấy khai sinh. ↵  ↵ Sinh ...
- **Ground Truth**: Sinh viên dân tộc thiểu số (không phải rất ít người) vùng đặc biệt khó khăn hoặc có giấy chứng nhận hộ nghèo/cận nghèo 2025 được miễn giảm học phí. Cần nộp: Giấy xác nhận vùng + Giấy CN hộ nghèo/cận nghèo + CT07 thông tin cư trú + bản sao Khai sinh
- **Root Cause**: Answer không faithful với context.

#### C_16 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.46 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Học sinh hoàn thành dự bị đại học có điều kiện gì để xét tuyển thẳng PT1 vào HaUI?
- **Bot**: Để thí sinh hoàn thành dự bị đại học được xét tuyển thẳng theo Phương thức 1 (PT1) tại Trường Đại học Công nghiệp Hà Nội (HaUI), cần đáp ứng các điều kiện sau: ↵  ↵ - Thí sinh phải là người đã hoàn thành chương trình dự bị đại học. ↵ - Điểm trung bình môn của từng môn trong tổ hợp xét tuyển lớp 10, 11, và 12 phải đạt từ 8.0 điểm trở lên. ↵  ↵ Đối với ngành Công nghệ đa phương tiện, CNTT, Cơ điện t...
- **Ground Truth**: PT1 dành cho học sinh hoàn thành dự bị đại học: điểm TB môn trong tổ hợp xét tuyển lớp 10+11+12 ≥ 8.0 (áp dụng cho các ngành: Công nghệ đa phương tiện, CNTT, Cơ điện tử, Ô tô, Robot & TTNT, Điều khiển tự động hóa, Hóa dược). Nộp hồ sơ trực tiếp tại trường trước 30/6
- **Root Cause**: Answer không faithful với context.

#### C_17 [MINOR]
- **Tags**: CHUA_DU
- **Score**: 3.87 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 3
- **Q**: TOPIK cần đạt cấp độ mấy để đăng ký PT2 ngành Ngôn ngữ Hàn Quốc HaUI?
- **Bot**: Để đăng ký phương thức tuyển sinh PT2 (xét kết hợp học bạ THPT + chứng chỉ quốc tế) vào ngành Ngôn ngữ Hàn Quốc tại Trường Đại học Công nghiệp Hà Nội (HaUI), thí sinh cần đạt tối thiểu **TOPIK cấp độ 3**. ↵  ↵ Nếu bạn quan tâm đến chương trình liên kết 2+2 với Đại học Khoa học Kỹ thuật Quảng Tây, yêu cầu TOPIK sẽ cao hơn là **cấp độ 4**.
- **Ground Truth**: PT2 yêu cầu TOPIK cấp độ 3 trở lên (điểm quy đổi ĐQĐCC: TOPIK 3=9.00, TOPIK 4=9.50, TOPIK 5/6=10.00) kết hợp TB từng môn trong tổ hợp DD2 (Toán-Văn-Tiếng Hàn) ≥ 7.0. Chứng chỉ phải còn hiệu lực
- **Root Cause**: 

#### C_19 [MINOR]
- **Tags**: FAITH_THAP
- **Score**: 3.75 | **Fact**: 1.0 | **Complete**: 4 | **Faith**: 2
- **Q**: Hạn chót nộp hồ sơ xét tuyển thẳng (PT1) HaUI 2025 là ngày nào?
- **Bot**: Hạn chót nộp hồ sơ xét tuyển thẳng (Phương thức 1 - PT1) tại Trường Đại học Công nghiệp Hà Nội năm 2025 là đến 17h00 ngày 30/6/2025. Bạn hãy lưu ý thời gian này để không bỏ lỡ nhé. ↵  ↵ Nếu bạn cần thêm thông tin gì khác về quy trình đăng ký hoặc điều kiện xét tuyển, em sẵn lòng hỗ trợ thêm!
- **Ground Truth**: Hồ sơ xét tuyển thẳng (PT1) nộp trực tiếp tại trường đến hết 17h00 ngày 30/6/2025. Công bố kết quả: trước 17h00 ngày 15/7/2025
- **Root Cause**: Answer không faithful với context.

#### D_04 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.85 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 4
- **Q**: So sánh giá phòng KTX chất lượng cao và tiêu chuẩn tại HaUI?
- **Bot**: **So sánh giá phòng ký túc xá chất lượng cao và tiêu chuẩn tại Đại học Công nghiệp Hà Nội (HaUI):** ↵  ↵ --- ↵  ↵ ### 1. Phòng ký túc xá chất lượng cao ↵  ↵ - **Phòng 3 người:** 800,000 đ/người/tháng ↵ - **Phòng 4 người:** 600,000 đ/người/tháng ↵ - **Phòng 6 người:** 400,000 đ/người/tháng ↵  ↵ Đặc điểm: ↵ - Có điều hòa ↵ - Bình nóng lạnh ↵ - Tủ cá nhân ↵ - Giường tầng gỗ ↵ - Đệm ↵ - Quạt trần ↵  ↵...
- **Ground Truth**: CLCao: có điều hòa; giá 3ng=800k, 4ng=600k, 6ng=400k; Tiêu chuẩn: không điều hòa; CS1: 4ng=465k, 6ng=310k; CS2: 4ng=420k, 6ng=280k. Tất cả có WC riêng, khép kín, ≥30m²
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### D_05 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 4.1 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 5
- **Q**: So sánh học phí K20 đại trà, K20 tiếng Anh và K19 HaUI?
- **Bot**: **So sánh học phí giữa các hệ đào tạo tại HaUI như sau:** ↵  ↵ - **Hệ cử nhân K20 chương trình đại trà:** Học phí là 700.000 đ/TC. ↵ - **Hệ cử nhân K20 chương trình đào tạo bằng Tiếng Anh:** Học phí là 1.000.000 đ/TC. ↵ - **Hệ cử nhân K19:** Học phí là 550.000 đ/TC. ↵  ↵ --- ↵ 💡 Để được tư vấn trực tiếp: ↵ ☎ 024.3765.5121 | 0834.560.255 ↵ 🌐 tuyensinh.haui.edu.vn ↵  ↵ Bạn cần thêm thông tin gì khác
- **Ground Truth**: K20 đại trà: 700.000đ/TC; K20 Tiếng Anh: 1.000.000đ/TC (+43%); K19: 550.000đ/TC; K18 trở về: 495.000đ/TC. Cùng công thức N_TCHP nhưng đơn giá khác nhau. K20 TA đắt hơn K20 đại trà 300.000đ/TC
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### D_06 [MINOR]
- **Tags**: FACT_THIEU, CHUA_DU
- **Score**: 3.4 | **Fact**: 0.5 | **Complete**: 3 | **Faith**: 3
- **Q**: Ngành Ngôn ngữ Trung Quốc và Trung Quốc học khác nhau thế nào?
- **Bot**: Ngành Ngôn ngữ Trung Quốc (mã 7220204) và ngành Trung Quốc học (mã 7310612) đều thuộc nhóm ngành Ngôn ngữ nhưng có những điểm khác biệt về mục tiêu đào tạo, kiến thức chuyên môn và cơ hội việc làm. ↵  ↵ **Ngành Ngôn ngữ Trung Quốc:** ↵ - **Mục tiêu:** Nâng cao kỹ năng ngôn ngữ tiếng Trung, hiểu biết văn hóa và xã hội Trung Quốc. ↵ - **Kiến thức chuyên môn:** Tập trung vào các kỹ năng giao tiếp, dị...
- **Ground Truth**: Ngôn ngữ TQ (7220204, 100CT, 23.00): thiên về ngôn ngữ học, dịch thuật, giảng dạy; Trung Quốc học (7310612, 50CT, 21.55): thiên về nghiên cứu văn hóa-chính trị-kinh tế TQ, quan hệ Việt-Trung; TQ học mang tính học thuật-khu vực học hơn
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### D_09 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 4.01 | **Fact**: 0.83 | **Complete**: 4 | **Faith**: 4
- **Q**: So sánh học bổng dành cho thủ khoa PT2 và thủ khoa nhóm tổ hợp A01?
- **Bot**: **So sánh học bổng dành cho thủ khoa PT2 và thủ khoa nhóm tổ hợp A01 tại HaUI như sau:** ↵  ↵ - **Thủ khoa PT2:** Học bổng toàn khóa (HB HaUI) được cấp cho thí sinh có điểm xét tuyển cao nhất trong từng phương thức, bao gồm cả PT2. Học bổng này miễn 100% học phí cho toàn bộ khóa học, yêu cầu duy trì GPA kỳ ≥ 2.5 và rèn luyện Tốt, cùng với việc đăng ký ít nhất 15 tín chỉ mỗi kỳ. ↵  ↵ - **Thủ khoa n...
- **Ground Truth**: Cả thủ khoa PT2 (HSG/CC quốc tế) và thủ khoa nhóm tổ hợp A01 (THPT) đều được nhận HB HaUI TOÀN KHÓA = 100% học phí toàn khóa học. Không có sự phân biệt giữa các nguồn thủ khoa về giá trị học bổng
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### EDGE_07 [MINOR]
- **Tags**: FACT_THIEU, CHUA_DU
- **Score**: 3.04 | **Fact**: 0.67 | **Complete**: 3 | **Faith**: 3
- **Q**: Điểm chuẩn CNTT 2025 thấp hơn 2024 có phải vì chất lượng thí sinh thấp hơn?
- **Bot**: Dựa trên dữ liệu hiện có, năm 2025 Trường Đại học Công nghiệp Hà Nội (HaUI) áp dụng điểm chuẩn chung cho tất cả các phương thức xét tuyển đối với ngành CNTT. Điểm chuẩn năm 2025 đã được điều chỉnh thấp hơn so với năm 2024. Tuy nhiên, việc thay đổi này không nhất thiết phản ánh chất lượng thí sinh thấp hơn mà có thể do nhiều yếu tố khác như chính sách tuyển sinh của trường, số lượng thí sinh đăng k...
- **Ground Truth**: KHÔNG. Điểm chuẩn 2025 (23.09) thấp hơn 2024 PT3 (25.22) là do THAY ĐỔI PHƯƠNG PHÁP XÉT TUYỂN: 2025 dùng điểm chung cho nhiều phương thức (PT2+PT3+PT5), không phân tách PT riêng lẻ như 2024. Không phản ánh chất lượng thí sinh; KHÔNG nên so sánh trực tiếp
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### MULTI_02 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.61 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 3
- **Q**: Toán 8, Vật lý 8, Anh 8 (tổng 24), KV2-NT. Có đủ điểm vào Cơ điện tử HaUI 2025 không?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **24.00** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.50** ↵ Vì 24.00 ≥ 22.5 → công thức giảm dần: ↵ ĐĐT = [(30 − 24.00) / 7.5] × 0.50 = **0.40** ↵ **ĐXT = 24.00 + 0.40 = 24.40** ↵ → **Điểm xét tuyển ≈ 24.40**. ↵ Điểm chuẩn **CN KT Cơ điện tử** (7510203) năm **2025** = **25.17**. Với ĐXT **24.40 < 25.17** → **chưa đủ so với điểm chuẩn...
- **Ground Truth**: Tổng=24; ≥22.5→giảm dần; KV2-NT=0.50; ĐĐT=[(30-24)/7.5]×0.50=(6/7.5)×0.50=0.8×0.50=0.40; ĐXT=24.40; ĐC Cơ điện tử 2025=25.17; 24.40<25.17 → TRƯỢT. Thiếu khoảng 0.77 điểm
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### MULTI_10 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.4 | **Fact**: 0.33 | **Complete**: 4 | **Faith**: 4
- **Q**: Em có điểm D01: Toán 7, Văn 7.5, Anh 7.5 (tổng 22), KV2. Có thể vào ngành kinh tế nào ở HaUI?
- **Bot**: 📊 **Tính điểm xét tuyển PT3:** ↵ Tổng điểm 3 môn (thang 30): **22.00** ↵ Ưu tiên khu vực + đối tượng (cộng dồn): **+0.25** ↵ Vì 22.00 < 22.5 → cộng thẳng ưu tiên: **ĐXT = 22.00 + 0.25 = 22.25** ↵ → **Điểm xét tuyển ≈ 22.25**. ↵ Anh/chị muốn đối chiếu với điểm chuẩn ngành nào ạ?
- **Ground Truth**: Tổng=22; KV2=0.25; < 22.5→cộng thẳng; ĐXT=22.25; ĐC ngành kinh tế 2025: đỗ Kế toán(20.00), Kiểm toán(20.00), QT văn phòng(20.00), QTKD(20.25), Tài chính-NH(20.75), PTTDKD(20.00), QT nhân lực(21.25), KT đầu tư(21.25); TRƯỢT: Marketing(22.50), Logistics(22.76)
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### MULTI_12 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.78 | **Fact**: 0.67 | **Complete**: 4 | **Faith**: 4
- **Q**: GPA 3.60 (Xuất sắc), rèn luyện 91đ (Xuất sắc), 16TC, đang nhận HB HaUI. Có thêm được KKHT không?
- **Bot**: Dựa trên thông tin bạn cung cấp và quy định về học bổng Khuyến khích học tập (KKHT) của Trường Đại học Công nghiệp Hà Nội (HaUI): ↵  ↵ - GPA: 3.60 (Xuất sắc) ↵ - Rèn luyện: 91đ (Xuất sắc) ↵ - Số tín chỉ: 16TC ↵ - Đang nhận Học bổng HaUI toàn khóa ↵  ↵ Theo quy định, sinh viên đang nhận học bổng HaUI không được xét học bổng KKHT cùng kỳ. Do đó, bạn **không đủ điều kiện** để thêm vào học bổng Khuyến...
- **Ground Truth**: KHÔNG. Quy định KKHT: không xét cho SV đang nhận HB HaUI cùng học kỳ. Dù đủ điều kiện GPA/rèn luyện/TC, SV đang nhận HB HaUI sẽ không được xét KKHT cùng kỳ đó
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### MULTI_18 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 4.0 | **Fact**: 0.8 | **Complete**: 4 | **Faith**: 4
- **Q**: Em muốn lấy 2 bằng cùng lúc ở HaUI có được không và điều kiện thế nào?
- **Bot**: Em hoàn toàn có thể đăng ký học để nhận **2 bằng tốt nghiệp** từ Trường Đại học Công nghiệp Hà Nội (HaUI). Sinh viên sau khi hoàn thành chương trình năm thứ nhất có thể đăng ký học 2 chương trình đào tạo khác nhau cùng lúc. Điều kiện cụ thể như sau: ↵  ↵ - Hoàn thành xong năm học đầu tiên tại HaUI. ↵ - Đủ điều kiện và được chấp thuận từ phía trường cho việc đăng ký học song song hai chương trình. ...
- **Ground Truth**: Được. Điều kiện: hoàn thành chương trình năm thứ nhất mới được đăng ký học đồng thời chương trình thứ 2. Tốt nghiệp cả hai → được cấp 2 bằng tốt nghiệp. Lưu ý: các chính sách học bổng KKHT không áp dụng cho chương trình thứ 2
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### STRAT_06 [MINOR]
- **Tags**: CHUA_DU
- **Score**: 3.75 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 4
- **Q**: Em muốn chi phí học tập thấp nhất ở HaUI. Nên chọn ngành và chương trình gì?
- **Bot**: Để có chi phí học tập thấp nhất tại Trường Đại học Công nghiệp Hà Nội (HaUI), bạn nên cân nhắc các yếu tố như chương trình đào tạo đại trà thay vì tiếng Anh, hệ đào tạo từ xa hoặc liên thông vừa làm vừa học. Dưới đây là một số gợi ý: ↵  ↵ 1. **Chương trình Đào tạo Đại trà**: ↵    - Học phí: 700,000 đồng/tín chỉ (K20) ↵    - Ngành có điểm chuẩn thấp và phù hợp với khả năng của bạn sẽ giúp giảm chi ...
- **Ground Truth**: Chọn chương trình đại trà (700k/TC) thay vì TA (1tr/TC). Nếu đã là K19 trở về: 550k/TC (còn thấp hơn). Ngành chỉ tiêu lớn + ĐC thấp để dễ vào: Kế toán đại trà, Dệt may, Môi trường. KTX tiêu chuẩn CS2 phòng 6 người: 280k/tháng là thấp nhất. Tổng chi phí thấp nhất: ~18-22tr/năm
- **Root Cause**: 

#### STRAT_07 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.71 | **Fact**: 0.5 | **Complete**: 4 | **Faith**: 4
- **Q**: Em thích Hóa học, điểm B00 (Toán-Hóa-Sinh) khoảng 22 điểm, KV1. Nên đăng ký ngành nào ở HaUI?
- **Bot**: Dựa trên thông tin bạn cung cấp, em sẽ tư vấn cho bạn như sau: ↵  ↵ **Ngành Công nghệ thực phẩm (mã 7540101):** ↵ - Điểm chuẩn năm 2025: 20.6 điểm ↵ - Chỉ tiêu năm 2025: 120 sinh viên ↵ - Tổ hợp xét tuyển phù hợp với bạn: B00 (Toán-Hóa học-Sinh học) ↵  ↵ **Ngành Hóa dược (mã 7720203):** ↵ - Điểm chuẩn năm 2025: 21.35 điểm ↵ - Chỉ tiêu năm 2025: 60 sinh viên ↵ - Tổ hợp xét tuyển phù hợp với bạn: B0...
- **Ground Truth**: ĐXT=22 KV1 < 22.5 → cộng thẳng: ĐXT=22+0.75=22.75. Tổ hợp B00 dùng được cho: CNKT Hóa học (ĐC20.25 ✓), Hóa dược (ĐC21.35 ✓), Công nghệ thực phẩm (ĐC20.60 ✓), CNKT môi trường (ĐC18.75 ✓). Tất cả đều đỗ với ĐXT 22.75
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

#### TREND_02 [MINOR]
- **Tags**: CHUA_DU
- **Score**: 3.51 | **Fact**: 1.0 | **Complete**: 3 | **Faith**: 3
- **Q**: Điểm chuẩn Cơ điện tử HaUI qua 3 năm 2023-2025 thay đổi thế nào?
- **Bot**: Dựa trên thông tin từ dữ liệu đã cung cấp, điểm chuẩn ngành Công nghệ kỹ thuật cơ điện tử (mã 7510203) của Trường Đại học Công nghiệp Hà Nội (HaUI) trong các năm 2023-2025 thay đổi như sau: ↵  ↵ **Năm 2025:**   ↵ Điểm chuẩn chung: **25.17 điểm** ↵  ↵ **Năm 2024:**   ↵ - PT PT3 (thpt): **25.41 điểm** ↵ - PT PT4 (hoc_ba): **28.71 điểm** ↵ - PT PT2 (chung_chi_hsg): **26.01 điểm** ↵ - PT PT5 (danh_gia...
- **Ground Truth**: Cơ điện tử (7510303): 2023 PT3=24.63, PT4=28.55; 2024 PT3=25.41, PT4=28.71; 2025 chung=25.17. Xu hướng PT3 tăng từ 24.63→25.41. Điểm 2025 (25.17) giảm so với 2024 nhưng cần lưu ý thay đổi phương pháp tính điểm
- **Root Cause**: 

#### TREND_05 [MINOR]
- **Tags**: FACT_THIEU
- **Score**: 3.8 | **Fact**: 0.4 | **Complete**: 4 | **Faith**: 4
- **Q**: Điểm chuẩn Logistics HaUI qua các năm và ngành này có cạnh tranh không?
- **Bot**: **Điểm chuẩn ngành Logistics và quản lý chuỗi cung ứng (mã 7510605) tại Trường Đại học Công nghiệp Hà Nội (HaUI) qua các năm:** ↵  ↵ - **Năm 2025:** 22.76 điểm (thang 30) ↵ - **Năm 2024:**  ↵   - PT3 (THPT): 25.89 điểm ↵   - PT4 (Học bạ): 28.91 điểm ↵   - PT2 (Chứng chỉ HSG): 27.0 điểm ↵   - PT5 (Đánh giá năng lực): 19.5 điểm ↵ - **Năm 2023:**  ↵   - PT3 (THPT): 25.52 điểm ↵   - PT4 (Học bạ): 28.6...
- **Ground Truth**: Logistics (7510605): 2023 PT3=25.52, PT4=28.60; 2024 PT3=25.89, PT4=28.91; 2025 chung=22.76 (đổi phương pháp). Xu hướng PT3 tăng liên tục (25.52→25.89), chỉ tiêu 60 SV (ít) → cạnh tranh cao
- **Root Cause**: Answer không đầy đủ hoặc có chi tiết sai lệch.

---
## PHẦN 5: THỨ TỰ THỰC HIỆN

### Bước 1: Fix structured.py bugs (ảnh hưởng ~15 cases)
1. Sửa Robot mã ngành: `'robot': ('Robot và trí tuệ nhân tạo', '75102032')` (L172)
2. Sửa KTX chia tháng: `hp_per_month = hp_total / 4` (L367)
3. Verify SAT quy đổi vs `data/processed/diem_quy_doi.json`
4. Thêm parse HSA so sánh 2 giá trị (L391)
5. Thêm validate tổ hợp vs ngành trước khi tính điểm
6. Sửa inject chương trình TA đầy đủ (L1002-1011)
7. Đảm bảo `_compare_diem_chuan` luôn chạy khi `_has_admission_question`

### Bước 2: Fix pipeline.py router (ảnh hưởng ~8 cases)
1. Thêm alias 'máy tính' vào NGANH_ALIASES
2. Thêm trend pattern `\d+\s*năm\s*(gần nhất|qua|gần đây)`
3. Fix B1 guard cho 'đỗ vào các ngành nào' không cần KV
4. Fix C vs B1 khi có tổ hợp + điểm cụ thể
5. Fix D vs A2 khi có chứng chỉ + 'nên đăng ký'

### Bước 3: Thêm deterministic logic mới (ảnh hưởng ~12 cases)
1. `try_deterministic_kkht()`: parse GPA + rèn luyện + TC → xác định loại KKHT
2. `try_deterministic_hb_ntb()`: parse đối tượng + GPA + TC → xét HB NTB
3. `_validate_tohop_nganh()`: check tổ hợp hợp lệ cho ngành

### Bước 4: Fix prompts.py + max_tokens (ảnh hưởng ~30 cases)
1. Tăng max_tokens: A2→1200, D→1024
2. Thêm rule: 'Khi so sánh điều kiện, PHẢI viết X < Y → KẾT LUẬN'
3. Thêm rule: 'Thí sinh TN trước năm hiện hành TUYỆT ĐỐI không PT2/4/5'
4. Thêm rule: 'Khi context nói rõ điều kiện → kết luận dứt khoát, KHÔNG hedging'
5. Inject lịch 2026 vào enrich_context cho câu hỏi liên quan thời gian

### Bước 5: Verify
1. Chạy lại evaluation trên 196 test cases
2. So sánh score trước/sau
3. Kiểm tra tất cả 104 cases đã được cải thiện
