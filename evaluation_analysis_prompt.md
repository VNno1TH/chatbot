

**Đóng vai trò là một Chuyên gia Kỹ sư AI & Kiến trúc sư RAG (Retrieval-Augmented Generation) cấp cao.**

Tôi cung cấp cho bạn dữ liệu từ file `evaluation_results.json`. Đây là file chứa các kết quả đánh giá (evaluation) chi tiết về hệ thống chatbot hiện tại của tôi qua các bài test.

**🎯 MỤC TIÊU CỐT LÕI:**
Nhiệm vụ của bạn là đọc thật sâu dữ liệu này, phân tích các điểm yếu và lập ra một **Kế hoạch cải thiện hệ thống toàn diện**. Mục tiêu tối thượng là tối ưu hóa để chatbot trả lời chính xác hơn, đạt điểm đánh giá (score) cao hơn, và đảm bảo câu trả lời của chatbot (`answer`) phải khớp chính xác và đầy đủ thông tin so với đáp án chuẩn định kiến (`ground_truth_full`).

**🔍 YÊU CẦU THỰC HIỆN CỤ THỂ:**

1. **Phân tích Lỗi & Nhóm Lỗi (Error Categorization):**
   - Hãy rà soát các test case bị điểm thấp hoặc có sự sai lệch giữa `answer` và `ground_truth_full`.
   - Phân loại lỗi thuộc về thành phần nào trong pipeline: Do phân loại sai ý định (Router)? Truy xuất thiếu/sai tài liệu (Retriever)? Xử lý logic/tính toán sai (Structured)? Hay LLM sinh ra ảo giác/thiếu ý (Generator)?

2. **Tìm Nguyên Nhân Gốc Rễ (Root Cause Analysis):**
   - Chỉ ra lý do vì sao chatbot lại thất bại ở các case đó. (Ví dụ: do top_K quá nhỏ, chunking không hợp lý, prompt thiếu tính ràng buộc, hay do logic code RAG đang bị rẽ nhánh sai?).

3. **Mạnh dạn Đề xuất Thay đổi Thiết kế (Architecture/Design Overhaul):**
   - Hãy soi xét thiết kế hệ thống hiện tại được thể hiện qua các lỗi. Nếu hướng tiếp cận, luồng pipeline hoặc cấu trúc thiết kế hiện tại là **sai lầm, quá cồng kềnh hoặc không phù hợp**, hãy dũng cảm đề xuất đập bỏ và thay đổi kiến trúc mới. Tôi ưu tiên sự chính xác tuyệt đối và sẵn sàng refactor code diện rộng nếu cần.

4. **Lập Kế hoạch Hành động Chi tiết (Step-by-Step Action Plan):**
   - Trình bày kế hoạch sửa chữa theo thứ tự ưu tiên (việc gì mang lại hiệu quả cao nhất thì làm trước).
   - Đưa ra các kỹ thuật RAG nâng cao nên áp dụng để trị các lỗi hiện tại (như Hybrid Search, Query Rewriting, Self-Correction, Multi-agent routing, v.v.).
   - Cung cấp cấu trúc hệ thống hoặc các đoạn mã/prompt giả mã (pseudocode) hướng dẫn cách thực thi việc cải tiến.

**⚠️ RÀNG BUỘC NGHIÊM NGẶT (ANTI-LAZINESS):**
File dữ liệu tôi gửi rất dài. Tôi nghiêm cấm việc bạn chỉ đọc lướt một vài test case đầu tiên rồi đưa ra kết luận.
- Bạn **PHẢI** rà soát từ đầu đến cuối file.
- Hãy liệt kê hoặc gom nhóm **TẤT CẢ** các câu hỏi (queries) bị trả lời sai/điểm thấp vào các danh mục lỗi cụ thể (ví dụ: "Nhóm lỗi tính học phí gồm các câu: [X, Y, Z]", "Nhóm lỗi trả lời chung chung thiếu ý gồm các câu: [A, B, C]").
- Đảm bảo rằng không có bất kỳ test case lỗi nào bị bỏ sót trong bản phân tích của bạn. Tôi sẽ kiểm tra lại từng lỗi một dựa trên báo cáo của bạn.

Hãy trả lời bằng một báo cáo markdown chuyên nghiệp, mạch lạc và đi thẳng vào các giải pháp thực tế có thể code ngay được. Không trả lời chung chung.
