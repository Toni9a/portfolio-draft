-- Applied via Supabase MCP as `blog_subscribers_and_comments` (2026-09-23).
-- Blog mailing list + reader comments. The public site only ever INSERTS into
-- these with the anon key; nobody outside the admin can read an email back.

create table if not exists public.blog_subscribers (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  source text,                         -- slug of the page they signed up on, or 'index'
  created_at timestamptz not null default now(),
  confirmed_at timestamptz,            -- for a future double opt-in (Resend etc.)
  unsubscribed_at timestamptz,
  constraint blog_subscribers_email_format check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$' and length(email) <= 254),
  constraint blog_subscribers_source_len check (source is null or length(source) <= 120)
);
create unique index if not exists blog_subscribers_email_key on public.blog_subscribers (lower(email));

create table if not exists public.blog_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.published_posts(id) on delete cascade,
  name text,
  email text not null,
  body text not null,
  status text not null default 'pending',   -- pending | approved | hidden
  created_at timestamptz not null default now(),
  constraint blog_comments_status check (status in ('pending','approved','hidden')),
  constraint blog_comments_email_format check (email ~* '^[^@\s]+@[^@\s]+\.[^@\s]+$' and length(email) <= 254),
  constraint blog_comments_name_len check (name is null or length(name) <= 80),
  constraint blog_comments_body_len check (length(btrim(body)) between 2 and 4000)
);
create index if not exists blog_comments_post_idx on public.blog_comments (post_id, status, created_at);

alter table public.blog_subscribers enable row level security;
alter table public.blog_comments enable row level security;

create policy "anon can subscribe" on public.blog_subscribers
  for insert to anon
  with check (confirmed_at is null and unsubscribed_at is null);

create policy "anon can comment on published posts" on public.blog_comments
  for insert to anon
  with check (
    status = 'pending'
    and exists (select 1 from public.published_posts p where p.id = post_id and p.published_at is not null and p.published_at <= now())
  );

create policy "anon reads approved comments" on public.blog_comments
  for select to anon
  using (status = 'approved');

create policy "auth full access" on public.blog_subscribers
  for all to authenticated using (true) with check (true);
create policy "auth full access" on public.blog_comments
  for all to authenticated using (true) with check (true);

revoke all on public.blog_subscribers from anon;
grant insert (email, source) on public.blog_subscribers to anon;

revoke all on public.blog_comments from anon;
grant insert (post_id, name, email, body) on public.blog_comments to anon;
grant select (id, post_id, name, body, created_at) on public.blog_comments to anon;

grant all on public.blog_subscribers, public.blog_comments to authenticated;
