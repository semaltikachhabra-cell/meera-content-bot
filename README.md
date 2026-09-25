# Meera's Content Bot (MESA Case 1 · Skinstinct)

Meera drops raw notes (text or voice) into her private Telegram channel. This bot picks each one up, **scores** it, finds a **current news angle**, **drafts a LinkedIn post in her voice**, **saves** everything, and sends the draft back for her to **approve or reject**.

It never posts to LinkedIn. **Meera reviews, edits and publishes herself.**

## The Cut: why nothing auto-publishes

Nine-checks result: **Check 07, Judgment Protected, fails** for "end-to-end auto-posting". Meera turned down two consultants who built exactly that. She wants to stay the author of everything published under her name. So the system automates **capture → scoring → news research → drafting** and stops at a **human review gate**. Any draft that uses a news item carries a verify flag so she checks the claim before it goes out under her name.

## Components map

| Trigger | Input | Processing | Context | AI | Output |
|---|---|---|---|---|---|
| Meera posts a note in her Telegram channel | Telegram webhook → Vercel (`api/webhook.py`); voice notes transcribed by Gemini | **Gemini Flash** scores 0–10 with a reason; below 6 → polite "not drafted" message, stop | Gemini extracts a search phrase → **Google News RSS** (free, no key) → top 5 recent items | Drafting model (Gemini, or **Claude** if `ANTHROPIC_API_KEY` is set) + `voice-skill.txt` on every call; uses a news item only if it is genuinely relevant | Draft + verify flag back in Telegram → **Meera replies APPROVE / REJECT** → status saved in **Supabase** |

## Project layout

```
api/webhook.py      Vercel function: Telegram POSTs here; GET = health check
bot/pipeline.py     The pipeline + all prompts (scoring, keywords, drafting, verify flag, APPROVE/REJECT)
bot/llm.py          Gemini + Claude API calls
bot/news.py         Google News RSS search
bot/store.py        Supabase memory (notes, drafts, voice_skill); skipped cleanly if not configured
bot/telegram.py     Send messages, download voice notes
bot/config.py       Environment variables; reads voice-skill.txt fresh on every call
voice-skill.txt     Meera's voice profile, built from her 15 published pieces
supabase/schema.sql The three tables
```

No third-party packages; only the Python standard library.

## Setup

1. **Deploy**: import this repo in Vercel and add Environment Variables (see `.env.example`):
   `TELEGRAM_BOT_TOKEN`, `GEMINI_API_KEY`, `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, plus the optional `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and `ANTHROPIC_API_KEY`.
2. **Check**: open `https://<app>.vercel.app/api/webhook?test=1` and every line should read OK or true.
3. **Connect Telegram**:
   `https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<app>.vercel.app/api/webhook&secret_token=<TELEGRAM_WEBHOOK_SECRET>`
   → should return `"ok":true`.
4. **Memory (optional)**: in Supabase, open SQL Editor, paste `supabase/schema.sql` and run it.

## Test notes

**Strong** (should score 6 or above and produce a draft):
> Customer DM today asked why our serum "doesn't do anything" for 3 weeks. Turns out she's layering it straight after a pH 3 glycolic toner. Niacinamide below pH 4 starts converting to niacin, which explains the flushing she mentioned too. Nobody tells customers about layering order and pH. We should.

> Manufacturing unit visit: the mid-batch CoA on the new serum run came back 0.4% under label on niacinamide. Within spec, but only because we sample mid-batch. If we only tested start and end like most brands, we'd never have seen it. This is why I pay extra for mid-batch sampling.

**Weak** (should score 3 or below, no draft):
> call courier re: Pune shipment before 4

> retinol??

## Security

`.env` is git-ignored; keys live only in Vercel Environment Variables. The webhook rejects requests without Telegram's secret token (when `TELEGRAM_WEBHOOK_SECRET` is set) and only listens to `TELEGRAM_CHAT_ID`.
