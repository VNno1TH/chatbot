"""
app.py — Flask API server for HaUI RAG Chatbot
Web chat (no login) + Admin panel (login required) + Telegram bot
"""
import os
import json
import shutil
import time
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

from src.config import (
    BASE_DIR, DATA_DIR, SECRET_KEY, HAUI_DEBUG, TELEGRAM_BOT_TOKEN
)
from src.api.auth import verify_admin, create_token, verify_token
from src.rag.pipeline import handle_query, load_index, reload_index
from src.rag.indexer import build_index

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = SECRET_KEY
CORS(app)

# ══════════════════════════════════════════
#  AUTH MIDDLEWARE
# ══════════════════════════════════════════

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token required'}), 401
        username = verify_token(token)
        if not username:
            return jsonify({'error': 'Invalid or expired token'}), 401
        return f(*args, **kwargs)
    return decorated

# ══════════════════════════════════════════
#  PAGES
# ══════════════════════════════════════════

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/admin')
def admin_page():
    return send_from_directory('static', 'admin.html')

# ══════════════════════════════════════════
#  PUBLIC API — Chat (no login)
# ══════════════════════════════════════════

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    if not data or 'message' not in data:
        return jsonify({'error': 'Missing message'}), 400

    user_message = data['message'].strip()
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400

    try:
        result = handle_query(user_message)
        return jsonify({
            'answer': result.get('answer', ''),
            'intent': result.get('intent', ''),
            'time': result.get('time', 0),
            'num_chunks': result.get('num_chunks', 0)
        })
    except Exception as e:
        if HAUI_DEBUG:
            print(f"[CHAT ERROR] {e}")
        return jsonify({
            'answer': 'Xin lỗi, em gặp lỗi khi xử lý. Anh/chị thử lại sau nhé!',
            'intent': 'error',
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'timestamp': time.time()})

# ══════════════════════════════════════════
#  ADMIN API — Login
# ══════════════════════════════════════════

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')

    if verify_admin(username, password):
        token = create_token(username)
        return jsonify({'token': token, 'username': username})
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

# ══════════════════════════════════════════
#  ADMIN API — Data management
# ══════════════════════════════════════════

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """Get indexing stats."""
    from rag_pipeline import _collection, _chunks
    stats = {
        'total_chunks': len(_chunks) if _chunks else 0,
        'chroma_docs': _collection.count() if _collection else 0,
        'data_files': []
    }

    if os.path.exists(DATA_DIR):
        for f in sorted(os.listdir(DATA_DIR)):
            fpath = os.path.join(DATA_DIR, f)
            if os.path.isfile(fpath):
                stats['data_files'].append({
                    'name': f,
                    'size': os.path.getsize(fpath),
                    'type': 'json' if f.endswith('.json') else 'md'
                })

    return jsonify(stats)

@app.route('/api/admin/upload', methods=['POST'])
@admin_required
def admin_upload():
    """Upload new data file and re-index."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'No filename'}), 400

    allowed = file.filename.endswith('.json') or file.filename.endswith('.md')
    if not allowed:
        return jsonify({'error': 'Only .json and .md files allowed'}), 400

    # Save file
    save_path = os.path.join(DATA_DIR, file.filename)
    file.save(save_path)

    # Re-index
    try:
        build_index(DATA_DIR)
        reload_index()
        return jsonify({
            'message': f'File {file.filename} uploaded and indexed successfully',
            'filename': file.filename
        })
    except Exception as e:
        return jsonify({'error': f'Index failed: {str(e)}'}), 500

@app.route('/api/admin/reindex', methods=['POST'])
@admin_required
def admin_reindex():
    """Manually trigger re-indexing."""
    try:
        build_index(DATA_DIR)
        reload_index()
        from src.rag.pipeline import _collection, _chunks
        return jsonify({
            'message': 'Re-indexing completed',
            'total_chunks': len(_chunks) if _chunks else 0,
            'chroma_docs': _collection.count() if _collection else 0
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/delete/<filename>', methods=['DELETE'])
@admin_required
def admin_delete(filename):
    """Delete a data file."""
    fpath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(fpath):
        return jsonify({'error': 'File not found'}), 404
    os.remove(fpath)
    return jsonify({'message': f'{filename} deleted'})


# ══════════════════════════════════════════
#  STARTUP
# ══════════════════════════════════════════

def init_app():
    """Initialize on startup."""
    print("\n" + "=" * 60)
    print("  🎓 HaUI RAG Chatbot v2.2")
    print("=" * 60)

    # Load index
    load_index()

    # Start Telegram bot (only in reloader child process to avoid duplicate instances)
    if TELEGRAM_BOT_TOKEN:
        # In debug mode, Flask spawns 2 processes. Only start bot in the child.
        is_reloader_child = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
        if is_reloader_child or not HAUI_DEBUG:
            from src.bot.telegram import start_telegram_bot_async
            start_telegram_bot_async()
        else:
            print("  ⏳ Telegram bot sẽ khởi động khi reloader sẵn sàng...")

    print("\n  ✓ Server ready!")
    print("  🌐 Web: http://localhost:5000")
    print("  🔧 Admin: http://localhost:5000/admin")
    if TELEGRAM_BOT_TOKEN:
        print("  📱 Telegram bot: running")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    init_app()
    app.run(host='0.0.0.0', port=5000, debug=HAUI_DEBUG)
