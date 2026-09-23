# Blog rebuild: editorial layout, autosaving drafts, Gemini studio (2026-09-23)

Working-copy changes in `~/personal port/`, **not committed or pushed**. Supabase changes are live.
Tested locally on `localhost:8010`. `python -m http.server` has no clean URLs, so use `/admin.html` and `/blog.html` (add `?x=1` if Chrome has cached an old `/admin.html` → `/admin` redirect).

## What changed

**Public blog (`blog.html`)**: rebuilt to the Codex handoff (`SITE-HANDOFF.md`): dark editorial collage layout, serif titles, opening paper note, numbered sections, pull quote, margin cutouts, "Sources & sparks", and the particle hydrangea footer (`assets/blog/flower.js` + `hydrangea.mp4`, fixed footer settings). There are two views, the index and an article. Articles live at `/blog/<slug>` through a new rewrite in `vercel.json`; `#slug` and `?p=slug` also work locally. Asset paths are absolute.

**Shared renderer (`assets/blog/editorial.js`)**: used by both `blog.html` and the admin preview, so the preview is the published page. The post is still plain markdown in `body_md`, with these conventions:

| Markdown | Renders as |
|---|---|
| `> text` (first, before any heading) | the paper "quick take" note |
| `## [LABEL] Heading` | numbered section `01 / LABEL` |
| `>> text` | pull quote |
| `[[cutout:<post_media id>]]` | cutout in the margin beside the next passage |
| `[[image:<id>]]` / `[[voice:<inbox id>]]` | inline photo / voice player |
| `*words*` in the title | italic blue |

**Admin Blog tab (`admin.html`)**:
- No more empty rows. A draft is written only once it passes `sync_posts.py`'s rule: a non-placeholder title, or 20 or more characters of body. After that it autosaves about 1.1s after typing stops. Published posts don't autosave; they get an "Update live post" button.
- A full-screen editor with the live preview (`blog.html?preview=1` in an iframe, fed by `postMessage`) and a desktop/mobile toggle.
- **Write**: title, deck, body, formatting helpers, insert from flagged captures (which also links the take and adds the source), and house-rule chips (em dashes with a one-click fix).
- **Shape**: `transcript_md` holds the original voice note. The Gemini shape pass keeps Toni's words verbatim and returns a proposal to apply or undo. A sentence-by-sentence comparison lists dropped sentences and words that aren't in the transcript.
- **Images**: Gemini suggests 0–3 cutout ideas, then generates each with the handoff prompt plus the three prototype cutouts as style references (`assets/blog/style-refs/`). The image comes back on a chroma-green ground and `assets/blog/chroma-key.js` removes it into a real transparent PNG. It's then uploaded with alt text, placement and the passage that inspired it, and the token is placed beside the chosen section.
- **Links & graph**: node state (synced, embedded, tagged, or edited since tagging), plus doors, domains, concepts and tags. Linked takes (`commentary_ids`), projects (`related_project_ids`), and sources with display titles (`source_labels`). Gemini suggestions include graph neighbours.
- **Publish check**: blocks on no title, em dashes, and missing or alt-less images; warns on transcript drift, no deck or no sections.

## Supabase (live)

| Change | Detail |
|---|---|
| Migration `blog_editorial_fields` | `published_posts.transcript_md`, `published_posts.source_labels`; `post_media.kind/alt/placement/inspired_by/prompt` |
| Migration `hide_transcript_from_anon` | anon now has column-level SELECT on `published_posts` that excludes `transcript_md`. **Any new public column needs adding to that grant.** |
| Migration `match_nodes_by_kind` | exact-scan nearest neighbours by kind. `match_nodes()` goes through HNSW (ef_search 40), so it only ever returns ~40 nodes, nearly all captures. Semantic search elsewhere is subject to the same cap. |
| `blog-studio` (new) | `shape`, `cutout_ideas`, `generate_cutout` (tries `gemini-3.1-flash-image`, then `gemini-2.5-flash-image`, then `gemini-3-pro-image`), `models` |
| `public-post-media` (new, public) | presigns a published post's images, only for ids whose token is in its body |
| `blog-link-check` v6 | adds `related_projects` / `related_takes` from the graph |
| `admin-post-media` v3 | cutout metadata, `update` action |

**Security fix**: `blog-studio`, `blog-link-check` and `admin-post-media` now check for a signed-in user. `verify_jwt` alone accepts the public anon key, so before this anyone could run Gemini jobs or upload and delete blog media. `retag-item`, `semantic-search`, `answer-question`, `presign-media` and `backfill-voice-audio` still have that gap. Not yet fixed.

## Pipeline

`scripts/sync_posts.py` now strips the layout markup (tokens, `[LABEL]`, `>>`, `*`) before syncing, so the next run will retag the GEO post once.

## Test case

Draft `da88cf93…` was shaped in place and given one generated cutout during the local test (title "When Generative Engines Need *Human Influencers*"). Its original text is kept in `transcript_md`.

## Follow-up the same evening
- **The published GEO post (`3bdcd7d1…`) now carries the Codex article**: its title, deck, sections, pull quote, source titles and the three Codex cutouts (uploaded to R2 via `post_media`). The old body is kept in `transcript_md`. **Until the new `blog.html` is pushed, the old live blog shows the new markup raw** (`[The source]`, `[[cutout:…]]`).
- **Voice notes**: a "+ Voice note…" picker in Write lists every archived recording (`inbox.voice_audio_path`) and places a `[[voice:id]]` player styled for the editorial page. `public-voice-presign` v3 no longer requires `raw_message_type = 'voice'`, so voice replies to "add your take?" play too. Its source is still only in Supabase, not the repo.
- The full-resolution Codex cutouts were copied to `_to_delete/codex-cutouts/` for the upload and can be deleted.

## Still to do
- Commit and push (repo changes listed above), soon, because of the GEO note above.
- Close the same anon-key gap in the other five functions.
