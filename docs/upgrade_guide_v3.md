# 🚀 Kế hoạch Nâng cấp HaUI RAG Chatbot (v3.0)

Tài liệu hướng dẫn chi tiết các hạng mục nâng cấp hệ thống tư vấn tuyển sinh đại học để đạt tiêu chuẩn ứng dụng thương mại Enterprise, hỗ trợ ăn điểm tối đa trước Hội đồng Bảo vệ. Mọi cải tiến đều KHÔNG yêu cầu đổi cấu trúc RAG cốt lõi.

---

## 1. Nâng cấp Trải nghiệm Người dùng (UX/UI) & Giao diện

Nâng cấp tương tác giúp hệ thống trông thông minh, chuyên nghiệp và có "hơi thở" giống với ChatGPT nhất có thể.

### 1.1. Streaming Response (Hiệu ứng gõ phím SSE)
*   **Giá trị:** Loại bỏ thời gian chờ đợi rỗng. Chữ được xuất ra màn hình Frontend ngay khi LLM nhả từng token.
*   **Lưu ý quan trọng:** Toàn bộ pipeline RAG (Router → Rewrite → HyDE → Search → Rerank → Self-Reflect) vẫn phải chạy xong **TRƯỚC** khi bắt đầu stream. Chỉ có bước cuối cùng — hàm `generate_response()` (gọi `call_llm` tại dòng 830 `pipeline.py`) — mới stream được. Nghĩa là người dùng sẽ vẫn chờ ~1-2s cho RAG retrieve, sau đó chữ bắt đầu chảy ra liên tục thay vì chờ thêm 3-5s nữa rồi mới nhận cả cục.
*   **Cách triển khai:**

    **Bước 1 — Backend: Tách hàm generate ra khỏi pipeline (`pipeline.py`)**
    *   Tạo hàm mới `handle_query_stream(user_query)` bên cạnh `handle_query()` hiện tại.
    *   Hàm này chạy toàn bộ bước 1→12 (route, rewrite, search, rerank, build context) y nguyên code cũ.
    *   Riêng bước 13 (Generate), thay vì gọi `call_llm()` đồng bộ, gọi Ollama SDK với `stream=True`:
    ```python
    def stream_generate(prompt, model=None, max_tokens=1024):
        """Yield từng đoạn text khi LLM nhả ra."""
        client = get_ollama_client()
        for chunk in client.generate(model=model or OLLAMA_MODEL,
                                     prompt=prompt,
                                     stream=True,
                                     options={'num_predict': max_tokens, 'temperature': 0.02}):
            yield chunk['response']
    ```

    **Bước 2 — Backend: Tạo endpoint SSE mới (`app.py`)**
    *   Thêm route `/api/chat/stream` trả về `text/event-stream`:
    ```python
    from flask import Response, stream_with_context

    @app.route('/api/chat/stream', methods=['POST'])
    def chat_stream():
        data = request.get_json()
        user_message = data['message'].strip()

        def generate():
            for token in handle_query_stream(user_message):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"

        return Response(stream_with_context(generate()),
                        content_type='text/event-stream')
    ```

    **Bước 3 — Frontend: Đọc stream (`app.js`)**
    *   Thay đổi hàm `sendMessage()` (hiện đang ở dòng 43 `app.js`). Thay vì `await fetch → response.json()`, dùng Streams API:
    ```javascript
    const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
    });
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let botText = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value);
        // Parse SSE format: "data: ...\n\n"
        for (const line of chunk.split('\n')) {
            if (line.startsWith('data: ') && line !== 'data: [DONE]') {
                botText += line.slice(6);
                // Cập nhật nội dung tin nhắn bot đang hiển thị
                botMessageContent.innerHTML = marked.parse(botText);
            }
        }
    }
    ```

### 1.2. Conversation History (Cửa sổ Ngữ cảnh Trò chuyện)
*   **Giá trị:** Chatbot có thể "nhớ" câu hỏi trước đó để duy trì một cuộc hội thoại đa lượt mượt mà (ví dụ: *"Ngành đó học phí bao nhiêu?"* - AI hiểu chữ *"ngành đó"* nghĩa là ngành nào).
*   **Cách triển khai (Không cần đăng nhập):**

    **Bước 1 — Frontend (`app.js`): Sinh Session ID**
    *   Ngay đầu file, thêm logic sinh và lưu ID phiên:
    ```javascript
    // Sinh session_id 1 lần duy nhất khi mở tab
    let sessionId = sessionStorage.getItem('haui_session_id');
    if (!sessionId) {
        sessionId = 'sess_' + crypto.randomUUID();
        sessionStorage.setItem('haui_session_id', sessionId);
    }
    ```
    *   Trong hàm `sendMessage()`, khi gọi `fetch`, gửi kèm ID:
    ```javascript
    body: JSON.stringify({ message, session_id: sessionId })
    ```

    **Bước 2 — Backend (`app.py`): Lưu trữ lịch sử theo session**
    *   Thêm biến toàn cục lưu lịch sử và giới hạn 3-5 cặp trò chuyện gần nhất:
    ```python
    from collections import defaultdict
    chat_histories = defaultdict(list)  # { session_id: [{role, content}, ...] }
    MAX_HISTORY = 3  # Giữ tối đa 3 lượt hỏi-đáp gần nhất
    ```
    *   Trong hàm `chat()`, đọc lịch sử và truyền vào pipeline:
    ```python
    session_id = data.get('session_id', '')
    history = chat_histories.get(session_id, [])[-MAX_HISTORY*2:]

    result = handle_query(user_message, history=history)

    # Cập nhật lịch sử
    if session_id:
        chat_histories[session_id].append({'role': 'user', 'content': user_message})
        chat_histories[session_id].append({'role': 'bot', 'content': result.get('answer', '')})
        # Cắt bớt nếu quá dài
        if len(chat_histories[session_id]) > MAX_HISTORY * 2:
            chat_histories[session_id] = chat_histories[session_id][-MAX_HISTORY*2:]
    ```

    **Bước 3 — Pipeline (`pipeline.py`): Chèn lịch sử vào Prompt**
    *   Sửa hàm `handle_query()` nhận thêm tham số `history=None`.
    *   Trong hàm `generate_response()` (dòng 661), chèn lịch sử **SAU** `SYSTEM_PROMPT + context` và **TRƯỚC** câu hỏi hiện tại:
    ```python
    def generate_response(query, context, intent, history=None):
        system = SYSTEM_PROMPT_TEMPLATE.replace('{context}', context).replace('{intent}', intent)
        
        # Chèn lịch sử hội thoại (nếu có)
        history_block = ""
        if history:
            history_block = "\n\n[LỊCH SỬ HỘI THOẠI GẦN ĐÂY]\n"
            for turn in history:
                role = "Học sinh" if turn['role'] == 'user' else "Trợ lý"
                history_block += f"{role}: {turn['content'][:200]}\n"
            history_block += "[HẾT LỊCH SỬ]\n"
        
        prompt = f"{system}{VI_RULE}{history_block}\n\nCâu hỏi của người dùng: {query}"
    ```
    *   **Lý do chèn ở vị trí này:** Context RAG nằm trong `system` (đã có dữ liệu tuyển sinh), lịch sử nằm ngay sau để LLM biết đã nói gì, cuối cùng mới là câu hỏi hiện tại. Thứ tự này đảm bảo LLM ưu tiên dữ liệu nguồn > lịch sử > câu hỏi.

### 1.3. Cơ chế Đánh giá Feedback (Human-in-the-loop)
*   **Giá trị:** Thể hiện khả năng "Tự huấn luyện" và quản lý chất lượng AI.
*   **Cách triển khai:**

    **Bước 1 — Frontend (`app.js`): Thêm nút 👍👎**
    *   Trong hàm `addMessage()` (dòng 93), khi `type === 'bot'`, chèn thêm HTML nút feedback vào cuối `content`:
    ```javascript
    if (type === 'bot') {
        const feedbackDiv = document.createElement('div');
        feedbackDiv.className = 'feedback-buttons';
        feedbackDiv.innerHTML = `
            <button onclick="sendFeedback(this, 'up')" title="Câu trả lời tốt">👍</button>
            <button onclick="sendFeedback(this, 'down')" title="Câu trả lời chưa tốt">👎</button>
        `;
        content.appendChild(feedbackDiv);
    }
    ```

    **Bước 2 — Backend (`app.py`): Tạo endpoint nhận feedback**
    ```python
    @app.route('/api/feedback', methods=['POST'])
    def feedback():
        data = request.get_json()
        # data = { type: 'up'|'down', question: '...', answer: '...', comment: '...' }
        log_entry = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'type': data.get('type'),
            'question': data.get('question', ''),
            'answer': data.get('answer', '')[:300],
            'comment': data.get('comment', '')
        }
        # Ghi vào file JSON log
        log_path = os.path.join(BASE_DIR, 'data', 'feedback_log.json')
        # ... append vào file ...
        return jsonify({'status': 'ok'})
    ```

    **Bước 3 — Admin (`admin.js`): Hiển thị bảng feedback**
    *   Tạo endpoint `/api/admin/feedback` (có `@admin_required`) trả về danh sách feedback.
    *   Hiển thị dạng bảng HTML trên trang `admin.html`, đánh dấu các feedback 👎 bằng màu đỏ để Admin duyệt nhanh.

---

## 2. Nâng cấp Admin Dashboard & Phân tích Dữ liệu (Analytics)

Cung cấp cho trường Đại học bảng điều khiển thông minh để thấu hiểu nguyện vọng của học sinh dựa trên dữ liệu chat.

### 2.1. Cấu trúc lại giao diện trang `admin.html`
*   **Giá trị:** Chuyển đổi từ trang công cụ upload khô khan thành Bảng điều khiển quản trị (Control Center).
*   **Cách triển khai:** Tích hợp bộ thư viện **Chart.js** (miễn phí, chỉ cần thêm 1 thẻ `<script>` CDN) vào `admin.html`.

### 2.2. Tracking Hành vi và Góp nhặt Dữ liệu
*   **Cần tạo file mới:** `src/analytics.py` — module chuyên ghi log và đọc thống kê.
*   **Vị trí chèn code ghi log:** Cuối hàm `handle_query()` trong `pipeline.py` (ngay sau dòng 842, trước `return result`):
    ```python
    # === GHI LOG ANALYTICS ===
    from src.analytics import log_query
    log_query(
        question=user_query,
        intent=intent,
        ma_nganh=entities.get('ma_nganh', ''),
        ten_nganh=entities.get('ten_nganh', ''),
        response_time=result['time'],
        num_chunks=len(docs)
    )
    ```
*   **Cấu trúc file `src/analytics.py`:**
    ```python
    import json, os, time
    from src.config import BASE_DIR

    LOG_PATH = os.path.join(BASE_DIR, 'data', 'analytics_log.json')

    def log_query(question, intent, ma_nganh, ten_nganh, response_time, num_chunks):
        entry = {
            'ts': time.strftime('%Y-%m-%d %H:%M:%S'),
            'question': question[:200],
            'intent': intent,
            'ma_nganh': ma_nganh,
            'ten_nganh': ten_nganh,
            'time': response_time,
            'chunks': num_chunks
        }
        # Append vào file JSON
        logs = []
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        logs.append(entry)
        with open(LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)

    def get_stats():
        """Trả về thống kê cho Admin Dashboard."""
        if not os.path.exists(LOG_PATH):
            return {'total': 0, 'intents': {}, 'top_majors': []}
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            logs = json.load(f)
        # Đếm intent
        intents = {}
        majors = {}
        for log in logs:
            i = log.get('intent', 'unknown')
            intents[i] = intents.get(i, 0) + 1
            tn = log.get('ten_nganh', '')
            if tn:
                majors[tn] = majors.get(tn, 0) + 1
        top_majors = sorted(majors.items(), key=lambda x: -x[1])[:10]
        return {'total': len(logs), 'intents': intents, 'top_majors': top_majors}
    ```
*   **Endpoint Admin (`app.py`):** Thêm route `/api/admin/analytics` gọi `get_stats()` trả JSON cho Frontend vẽ biểu đồ.

### 2.3. Các Biểu đồ Thống kê khuyên xây dựng:
1.  **Biểu đồ đường tròn (Pie Chart):** Thể hiện % Ý định câu hỏi (VD: Tra điểm chuẩn chiếm 60%, Thủ tục 30%, Chit-chat 10%).
2.  **Biểu đồ cột (Bar Chart):** Top 5-10 ngành học được tra cứu nhiều nhất trong ngày/tuần (rất hữu ích cho Marketing Tuyển sinh).
3.  **Bảng dữ liệu (Data Table):** Hiển thị những Feedback 👎 để Admin kiểm tra lại độ ảo giác của LLM.
4.  **Thẻ số liệu (Stat Cards):** Tổng số câu hỏi đã xử lý, thời gian phản hồi trung bình, tỷ lệ cache hit (nếu sau này bật cache).

---

## 3. Tích hợp Đa kênh (Omnichannel) — Facebook Messenger

Mở rộng điểm chạm để học sinh có thể chat trực tiếp với AI Tuyển sinh thông qua Fanpage của Nhà trường thay vì chỉ dùng Web/Telegram. Đây là điểm nhấn cực mạnh về tính "Thực tiễn".

### 3.1. Giá trị mang lại
*   Mang sản phẩm ra môi trường có lượng người dùng học sinh cấp 3 lớn nhất Việt Nam.
*   Miễn phí hoàn toàn (không như Zalo bắt buộc phải xác thực doanh nghiệp). 
*   Bot tự động trả lời 24/7 giúp giảm tải 90% công việc cho cán bộ tư vấn tuyển sinh.

### 3.2. Cách triển khai (Không tốn phí)

**Bước 1 — Thiết lập phía Facebook:**
*   Tạo một Fanpage Facebook (Ví dụ: "Tư vấn Tuyển sinh HaUI").
*   Vào trang [Meta for Developers](https://developers.facebook.com/), tạo một Ứng dụng (App) kết nối với Fanpage đó.
*   Lấy `PAGE_ACCESS_TOKEN` và chọn một `VERIFY_TOKEN` tùy ý (chuỗi bí mật do bạn tự đặt).

**Bước 2 — Tạo file mới `src/bot/facebook.py`** (song song với `src/bot/telegram.py`):
```python
"""
facebook.py — Facebook Messenger Webhook integration
Kiến trúc tương tự telegram.py: nhận tin nhắn → gọi handle_query → trả kết quả.
"""
import requests
from flask import Blueprint, request, jsonify
from src.config import FB_PAGE_TOKEN, FB_VERIFY_TOKEN
from src.rag.pipeline import handle_query

fb_bp = Blueprint('facebook', __name__)

@fb_bp.route('/api/webhook/facebook', methods=['GET'])
def verify():
    """Facebook xác minh Webhook (chạy 1 lần duy nhất khi đăng ký)."""
    if request.args.get('hub.verify_token') == FB_VERIFY_TOKEN:
        return request.args.get('hub.challenge', '')
    return 'Invalid token', 403

@fb_bp.route('/api/webhook/facebook', methods=['POST'])
def webhook():
    """Nhận tin nhắn từ Messenger, xử lý và trả lời."""
    data = request.get_json()
    for entry in data.get('entry', []):
        for event in entry.get('messaging', []):
            sender_id = event['sender']['id']
            if 'message' in event and 'text' in event['message']:
                user_text = event['message']['text']
                result = handle_query(user_text)
                answer = result.get('answer', 'Xin lỗi, em chưa xử lý được.')
                send_message(sender_id, answer)
    return jsonify({'status': 'ok'})

def send_message(recipient_id, text):
    """Gửi tin nhắn về Messenger qua Graph API."""
    # Cắt nếu text quá 2000 ký tự (giới hạn Messenger)
    if len(text) > 2000:
        text = text[:2000] + '...'
    requests.post(
        'https://graph.facebook.com/v19.0/me/messages',
        params={'access_token': FB_PAGE_TOKEN},
        json={
            'recipient': {'id': recipient_id},
            'message': {'text': text}
        }
    )
```

**Bước 3 — Đăng ký Blueprint trong `app.py`:**
*   Thêm vào phần `init_app()` (hiện tại dòng 192), tương tự cách Telegram đang được khởi tạo (dòng 202-209):
```python
# Facebook Messenger webhook
from src.bot.facebook import fb_bp
app.register_blueprint(fb_bp)
print("  📘 Facebook Webhook: /api/webhook/facebook")
```

**Bước 4 — Cấu hình `.env` và `config.py`:**
*   Thêm 2 biến vào `.env`:
```env
FB_PAGE_TOKEN=your_page_access_token
FB_VERIFY_TOKEN=your_custom_verify_string
```
*   Thêm vào `src/config.py`:
```python
FB_PAGE_TOKEN = os.getenv("FB_PAGE_TOKEN", "")
FB_VERIFY_TOKEN = os.getenv("FB_VERIFY_TOKEN", "haui-fb-verify-2026")
```

**Bước 5 — Kiểm thử ở Localhost:**
*   Dùng **Cloudflare Tunnel** (lệnh `cloudflared tunnel --url http://localhost:5000`) để tạo đường dẫn HTTPS public miễn phí.
*   Dán đường dẫn `https://xxx.trycloudflare.com/api/webhook/facebook` vào cấu hình Webhook trên trang Meta App.
*   Vì App ở chế độ Development Mode, chỉ những tài khoản Facebook được thêm vào danh sách "Tester" mới chat được (đủ dùng cho demo đồ án, không cần xin Review chính thức).

---

## 4. Cập nhật Bộ kiểm thử (Evaluation)

Hệ thống đã có bộ đánh giá RAGAS 8 metrics rất mạnh trong `tests/evaluate.py`. Sau khi bổ sung các tính năng mới, cần mở rộng bộ test để đảm bảo chất lượng.

### 4.1. Thêm test case Multi-turn
*   Bổ sung vào `tests/test_dataset.json` các bộ câu hỏi chuỗi (multi-turn) để kiểm tra Conversation History:
    *   Câu 1: *"Điểm chuẩn ngành Kế toán?"* → Kỳ vọng: trả đúng điểm.
    *   Câu 2 (cùng session): *"Ngành đó cần tổ hợp gì?"* → Kỳ vọng: trả tổ hợp của ngành **Kế toán** (không phải hỏi lại ngành nào).

### 4.2. Kiểm tra Feedback logging
*   Viết script nhỏ gửi vài request mẫu tới `/api/feedback`, sau đó kiểm tra file `data/feedback_log.json` có ghi đúng không.

### 4.3. Kiểm tra Analytics tracking
*   Sau khi chạy vài câu hỏi test, kiểm tra file `data/analytics_log.json` có ghi đúng intent, mã ngành, thời gian không.
*   Gọi `/api/admin/analytics` để xác nhận dữ liệu biểu đồ trả về đúng format.

---

> 💡 **Thứ tự triển khai khuyến nghị:**
> 1. **Conversation History** (Mục 1.2) — Thay đổi ít file, hiệu quả trình diễn cao nhất.
> 2. **Analytics Dashboard** (Mục 2) — Trực quan, demo rất ấn tượng với biểu đồ Chart.js.
> 3. **Feedback** (Mục 1.3) — Bổ trợ cho Dashboard, code đơn giản.
> 4. **SSE Streaming** (Mục 1.1) — Code phức tạp hơn nhưng WOW factor cao.
> 5. **Facebook Messenger** (Mục 3) — Làm cuối nếu thừa thời gian.
