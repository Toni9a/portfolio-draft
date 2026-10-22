-- Tonidex Visuals: nearest image captures to one node, by its stored embedding (no Gemini call).
-- Not wired into the page yet (Visuals ranks "more like this" in the browser); kept for when images
-- are re-embedded with their captions (embed_nodes.py --reembed-images). Service role only.
create or replace function public.tonidex_similar(p_id bigint, p_limit int default 60)
returns table (id bigint, score real)
language sql
stable
security definer
set search_path = public
as $$
  select n.id, (1 - (n.embedding <=> s.embedding))::real as score
  from node n, (select embedding from node where id = p_id) s
  where n.id <> p_id
    and n.embedding is not null
    and n.image_tagged_model is not null and n.image_tagged_model <> 'unfetchable'
  order by n.embedding <=> s.embedding
  limit least(greatest(coalesce(p_limit, 60), 1), 200);
$$;
revoke all on function public.tonidex_similar(bigint, int) from public, anon, authenticated;
grant execute on function public.tonidex_similar(bigint, int) to service_role;
