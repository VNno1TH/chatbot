# 🎓 HaUI RAG Chatbot

Trợ lý ảo Tư vấn Tuyển sinh Đại học Công nghiệp Hà Nội (HaUI). 
Hệ thống sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)** nâng cao, kết hợp giữa Vector Search và Full-text Search (BM25), được thiết kế đặc biệt để tính toán điểm chuẩn chính xác, tư vấn ngành học, và giải đáp các thắc mắc về thủ tục tuyển sinh hoàn toàn bằng Tiếng Việt.

---

## 🎯 Tính năng nổi bật

- **Hybrid Search RAG**: Trích xuất dữ liệu kết hợp giữa Vector Search (BGE-M3 + ChromaDB) và BM25, hợp nhất bằng thuật toán RRF (Reciprocal Rank Fusion).
- **Phân luồng thông minh (Router)**: Có khả năng tự động bóc tách các câu hỏi dạng tra cứu, small talk, hoặc các query nằm ngoài phạm vi tư vấn.
- **Tính toán điểm chuẩn Deterministic**: Cài đặt sẵn logic tính điểm chính xác bằng code (quy đổi chứng chỉ tiếng Anh, chứng chỉ ĐGNL / ĐGTD, điểm xét tuyển PT2, PT3, ưu tiên khu vực) giúp giảm tải cho LLM và bảo đảm 100% độ chính xác.
- **RAG_LITE Mode**: Tối ưu tốc độ trả lời (giảm từ 10s xuống còn 2-3s) đối với các câu hỏi đơn giản hoặc các phép tính toán được định tuyến cứng cài trong hệ thống.
- **Giao diện Glassmorphism 3D**: Giao diện Premium Web UI kết hợp hiệu ứng Float 3D, hỗ trợ render Markdown bảng biểu tuyệt đẹp.
- **Telegram Bot**: Tự động chạy ngầm song song với máy chủ Flask để hỗ trợ tra cứu trực tiếp qua Telegram.

---

## 🏗️ Kiến trúc thư mục (Clean Architecture)

Sau phiên bản v2.2, toàn bộ codebase đã được tái cấu trúc triệt để nhằm đảm bảo tính dễ bảo trì và mở rộng:

```text
chatbot_doan/
├── app.py                # Server Flask (Entry point)
├── config.py             # (Nằm trong src/config.py)
├── .env                  # Tệp lưu biến môi trường (Secrets, Token)
├── requirements.txt      # Module Python phụ thuộc cần thiết
├── data/                 # Chứa dữ liệu Database cục bộ
│   ├── processed/        # Chứa dữ liệu JSON/MD nguồn thu thập từ web HaUI
│   └── vectorstore/      # Chứa CSDL ChromaDB và BM25 Cache
├── static/               # Giao diện Frontend
│   ├── index.html        # Trang Web người dùng
│   ├── app.js            # Frontend Logic 
│   ├── style.css         # UI Design
│   └── admin.*           # Web Quản trị
├── docs/                 # Tài liệu hướng dẫn RAG Technical
├── tests/                # Evaluate Scripts (kiểm thử chất lượng RAGAS)
└── src/                  # Mã nguồn lõi (Core Engine)
    ├── config.py         # App Config Path & Params
    ├── api/
    │   └── auth.py       # Authentication Controller cho Admin
    ├── rag/              
    │   ├── chunking.py   # Lọc, xẻ mảnh văn bản & cấu trúc dữ liệu
    │   ├── indexer.py    # Đồng bộ & nạp dữ liệu vào Database
    │   ├── pipeline.py   # RAG Engine (Router → Rerank → LLM Generate) 
    │   ├── structured.py # Hàm tính điểm Regex (Deterministic Fallbacks)
    │   └── prompts.py    # Prompt cốt lõi, Rules và Instructions
    └── bot/
        └── telegram.py   # Worker chạy Telegram API
```

---

## 🚀 Hướng dẫn Cài đặt & Sử dụng

### 1. Yêu cầu Hệ thống
- **Python**: `>= 3.10`
- **Ollama**: Backend LLM để xử lý inference.

### 2. Cài đặt Môi trường
Tạo và kích hoạt môi trường ảo (khuyến nghị dùng Conda):

```bash
conda create -n hauichatbot python=3.10 -y
conda activate hauichatbot
```

Cài đặt các gói thư viện phụ thuộc:
```bash
pip install -r requirements.txt
```

### 3. Cài đặt Models cho Ollama
Bật Ollama chạy ngầm, sau đó tải các mô hình tiêu chuẩn được dùng trong hệ thống:
```bash
# Model Sinh text chính
ollama pull qwen2.5:14b

# Model Embeddings (để chuyển văn bản thành Vector)
ollama pull bge-m3
```

### 4. Nạp Dữ liệu (Indexing)
Bạn cần nạp các tài liệu văn bản (`/data/processed`) vào cơ sở dữ liệu Vector để Chatbot có đủ kiến thức:
```bash
python -m src.rag.indexer
```

### 5. Khởi chạy
Chạy ứng dụng bằng lệnh:
```bash
python app.py
```

- **Chat UI**: http://localhost:5000
- **Admin Panel**: http://localhost:5000/admin (Dùng để kiểm soát / upload dữ liệu trực tiếp lên DB).

---

## ⚙️ Cấu hình Môi trường (.env)

Đổi / điền thông tin các cấu hình cơ sở trong tệp `.env` tại thư mục root (nếu chưa có thì tự tạo mới):

```env
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=your_flask_secret_key

# Model Settings
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
OLLAMA_EMBED_MODEL=bge-m3

# Telegram API
TELEGRAM_BOT_TOKEN=token_su_dung_trong_telegram_bot_father
```
