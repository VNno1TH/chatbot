"""
analytics.py — Query logging and statistics for Admin Dashboard.
Single responsibility: write logs, read stats. No RAG logic here.

Log files (auto-created in data/):
- analytics_log.json  : one entry per query, pruned to MAX_DAYS
- feedback_log.json   : user thumbs-up / thumbs-down events
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from src.config import BASE_DIR

# ── Paths ──────────────────────────────────────────────────────────────────
_ANALYTICS_PATH = os.path.join(BASE_DIR, 'data', 'analytics_log.json')
_FEEDBACK_PATH  = os.path.join(BASE_DIR, 'data', 'feedback_log.json')

# Keep only the last N days of query logs to cap file size
_MAX_DAYS = 7


# ── Private helpers ─────────────────────────────────────────────────────────

def _load(path: str) -> list:
    """Load a JSON list from *path*. Returns [] on missing/corrupt file."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(path: str, data: list) -> None:
    """Persist *data* as a JSON list to *path*, creating parent dirs."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _prune(logs: list, max_days: int = _MAX_DAYS) -> list:
    """Drop entries older than *max_days* (relies on ISO-8601 'ts' field)."""
    cutoff = (datetime.now() - timedelta(days=max_days)).isoformat()
    return [entry for entry in logs if entry.get('ts', '') >= cutoff]


# ── Public API ───────────────────────────────────────────────────────────────

def log_query(
    intent: str,
    ma_nganh: str = '',
    ten_nganh: str = '',
    response_time: float = 0.0,
    num_chunks: int = 0,
) -> None:
    """Append one chat-query event to the analytics log."""
    entry = {
        'ts':       datetime.now().isoformat(timespec='seconds'),
        'intent':   intent,
        'ma_nganh': ma_nganh,
        'ten_nganh': ten_nganh,
        'time':     round(response_time, 2),
        'chunks':   num_chunks,
    }
    logs = _prune(_load(_ANALYTICS_PATH))
    logs.append(entry)
    _save(_ANALYTICS_PATH, logs)


def get_stats() -> dict:
    """Aggregate analytics logs into chart-ready data for the Admin Dashboard."""
    logs = _load(_ANALYTICS_PATH)

    intents: dict[str, int] = {}
    majors:  dict[str, int] = {}
    total_time = 0.0

    for log in logs:
        # Count by intent
        intent = log.get('intent', 'unknown')
        intents[intent] = intents.get(intent, 0) + 1

        # Count by major (ten_nganh)
        ten_nganh = log.get('ten_nganh', '').strip()
        if ten_nganh:
            majors[ten_nganh] = majors.get(ten_nganh, 0) + 1

        total_time += log.get('time', 0)

    top_majors = sorted(majors.items(), key=lambda x: -x[1])[:10]
    avg_time = round(total_time / len(logs), 2) if logs else 0.0

    return {
        'total':      len(logs),
        'avg_time':   avg_time,
        'intents':    intents,
        'top_majors': [{'name': k, 'count': v} for k, v in top_majors],
    }


def log_feedback(
    question: str,
    answer: str,
    feedback_type: str,
    comment: str = '',
) -> None:
    """Append one user-feedback event (thumbs-up / thumbs-down)."""
    entry = {
        'ts':       datetime.now().isoformat(timespec='seconds'),
        'type':     feedback_type,       # 'up' | 'down'
        'question': question[:300],
        'answer':   answer[:300],
        'comment':  comment[:500],
    }
    logs = _load(_FEEDBACK_PATH)
    logs.append(entry)
    _save(_FEEDBACK_PATH, logs)


def get_feedback(limit: int = 50) -> list:
    """Return the *limit* most-recent feedback entries (newest first)."""
    logs = _load(_FEEDBACK_PATH)
    return list(reversed(logs))[:limit]
