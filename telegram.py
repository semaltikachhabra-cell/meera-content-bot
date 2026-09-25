"""Telegram Bot API: send messages back, and download voice notes."""
from . import config
from .http import get_bytes, request

API = "https://api.telegram.org/bot{token}/{method}"
FILE = "https://api.telegram.org/file/bot{token}/{path}"
MAX_LEN = 4000  # Telegram's hard limit is 4096 characters per message


def call(method, **params):
    resp = request("POST", API.format(token=config.TELEGRAM_BOT_TOKEN, method=method), body=params)
    return resp.get("result") if resp else None


def send(chat_id, text, reply_to=None):
    """Send plain text (no Markdown, so special characters never break a message). Returns the last message id."""
    last_id = None
    chunks = [text[i : i + MAX_LEN] for i in range(0, len(text), MAX_LEN)] or [""]
    for chunk in chunks:
        params = {"chat_id": chat_id, "text": chunk, "disable_web_page_preview": True}
        if reply_to:
            params["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
        msg = call("sendMessage", **params)
        last_id = msg["message_id"] if msg else last_id
    return last_id


def typing(chat_id):
    try:
        call("sendChatAction", chat_id=chat_id, action="typing")
    except Exception:
        pass  # cosmetic only


def download_file(file_id):
    info = call("getFile", file_id=file_id)
    return get_bytes(FILE.format(token=config.TELEGRAM_BOT_TOKEN, path=info["file_path"]))
