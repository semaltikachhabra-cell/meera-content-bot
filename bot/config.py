"""All settings come from environment variables (.env locally, Vercel Environment Variables in production)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# Optional: if set, the bot only listens to this channel/chat (a negative number starting with -100).
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
# Optional: if set, Telegram must send this secret with every webhook call (pass it as secret_token to setWebhook).
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest").strip()

# Optional: if set, drafts are written by Claude (holds a voice better); otherwise Gemini writes them.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5").strip()

# Optional: memory layer. If not set, the bot still works but nothing is saved.
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

SCORE_THRESHOLD = int(os.environ.get("SCORE_THRESHOLD", "6"))


def voice_skill() -> str:
    """Read voice-skill.txt fresh on every call so the voice always reaches the drafting model."""
    return (ROOT / "voice-skill.txt").read_text(encoding="utf-8")
