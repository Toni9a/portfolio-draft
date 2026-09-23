-- Applied via Supabase MCP as `match_nodes_by_kind` (2026-09-23).
-- Nearest nodes of given kinds (e.g. projects/repos, or commentary) for the
-- blog editor's "related" suggestions. match_nodes() goes through the HNSW
-- index, whose default ef_search (40) means a post's nearest 40 neighbours,
-- almost all captures, and nothing else. The graph is small (~1.1k rows), so
-- this does an exact scan instead: "+ 0" keeps the planner off the index.
create or replace function public.match_nodes_by_kind(
  query_embedding vector,
  kinds text[],
  match_count integer default 6,
  exclude_node bigint default null
)
returns table(id bigint, kind text, title text, source_id text, similarity double precision)
language sql stable
set search_path to 'public', 'pg_temp'
as $$
  select n.id, n.kind, n.title, n.source_id, 1 - (n.embedding <=> query_embedding)
  from node n
  where n.embedding is not null
    and n.kind = any(kinds)
    and (exclude_node is null or n.id <> exclude_node)
  order by (n.embedding <=> query_embedding) + 0
  limit match_count;
$$;

revoke all on function public.match_nodes_by_kind(vector, text[], integer, bigint) from public, anon;
grant execute on function public.match_nodes_by_kind(vector, text[], integer, bigint) to authenticated, service_role;
