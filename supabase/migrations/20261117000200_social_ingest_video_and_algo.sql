-- Social saves ingest (social_ingest/social_ingest_spec_2026-11-15.md), build step 2.
-- Additive only: three nullable inbox columns and one new table. No data changes.

-- ── inbox: video pass state ──────────────────────────────────────────────
-- video_route: where the video pass sent this row.
--   pending                 ingested, waiting for watch_videos.py (sync_captures skips these)
--   triaged_out             unfiled TikTok failed caption triage (sync_captures skips these)
--   unavailable             deleted / private / blocked; keeps whatever text the export had
--   caption_only            no video to process (e.g. photo post)
--   native_transcript       platform subtitles, no Gemini
--   caption_transcript_cover  caption + transcript + cover image tag (tag_images.py)
--   audio                   Gemini transcribed the audio
--   full_video              Gemini watched the video
-- video_notes: {caption, creator, duration, transcript, wpm, notes, cost_usd, ...}
alter table public.inbox
  add column if not exists video_route text,
  add column if not exists video_notes jsonb,
  add column if not exists video_processed_at timestamptz;

alter table public.inbox drop constraint if exists inbox_video_route_check;
alter table public.inbox add constraint inbox_video_route_check check (
  video_route is null or video_route in (
    'pending', 'triaged_out', 'unavailable', 'caption_only', 'native_transcript',
    'caption_transcript_cover', 'audio', 'full_video'));

create index if not exists inbox_video_route_idx
  on public.inbox (video_route) where video_route is not null;

-- ── algo_snapshot: what the feeds showed Toni (signal, not knowledge) ─────
-- Not synced into node. Spec key is (platform, kind, url, snapshot_date); many
-- rows have no url (owner-only "not interested", searches, ad categories), so
-- the key uses ident = url, else owner:<handle>, else text:<caption>.
create table if not exists public.algo_snapshot (
  id            bigint generated always as identity primary key,
  platform      text not null check (platform in ('instagram', 'tiktok')),
  snapshot_date date not null,
  kind          text not null,
  url           text,
  caption       text,
  owner         text,
  hashtags      text[] not null default '{}',
  raw           jsonb,
  ident         text generated always as
                  (coalesce(url, 'owner:' || owner, 'text:' || caption, '')) stored,
  created_at    timestamptz not null default now(),
  constraint algo_snapshot_unique unique (platform, kind, ident, snapshot_date)
);

create index if not exists algo_snapshot_lookup_idx
  on public.algo_snapshot (platform, kind, snapshot_date);

-- Service role only (scripts). No policies = no anon/auth access.
alter table public.algo_snapshot enable row level security;
