-- Turns a post's links into real graph edges, so they show up when you walk
-- the knowledge graph (not only as arrays on published_posts):
--   post -> take       rel 'started_from'     (published_posts.commentary_ids)
--   post -> project    rel 'discusses'        (published_posts.related_project_ids)
--   post -> capture    rel 'from_voice_note'  ([[voice:<inbox id>]] tokens in body_md)
-- Idempotent: it only manages edges with origin 'post_links', adding missing
-- ones and removing ones whose link was taken off the post. Called at the end
-- of scripts/sync_posts.py; safe to call by hand.
create or replace function public.sync_post_edges()
returns table (added int, removed int)
language plpgsql
security definer
set search_path = public
as $$
declare a int; r int;
begin
  create temp table _want on commit drop as
  select distinct pn.id as from_node, t.id as to_node, 'started_from'::text as rel
    from published_posts p
    join node pn on pn.source_table = 'published_posts' and pn.source_id = p.id::text
    cross join lateral unnest(coalesce(p.commentary_ids, '{}')) c(cid)
    join node t on t.source_table = 'commentary' and t.source_id = c.cid::text
  union
  select pn.id, t.id, 'discusses'
    from published_posts p
    join node pn on pn.source_table = 'published_posts' and pn.source_id = p.id::text
    cross join lateral unnest(coalesce(p.related_project_ids, '{}')) r(sid)
    join node t on t.source_id = r.sid::text and t.kind in ('project', 'venture', 'repo')
  union
  select pn.id, t.id, 'from_voice_note'
    from published_posts p
    join node pn on pn.source_table = 'published_posts' and pn.source_id = p.id::text
    cross join lateral regexp_matches(coalesce(p.body_md, ''), '\[\[voice:([0-9a-f-]{36})\]\]', 'g') m
    join node t on t.source_table = 'inbox' and t.source_id = m[1];

  delete from edge e
   where e.origin = 'post_links'
     and not exists (select 1 from _want w where w.from_node = e.from_node and w.to_node = e.to_node and w.rel = e.rel);
  get diagnostics r = row_count;

  insert into edge (from_node, to_node, rel, weight, origin)
  select from_node, to_node, rel, 1, 'post_links' from _want
  on conflict (from_node, to_node, rel) do nothing;
  get diagnostics a = row_count;

  return query select a, r;
end;
$$;

revoke all on function public.sync_post_edges() from public, anon, authenticated;
grant execute on function public.sync_post_edges() to service_role;
