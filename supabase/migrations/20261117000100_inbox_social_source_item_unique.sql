-- Social saves ingest (social_ingest/social_ingest_spec_2026-11-15.md)
--
-- inbox_url_unique stops re-run duplicates only for rows that have a URL.
-- Instagram self-chat notes have no URL (NULLs never conflict), so every re-run
-- of scripts/ingest_social.py would insert them again. Each note carries a
-- stable source_item_id (ig_selfchat_<timestamp_ms>); make that unique.
--
-- Scoped to the social sources only: inbox already holds one twitter item saved
-- twice under two URL forms (source_item_id 1878371232560857557), and the spec
-- says never delete rows, so a table-wide index would fail to build.
--
-- Because the index is partial, ON CONFLICT can't target it from supabase-py.
-- ingest_social.py inserts URL-less rows only after checking which
-- source_item_ids already exist; this index is the backstop if that check races.
--
-- Applied 2026-11-17 via Supabase MCP (migration name inbox_social_source_item_unique).

create unique index if not exists inbox_social_source_item_unique
  on public.inbox (source, source_item_id)
  where source in ('instagram_save', 'instagram_selfchat', 'instagram_seemore', 'tiktok_save')
    and source_item_id is not null;
