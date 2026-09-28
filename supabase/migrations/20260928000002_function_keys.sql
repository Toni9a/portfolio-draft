-- Hashed keys for callers that can't sign in (e.g. the iOS answer-question
-- Shortcut). Only edge functions (service role) read this; RLS on with no
-- policies means anon/authenticated see nothing. The row
-- ('answer-question-shortcut', sha256 of SHORTCUT_KEY in .env) was inserted
-- by hand, not here, so the hash isn't in the repo.
create table if not exists public.function_keys (
  name text primary key,
  key_sha256 text not null,
  created_at timestamptz not null default now()
);
alter table public.function_keys enable row level security;
revoke all on public.function_keys from anon, authenticated;
