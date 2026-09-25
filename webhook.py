"""Vercel serverless function. Telegram POSTs every new message here: https://<your-app>.vercel.app/api/webhook

GET the same URL in a browser to see a health check of your configuration.
"""
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import config, pipeline, store  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if config.TELEGRAM_WEBHOOK_SECRET and (
            self.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.TELEGRAM_WEBHOOK_SECRET
        ):
            return self._reply(401, {"ok": False, "error": "bad secret"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            update = json.loads(self.rfile.read(length) or b"{}")
            pipeline.handle_update(update)
        except Exception as e:  # always answer 200 so Telegram doesn't retry forever
            print("webhook error:", repr(e))
        self._reply(200, {"ok": True})

    def do_GET(self):
        status = {
            "ok": True,
            "service": "Meera content bot",
            "telegram_token_set": bool(config.TELEGRAM_BOT_TOKEN),
            "gemini_key_set": bool(config.GEMINI_API_KEY),
            "gemini_model": config.GEMINI_MODEL,
            "drafting_model": "claude:" + config.CLAUDE_MODEL if config.ANTHROPIC_API_KEY else "gemini:" + config.GEMINI_MODEL,
            "channel_filter": config.TELEGRAM_CHAT_ID or "(none: replies to any chat)",
            "memory_supabase": store.enabled(),
        }
        try:
            skill = config.voice_skill()
            status["voice_skill_loaded"] = f"{len(skill.split())} words"
        except Exception as e:
            status["ok"] = False
            status["voice_skill_loaded"] = f"ERROR: {e}"
        else:
            try:
                store.sync_voice_skill(skill)
            except Exception as e:
                status["memory_supabase"] = f"ERROR: {str(e)[:200]}"
        if "test" in self.path:  # /api/webhook?test=1 also checks that Gemini answers
            try:
                score, reason, _ = pipeline.score_note("remind me to call the courier at 4pm")
                status["gemini_test"] = f"OK: scored a to-do note {score}/10 ({reason})"
            except Exception as e:
                status["ok"] = False
                status["gemini_test"] = f"ERROR: {str(e)[:300]}"
        self._reply(200, status)

    def _reply(self, code, payload):
        body = json.dumps(payload, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
