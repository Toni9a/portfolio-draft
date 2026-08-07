-- Migration 002: Core schema
-- Unified inbox, digest pipeline, blog publishing, project enrichment

-- ─────────────────────────────────────────────────────────────────────────────
-- INBOX
-- Single table for all inbound content: X bookmarks, YouTube, TikTok, anything
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists inbox (
  id                  uuid primary key default gen_random_uuid(),

  -- Source info
  url                 text not null,
  source              text not null,              -- 'twitter' | 'youtube' | 'tiktok' | 'manual'
  folder              text,                       -- e.g. 'cool news', 'Hard projects'
  source_item_id      text,                       -- tweet_id, video_id, etc.
  title               text,                       -- tweet text, video title, etc.
  full_text           text,                       -- full content where available
  author_name         text,
  author_handle       text,
  media_urls          text[]    default '{}',     -- attached images/videos

  -- Pipeline state
  status              text      not null default 'new',
  -- 'new'       → just captured, unprocessed
  -- 'in_digest' → included in a digest batch
  -- 'archived'  → skipped / not relevant
  -- 'published' → made it into a blog post

  -- Your annotations
  my_note             text,                       -- quick note you add on capture or review
  topic_tags          text[]    default '{}',     -- e.g. ['ai', 'computer_vision', 'spatial']
  related_item_ids    uuid[]    default '{}',     -- cross-links to other inbox items

  -- Timestamps
  source_created_at   timestamptz,                -- when the original was posted
  captured_at         timestamptz not null default now(),
  created_at          timestamptz not null default now(),

  -- Raw original payload for reference / reprocessing
  raw_data            jsonb,

  constraint inbox_url_unique unique (url)
);

create index if not exists inbox_source_idx     on inbox (source);
create index if not exists inbox_folder_idx     on inbox (folder);
create index if not exists inbox_status_idx     on inbox (status);
create index if not exists inbox_captured_idx   on inbox (captured_at desc);
create index if not exists inbox_tags_idx       on inbox using gin (topic_tags);


-- ─────────────────────────────────────────────────────────────────────────────
-- DIGEST ITEMS
-- Clustered, capped weekly batches of inbox items for you to review
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists digest_items (
  id            uuid primary key default gen_random_uuid(),
  inbox_ids     uuid[]    not null,               -- which inbox items this cluster covers
  summary       text,                             -- LLM one-liner summary
  topic_tags    text[]    default '{}',
  surfaced_at   timestamptz not null default now(),
  status        text      not null default 'pending',
  -- 'pending'   → waiting for you to write commentary
  -- 'commented' → you've written your take
  -- 'skipped'   → passed on this one
  created_at    timestamptz not null default now()
);

create index if not exists digest_status_idx    on digest_items (status);
create index if not exists digest_surfaced_idx  on digest_items (surfaced_at desc);


-- ─────────────────────────────────────────────────────────────────────────────
-- COMMENTARY
-- Your words on a topic. This is the brain's long-term memory.
-- Embeddings here power the backfeed / opinion-aware drafting.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists commentary (
  id              uuid primary key default gen_random_uuid(),
  digest_item_id  uuid references digest_items (id) on delete set null,
  body            text      not null,
  -- Gemini text-embedding-004 → 768 dims
  embedding       vector(768),
  topic_tags      text[]    default '{}',
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index if not exists commentary_digest_idx    on commentary (digest_item_id);
create index if not exists commentary_created_idx   on commentary (created_at desc);
-- Vector index for similarity search (backfeed)
create index if not exists commentary_embedding_idx
  on commentary using ivfflat (embedding vector_cosine_ops)
  with (lists = 50);


-- ─────────────────────────────────────────────────────────────────────────────
-- PUBLISHED POSTS
-- Final blog posts, ready to render on the site
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists published_posts (
  id                        uuid primary key default gen_random_uuid(),
  slug                      text      not null unique,
  title                     text      not null,
  body_md                   text      not null,
  excerpt                   text,
  cover_image_url           text,
  source_urls               text[]    default '{}',     -- credited source links
  commentary_ids            uuid[]    default '{}',     -- which commentary rows fed this
  related_project_ids       text[]    default '{}',     -- cross-link to portfolio projects
  related_skill_cluster_ids text[]    default '{}',     -- cross-link to skill clusters
  topic_tags                text[]    default '{}',
  published_at              timestamptz,                -- null = draft
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

create index if not exists posts_slug_idx       on published_posts (slug);
create index if not exists posts_published_idx  on published_posts (published_at desc);
create index if not exists posts_tags_idx       on published_posts using gin (topic_tags);


-- ─────────────────────────────────────────────────────────────────────────────
-- GITHUB SYNC CACHE
-- Raw pull from GitHub API for repos tagged for inclusion
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists github_sync_cache (
  id                uuid primary key default gen_random_uuid(),
  repo_full_name    text      not null unique,    -- e.g. 'tonzownz/trakrush'
  readme_md         text,
  description       text,
  topics            text[]    default '{}',
  homepage_url      text,
  stars             int       default 0,
  last_commit_at    timestamptz,
  synced_at         timestamptz not null default now(),
  raw_data          jsonb
);


-- ─────────────────────────────────────────────────────────────────────────────
-- PROJECT Q&A SESSIONS
-- Stores intake Q&A to populate project reasoning / long descriptions
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists project_qna_sessions (
  id            uuid primary key default gen_random_uuid(),
  project_id    text      not null,               -- matches projects[].id in portfolio JSON
  question      text      not null,
  answer        text,
  answered_at   timestamptz,
  created_at    timestamptz not null default now()
);

create index if not exists qna_project_idx on project_qna_sessions (project_id);


-- ─────────────────────────────────────────────────────────────────────────────
-- PROJECT MEDIA
-- Screenshots and video for project detail pages, stored in Supabase Storage
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists project_media (
  id                      uuid primary key default gen_random_uuid(),
  project_id              text      not null,
  storage_path            text      not null,     -- path in Supabase Storage bucket
  type                    text      not null,     -- 'image' | 'video'
  caption                 text,
  sort_order              int       default 0,
  content_repurpose_flags jsonb     default '{}', -- {tiktok: bool, linkedin: bool, notes: string}
  created_at              timestamptz not null default now()
);

create index if not exists media_project_idx on project_media (project_id);
create index if not exists media_sort_idx    on project_media (project_id, sort_order);
