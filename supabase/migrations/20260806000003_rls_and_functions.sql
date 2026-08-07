-- Migration 003: Row Level Security
-- You're the only user, so RLS is simple: everything is private by default,
-- open for authenticated users (you, via magic link).

alter table inbox               enable row level security;
alter table digest_items        enable row level security;
alter table commentary          enable row level security;
alter table published_posts     enable row level security;
alter table github_sync_cache   enable row level security;
alter table project_qna_sessions enable row level security;
alter table project_media       enable row level security;

-- Private tables: only accessible when authenticated (you)
create policy "auth only" on inbox                  for all using (auth.role() = 'authenticated');
create policy "auth only" on digest_items           for all using (auth.role() = 'authenticated');
create policy "auth only" on commentary             for all using (auth.role() = 'authenticated');
create policy "auth only" on github_sync_cache      for all using (auth.role() = 'authenticated');
create policy "auth only" on project_qna_sessions   for all using (auth.role() = 'authenticated');
create policy "auth only" on project_media          for all using (auth.role() = 'authenticated');

-- Published posts: authenticated users can do everything,
-- anonymous (site visitors) can only read published posts
create policy "auth full access" on published_posts
  for all using (auth.role() = 'authenticated');

create policy "public read published" on published_posts
  for select using (published_at is not null and published_at <= now());


-- ─────────────────────────────────────────────────────────────────────────────
-- SIMILARITY SEARCH FUNCTION
-- Used by the backfeed brain: given a new commentary embedding,
-- find the most semantically similar past opinions
-- ─────────────────────────────────────────────────────────────────────────────
create or replace function match_commentary (
  query_embedding vector(768),
  match_threshold float default 0.7,
  match_count     int   default 5
)
returns table (
  id          uuid,
  body        text,
  topic_tags  text[],
  created_at  timestamptz,
  similarity  float
)
language sql stable
as $$
  select
    c.id,
    c.body,
    c.topic_tags,
    c.created_at,
    1 - (c.embedding <=> query_embedding) as similarity
  from commentary c
  where c.embedding is not null
    and 1 - (c.embedding <=> query_embedding) > match_threshold
  order by c.embedding <=> query_embedding
  limit match_count;
$$;
