"""
facebook.py — Facebook Messenger Webhook integration (Flask Blueprint).
Architecture mirrors telegram.py: receive → handle_query → reply.
"""
from __future__ import annotations

import requests
from flask import Blueprint, request, jsonify

from src.config import FB_PAGE_TOKEN, FB_VERIFY_TOKEN, HAUI_DEBUG
from src.rag.pipeline import handle_query

fb_bp = Blueprint('facebook', __name__)

_GRAPH_API_URL = 'https://graph.facebook.com/v19.0/me/messages'
_MAX_MSG_LEN   = 2000   # Messenger single-message character limit


# ── Private helpers ──────────────────────────────────────────────────────────

def _send_message(recipient_id: str, text: str) -> None:
    """Send a text reply to a Messenger user via the Graph API."""
    if len(text) > _MAX_MSG_LEN:
        text = text[:_MAX_MSG_LEN - 3] + '...'
    try:
        requests.post(
            _GRAPH_API_URL,
            params={'access_token': FB_PAGE_TOKEN},
            json={
                'recipient': {'id': recipient_id},
                'message':   {'text': text},
            },
            timeout=10,
        )
    except Exception as exc:
        if HAUI_DEBUG:
            print(f'[FACEBOOK] Send failed: {exc}')


# ── Routes ───────────────────────────────────────────────────────────────────

@fb_bp.route('/api/webhook/facebook', methods=['GET'])
def verify_webhook():
    """
    Facebook one-time webhook verification.
    Called automatically when you register the webhook URL in Meta App settings.
    """
    hub_mode      = request.args.get('hub.mode')
    hub_token     = request.args.get('hub.verify_token')
    hub_challenge = request.args.get('hub.challenge', '')

    if hub_mode == 'subscribe' and hub_token == FB_VERIFY_TOKEN:
        return hub_challenge, 200
    return 'Forbidden', 403


@fb_bp.route('/api/webhook/facebook', methods=['POST'])
def receive_message():
    """
    Receive Messenger events, process text messages, and reply.
    Ignores non-text events (images, stickers, reactions, etc.).
    """
    payload = request.get_json(silent=True) or {}

    for entry in payload.get('entry', []):
        for event in entry.get('messaging', []):
            sender_id: str = event.get('sender', {}).get('id', '')
            message        = event.get('message', {})
            text: str      = message.get('text', '').strip()

            # Skip non-text events
            if not text or not sender_id:
                continue

            if HAUI_DEBUG:
                print(f'[FACEBOOK] From {sender_id}: {text[:80]}')

            result = handle_query(text)
            answer = result.get('answer', 'Xin lỗi, em chưa xử lý được câu hỏi này.')
            _send_message(sender_id, answer)

    return jsonify({'status': 'ok'})
