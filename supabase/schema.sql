-- Memory layer for the Meera content bot.
-- Supabase dashboard -> SQL Editor -> New query -> paste this whole file -> Run.

create table if not exists notes (
  id                  bigint generated always as identity primary key,
  created_at          timestamptz not null default now(),
  chat_id             bigint not null,
  telegram_message_id bigint not null,
  source              text not null default 'text',        -- text | voice
  text                text not null,
  score               int,
  score_reason        text,
  theme               text,
  status              text not null default 'received',    -- received | rejected | drafted
  unique (chat_id, telegram_message_id)                     -- stops duplicate processing if Telegram retries
);

create table if not exists drafts (
  id                  bigint generated always as identity primary key,
  created_at          timestamptz not null default now(),
  note_id             bigint references notes(id),
  chat_id             bigint,
  telegram_message_id bigint,                               -- the draft message, so a reply can find it
  model               text,
  score               int,
  draft_text          text not null,
  news_query          text,
  news_headline       text,
  news_source         text,
  news_date           text,
  news_url            text,
  status              text not null default 'pending',     -- pending | approved | rejected (never deleted)
  decided_at          timestamptz
);

create table if not exists voice_skill (
  id         bigint generated always as identity primary key,
  created_at timestamptz not null default now(),
  content    text not null
);

-- The bot uses the service_role key (server-side only), which bypasses RLS.
-- Enabling RLS with no policies keeps these tables private from the public anon key.
alter table notes       enable row level security;
alter table drafts      enable row level security;
alter table voice_skill enable row level security;
