"""Memory layer: Supabase (via its REST API). Every function is a no-op if Supabase isn't configured."""
from datetime import datetime, timezone

from . import config
from .http import HttpError, request


def enabled():
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY)


def _req(method, table, body=None, query="", prefer="return=representation"):
    return request(
        method,
        f"{config.SUPABASE_URL}/rest/v1/{table}{query}",
        headers={
            "apikey": config.SUPABASE_KEY,
            "Authorization": f"Bearer {config.SUPABASE_KEY}",
            "Prefer": prefer,
        },
        body=body,
        retries=0,
    )


def save_note(chat_id, message_id, text, source):
    """Insert the note. Returns its id, or None if this Telegram message was already processed (duplicate delivery)."""
    if not enabled():
        return None
    try:
        rows = _req("POST", "notes", {"chat_id": chat_id, "telegram_message_id": message_id, "text": text, "source": source})
        return rows[0]["id"]
    except HttpError as e:
        if "23505" in str(e):  # unique violation: Telegram retried the same update
            raise DuplicateNote()
        raise


def update_note(note_id, **fields):
    if enabled() and note_id:
        _req("PATCH", "notes", fields, query=f"?id=eq.{note_id}", prefer="return=minimal")


def save_draft(note_id, **fields):
    if not enabled():
        return None
    rows = _req("POST", "drafts", {"note_id": note_id, "status": "pending", **fields})
    return rows[0]["id"]


def set_draft_message(draft_id, chat_id, message_id):
    if enabled() and draft_id:
        _req("PATCH", "drafts", {"chat_id": chat_id, "telegram_message_id": message_id},
             query=f"?id=eq.{draft_id}", prefer="return=minimal")


def find_draft(chat_id, telegram_message_id=None, draft_id=None):
    if not enabled():
        return None
    if draft_id:
        q = f"?id=eq.{int(draft_id)}&select=*"
    else:
        q = f"?chat_id=eq.{chat_id}&telegram_message_id=eq.{telegram_message_id}&select=*"
    rows = _req("GET", "drafts", query=q)
    return rows[0] if rows else None


def latest_pending(chat_id):
    if not enabled():
        return None
    rows = _req("GET", "drafts", query=f"?chat_id=eq.{chat_id}&status=eq.pending&order=created_at.desc&limit=1&select=*")
    return rows[0] if rows else None


def decide(draft_id, status):
    now = datetime.now(timezone.utc).isoformat()
    _req("PATCH", "drafts", {"status": status, "decided_at": now}, query=f"?id=eq.{draft_id}", prefer="return=minimal")


def sync_voice_skill(content):
    """Keep the voice_skill table in step with voice-skill.txt (inserts a new version only when the text changes)."""
    if not enabled():
        return
    rows = _req("GET", "voice_skill", query="?order=created_at.desc&limit=1&select=content")
    if not rows or rows[0]["content"] != content:
        _req("POST", "voice_skill", {"content": content}, prefer="return=minimal")


class DuplicateNote(Exception):
    pass
