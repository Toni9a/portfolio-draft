-- Tonidex: blog posts carry their whole text (for search); everything else stays trimmed.
create or replace function public.tonidex_map_data()
returns jsonb
language sql
stable
security definer
set search_path = public
as $$
with items as (
  select n.id, n.kind, n.title, case when n.kind = 'post' then coalesce(n.body,'') else left(coalesce(n.body,''), 420) end as body, n.url, n.image_caption as caption,
         coalesce(n.occurred_at, n.created_at) as at,
         c.folder, c.image_key, c.author_handle as handle,
         i.media_urls[1] as media_url,
         i.source as src,
         case
           when c.image_key is not null and n.image_tagged_model is not null and n.image_tagged_model <> 'unfetchable' then 'image'
           when n.kind in ('commentary','post') then 'idea'
           when i.source in ('telegram_voice','telegram_thought') then 'idea'
           when n.kind = 'project' then 'work'
           when n.source_table = 'inbox' then 'link'
           else null
         end as layer
  from node n
  left join bot_node_card c on c.node_id = n.id
  left join inbox i on n.source_table = 'inbox' and i.id::text = n.source_id
),
picked as (select * from items where layer is not null)
select jsonb_build_object(
  'doors', (select jsonb_agg(jsonb_build_object('id', id, 'label', label, 'family', family) order by sort) from door where id <> 'cross_door'),
  'concepts', (select jsonb_agg(jsonb_build_object('id', c.id, 'slug', c.slug, 'label', c.label, 'door', c.door_id, 'kind', c.kind))
               from concept c where exists (select 1 from node_concept nc join picked p on p.id = nc.node_id where nc.concept_id = c.id)),
  'items', (select jsonb_agg(jsonb_build_object(
      'id', p.id, 'layer', p.layer, 'kind', p.kind, 'src', p.src, 'title', p.title, 'body', p.body, 'url', p.url, 'caption', p.caption,
      'at', p.at, 'folder', p.folder, 'handle', p.handle, 'image_key', p.image_key, 'media_url', p.media_url,
      'doors', coalesce((select jsonb_agg(distinct nd.door_id) from node_door nd where nd.node_id = p.id and nd.door_id <> 'cross_door'), '[]'::jsonb),
      'concepts', coalesce((select jsonb_agg(distinct nc.concept_id) from node_concept nc where nc.node_id = p.id), '[]'::jsonb),
      'tags', coalesce((select jsonb_agg(t.label) from (select t.label from node_tag nt join tag t on t.id = nt.tag_id
                         where nt.node_id = p.id and t.slug not like 'folder-%' order by (nt.origin = 'gemini-image') desc, t.label limit 6) t), '[]'::jsonb)
    )) from picked p),
  'edges', coalesce((select jsonb_agg(jsonb_build_object('a', e.from_node, 'b', e.to_node, 'rel', e.rel))
            from edge e where e.from_node in (select id from picked) and e.to_node in (select id from picked)), '[]'::jsonb)
);
$$;

revoke all on function public.tonidex_map_data() from public, anon, authenticated;
grant execute on function public.tonidex_map_data() to service_role;
