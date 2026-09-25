"""AI layer: Gemini Flash for fast/cheap steps, Claude (optional) for drafting."""
import base64
import json
import re

from . import config
from .http import request

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def gemini(prompt, system=None, as_json=False, temperature=0.4, audio=None):
    """Call Gemini. `audio` is an optional (bytes, mime_type) tuple, used for voice notes."""
    parts = [{"text": prompt}]
    if audio:
        data, mime = audio
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature},
    }
    if system:
        body["system_instruction"] = {"parts": [{"text": system}]}
    if as_json:
        body["generationConfig"]["responseMimeType"] = "application/json"
    resp = request(
        "POST",
        GEMINI_URL.format(model=config.GEMINI_MODEL),
        headers={"x-goog-api-key": config.GEMINI_API_KEY},
        body=body,
    )
    try:
        text = "".join(p.get("text", "") for p in resp["candidates"][0]["content"]["parts"])
    except (KeyError, IndexError):
        raise RuntimeError(f"Gemini returned no text: {json.dumps(resp)[:300]}")
    return parse_json(text) if as_json else text.strip()


def claude(prompt, system=None, temperature=0.7):
    body = {
        "model": config.CLAUDE_MODEL,
        "max_tokens": 2000,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    resp = request(
        "POST",
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"},
        body=body,
    )
    return "".join(b.get("text", "") for b in resp["content"] if b.get("type") == "text").strip()


def draft_model():
    """Claude if a key is configured, otherwise Gemini."""
    if config.ANTHROPIC_API_KEY:
        return f"claude:{config.CLAUDE_MODEL}", lambda p, s: parse_json(claude(p, s))
    return f"gemini:{config.GEMINI_MODEL}", lambda p, s: gemini(p, s, as_json=True, temperature=0.7)


def parse_json(text):
    """Parse a JSON object even if the model wrapped it in ```json fences or extra words."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise RuntimeError(f"Model did not return JSON: {text[:200]}")
        return json.loads(m.group(0))
