"""The pipeline:  note -> (transcribe) -> score -> news angle -> draft in Meera's voice -> save -> human review.

Nothing is ever posted to LinkedIn. Meera reviews, edits and publishes herself (the Cut: Judgment Protected).
"""
import re
import traceback

from . import config, llm, news, store, telegram

BOT_MARKERS = ("📝", "⏸", "✅", "❌", "⚠️", "👋", "🎙", "⏳")
_seen_updates = set()  # guards against Telegram re-delivering an update to a warm instance

# ─────────────────────────────── prompts ───────────────────────────────

SCORING_SYSTEM = """You are the editor who triages raw notes for Meera Pillai, founder of Skinstinct (a minimal-ingredient
Indian D2C skincare brand; ex-pharma formulation scientist). Her LinkedIn audience is 28-40 year old urban Indian women
and people in the skincare industry. Her published posts are evidence-led: formulation science, pH, actives, stability,
label claims, industry transparency, India-specific climate/market context, and honest founder lessons.

Score how publishable the note is as the seed of ONE strong LinkedIn post in her voice, 0-10. Be strict: most raw
notes should NOT pass.

9-10  A specific, non-obvious insight or story with concrete detail (a number, a test result, a scene, a customer
      question) that fits her themes. A post almost writes itself.
7-8   A clear point with some specifics; needs shaping but has substance.
6     Borderline but workable: a real idea, thin on detail.
3-5   A topic, not an idea ("should write about retinol"), vague musing, or a generic point anyone could make.
0-2   Logistics, reminders, to-dos, personal errands, half-sentences, pure promotion/discounts, or anything that would
      be confidential or risky to publish (naming and accusing a specific supplier/person, internal financials).

Return JSON only: {"score": <int 0-10>, "reason": "<one sentence, specific to this note>", "theme": "<2-4 words>"}"""

KEYWORDS_PROMPT = """From this note, extract 3-5 search keywords and ONE short Google News search phrase (2-4 words) that
would find a CURRENT news item, regulation update, study or industry data point relevant to the note's core point.
Prefer skincare/cosmetics-industry or India-market angles over generic ones.

Note:
{note}

Return JSON only: {{"keywords": ["..."], "search_phrase": "..."}}"""

DRAFT_RULES = """
────────────────────────
TASK RULES (follow exactly)
- Write ONE LinkedIn post in Meera's voice, as described above, developing the note's core point.
- Stay faithful to the note. Use its specifics. Do NOT invent statistics, study results, dates, customer quotes or
  Skinstinct data that are not in the note or the news item. If a point needs a number you don't have, make the point
  without one.
- News: you are given up to 5 recent news items. Use ONE only if it is genuinely relevant and makes the post timely;
  weave it in naturally (e.g. "This week ... reported ..."), and only state what the headline supports. If none fits
  naturally, use none. A forced news hook is worse than no hook.
- Plain text only: no markdown, no bold, no emojis, no hashtags, no bullet lists.
- Return JSON only: {"post": "<the post, paragraphs separated by blank lines>", "news_index": <index of the item used, or null>}
"""


def draft_system():
    return config.voice_skill() + DRAFT_RULES


# ─────────────────────────────── steps ───────────────────────────────

def transcribe(audio_bytes, mime):
    return llm.gemini(
        "Transcribe this voice note verbatim. Return only the transcript text, no commentary.",
        audio=(audio_bytes, mime),
        temperature=0,
    )


def score_note(note):
    result = llm.gemini(f"Note:\n{note}", system=SCORING_SYSTEM, as_json=True, temperature=0)
    return int(result.get("score", 0)), result.get("reason", ""), result.get("theme", "")


def find_news(note):
    kw = llm.gemini(KEYWORDS_PROMPT.format(note=note), as_json=True, temperature=0)
    phrase = kw.get("search_phrase") or " ".join(kw.get("keywords", [])[:3])
    items = news.search(phrase)
    if not items and kw.get("keywords"):  # broaden once if the phrase was too narrow
        items = news.search(" ".join(kw["keywords"][:2]), recent="when:1y")
    return phrase, items


def write_draft(note, items):
    model, fn = llm.draft_model()
    news_block = "\n".join(
        f"[{i}] {it['headline']} — {it['source']}, {it['date']}" for i, it in enumerate(items)
    ) or "(no news items found)"
    prompt = f"NOTE FROM MEERA:\n{note}\n\nRECENT NEWS ITEMS:\n{news_block}"
    out = fn(prompt, draft_system())
    post = (out.get("post") or "").strip()
    idx = out.get("news_index")
    used = items[idx] if isinstance(idx, int) and 0 <= idx < len(items) else None
    return model, post, used


def verify_flag(item):
    line = "─" * 33
    return (
        f"\n\n{line}\n"
        f"NEWS SOURCE: {item['headline']}\n"
        f"FROM: {item['source']} · {item['date']}\n"
        f"LINK: {item['url']}\n"
        f"⚠ Check this before publishing — you are the author of this claim\n"
        f"{line}"
    )


# ─────────────────────────────── handlers ───────────────────────────────

def handle_update(update):
    uid = update.get("update_id")
    if uid in _seen_updates:
        return
    _seen_updates.add(uid)

    msg = update.get("channel_post") or update.get("message")
    if not msg:
        return  # edits, reactions, etc.
    chat_id = msg["chat"]["id"]
    if config.TELEGRAM_CHAT_ID and str(chat_id) != config.TELEGRAM_CHAT_ID:
        return  # only listen to Meera's capture channel
    if msg.get("from", {}).get("is_bot"):
        return

    try:
        _route(chat_id, msg)
    except Exception as e:
        traceback.print_exc()
        telegram.send(chat_id, f"⚠️ Something went wrong processing that note: {str(e)[:300]}", reply_to=msg["message_id"])


def _route(chat_id, msg):
    text = (msg.get("text") or msg.get("caption") or "").strip()
    mid = msg["message_id"]

    if text.startswith(BOT_MARKERS):
        return  # never process the bot's own output
    if text.lower().startswith("/start") or text.lower().startswith("/help"):
        telegram.send(chat_id, HELP)
        return

    # Only a bare "APPROVE", "REJECT", or "APPROVE 12" counts, so a note that starts with "Reject..." is still a note.
    decision = re.match(r"^(approve|reject)\s*#?(\d+)?\s*[.!]?$", text, re.I)
    if decision:
        handle_decision(chat_id, msg, decision.group(1).lower(), decision.group(2))
        return

    source = "text"
    voice = msg.get("voice") or msg.get("audio")
    if voice:
        telegram.typing(chat_id)
        audio = telegram.download_file(voice["file_id"])
        text = transcribe(audio, voice.get("mime_type", "audio/ogg"))
        source = "voice"
        telegram.send(chat_id, f"🎙 Heard: {text}", reply_to=mid)

    if not text or text.startswith("/"):
        return
    process_note(chat_id, mid, text, source)


def process_note(chat_id, mid, note, source="text"):
    try:
        note_id = store.save_note(chat_id, mid, note, source)
    except store.DuplicateNote:
        return
    telegram.typing(chat_id)

    # 1. Processing: score before drafting
    score, reason, theme = score_note(note)
    store.update_note(note_id, score=score, score_reason=reason, theme=theme)
    if score < config.SCORE_THRESHOLD:
        store.update_note(note_id, status="rejected")
        telegram.send(
            chat_id,
            f"⏸ Not drafted · score {score}/10\nReason: {reason}\n\n"
            f"Kept in your notes. Add more detail and send it again if you want a draft.",
            reply_to=mid,
        )
        return
    store.update_note(note_id, status="drafted")
    telegram.typing(chat_id)

    # 2. Context: news angle
    phrase, items = find_news(note)

    # 3. AI: draft in Meera's voice
    telegram.typing(chat_id)
    model, post, used = write_draft(note, items)
    body = post + (verify_flag(used) if used else "")

    draft_id = store.save_draft(
        note_id,
        draft_text=body,
        model=model,
        score=score,
        news_query=phrase,
        news_headline=used and used["headline"],
        news_source=used and used["source"],
        news_date=used and used["date"],
        news_url=used and used["url"],
    )

    # 4. Output: to Meera for review (the human gate)
    label = f"#{draft_id}" if draft_id else ""
    header = f"📝 DRAFT {label} · score {score}/10 · {theme}\nWhy: {reason}\n\n"
    footer = (
        "\n\n— Reply to this message with APPROVE or REJECT."
        if store.enabled()
        else "\n\n— (Memory not connected: approvals won't be saved.)"
    )
    msg_id = telegram.send(chat_id, header + body + footer, reply_to=mid)
    store.set_draft_message(draft_id, chat_id, msg_id)


def handle_decision(chat_id, msg, action, draft_num):
    if not store.enabled():
        telegram.send(chat_id, "⚠️ Memory (Supabase) isn't connected yet, so decisions can't be saved.")
        return
    replied = msg.get("reply_to_message")
    draft = None
    if draft_num:
        draft = store.find_draft(chat_id, draft_id=draft_num)
    elif replied:
        draft = store.find_draft(chat_id, telegram_message_id=replied["message_id"])
    if not draft:
        draft = store.latest_pending(chat_id)
    if not draft:
        telegram.send(chat_id, "⚠️ I couldn't find a pending draft. Reply directly to a draft message with APPROVE or REJECT.")
        return

    status = "approved" if action == "approve" else "rejected"
    store.decide(draft["id"], status)
    if status == "approved":
        telegram.send(
            chat_id,
            f"✅ Draft #{draft['id']} marked APPROVED.\nCopy it, make any edits, and publish it on LinkedIn yourself. "
            f"Nothing is posted automatically: you stay the author.",
            reply_to=msg["message_id"],
        )
    else:
        telegram.send(
            chat_id,
            f"❌ Draft #{draft['id']} marked REJECTED. It's kept (not deleted) so we can see what needs improving.",
            reply_to=msg["message_id"],
        )


HELP = """👋 I'm Meera's content assistant.

Drop a note here (text or a voice note). I will:
1. Score it 0-10 for how publishable it is (below 6 = no draft, and I'll tell you why)
2. Look for a current news angle
3. Draft a LinkedIn post in your voice
4. Send it back here for you to review

Reply to a draft with APPROVE or REJECT. I never post anything to LinkedIn. You publish."""
