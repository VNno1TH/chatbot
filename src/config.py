"""
Configuration module — load settings from .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Ollama ──
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11435")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "bge-m3:latest")

# ── Router ──
ROUTER_MODEL = os.getenv("ROUTER_MODEL", OLLAMA_MODEL)
ROUTER_TIMEOUT = int(os.getenv("ROUTER_TIMEOUT", "20"))

# ── Reranker ──
RERANKER_URL = os.getenv("RERANKER_URL", "http://localhost:8080")
USE_REMOTE_RERANKER = os.getenv("USE_REMOTE_RERANKER", "1") == "1"

# ── Retriever features ──
HYDE_ENABLED = os.getenv("HYDE_ENABLED", "1") == "1"
QUERY_REWRITE_ENABLED = os.getenv("QUERY_REWRITE_ENABLED", "1") == "1"
SELF_REFLECT_ENABLED = os.getenv("SELF_REFLECT_ENABLED", "1") == "1"
RETRIEVER_LLM_TIMEOUT = int(os.getenv("RETRIEVER_LLM_TIMEOUT", "6"))
# Tối ưu tốc độ: chỉ bật HyDE / self-reflect cho intent cần retrieve rộng (mặc định A2, B2)
RAG_LITE = os.getenv("RAG_LITE", "1") == "1"
_HYDE_I = os.getenv("HYDE_INTENTS", "A2,B2").strip()
HYDE_INTENTS = frozenset(x.strip() for x in _HYDE_I.split(",") if x.strip()) if _HYDE_I else None
_REF_I = os.getenv("SELF_REFLECT_INTENTS", "A2,B2").strip()
SELF_REFLECT_INTENTS = frozenset(x.strip() for x in _REF_I.split(",") if x.strip()) if _REF_I else None

# ── Debug ──
HAUI_DEBUG = os.getenv("HAUI_DEBUG", "0") == "1"

# ── Paths ──
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
NGANH_DIR = os.path.join(DATA_DIR, "nganh")
VECTORSTORE_DIR = os.path.join(BASE_DIR, "data", "vectorstore", "chroma_db")
BM25_PATH = os.path.join(BASE_DIR, "data", "vectorstore", "bm25_index.pkl")
CHUNKS_PATH = os.path.join(BASE_DIR, "data", "vectorstore", "chunks.pkl")

# ── Telegram ──
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── Admin ──
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "haui2026")
SECRET_KEY = os.getenv("SECRET_KEY", "haui-chatbot-secret-key-2026")

# ── Embedding dimensions ──
EMBED_DIM = 1024  # BGE-M3 output dimension

# ── Facebook Messenger ──
FB_PAGE_TOKEN   = os.getenv('FB_PAGE_TOKEN', '')
FB_VERIFY_TOKEN = os.getenv('FB_VERIFY_TOKEN', 'haui-fb-verify-2026')
