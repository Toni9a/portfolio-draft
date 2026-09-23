-- Editorial blog rebuild (2026-09-23). Applied via Supabase MCP as `blog_editorial_fields`.
-- transcript_md: the original voice-note transcript, kept separately so the
--   shaped article can be compared against it sentence by sentence.
-- source_labels: optional human titles for source_urls, keyed by url.
alter table public.published_posts
  add column if not exists transcript_md text,
  add column if not exists source_labels jsonb not null default '{}'::jsonb;

-- post_media grows from "uploaded photo" into editorial cutouts.
alter table public.post_media
  add column if not exists kind text not null default 'image',       -- 'image' | 'cutout'
  add column if not exists alt text,
  add column if not exists placement text,                           -- 'lead' | 'left' | 'right'
  add column if not exists inspired_by text,                         -- the passage that inspired it
  add column if not exists prompt text;                              -- the exact image prompt used

alter table public.post_media drop constraint if exists post_media_kind_check;
alter table public.post_media add constraint post_media_kind_check check (kind in ('image','cutout'));
alter table public.post_media drop constraint if exists post_media_placement_check;
alter table public.post_media add constraint post_media_placement_check check (placement is null or placement in ('lead','left','right'));

-- Applied separately as `hide_transcript_from_anon`.
-- The raw voice-note transcript is working material, not published copy.
-- published_posts has a public-read RLS policy for published rows, so switch
-- anon to column-level SELECT that simply leaves transcript_md out.
revoke select on public.published_posts from anon;
grant select (id, slug, title, body_md, excerpt, cover_image_url, source_urls, source_labels,
              commentary_ids, related_project_ids, related_skill_cluster_ids, topic_tags,
              published_at, created_at, updated_at, captured_on)
  on public.published_posts to anon;
