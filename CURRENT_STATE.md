# Portfolio — Current State

**Last updated:** 2026-09-28 · **Branch:** `main` · Newest dated section first; each section says when it was verified.

Everything marked ✅ below was verified on this date directly against the Supabase project (`dmlwcrbjetpgqacblvqp`), the deployed edge-function list, the GitHub Actions tab and the working copy. Claims carried over from the previous version without re-checking are marked *(carried forward)*.

Companion doc: `system_atlas.md` (repo root) — the same system from the Layer 1 / pipeline side, with verification queries. This doc is the Layer 2 / site-and-repo view. Don't duplicate between them.


## 2026-09-28 (later): captures flow into the graph again ✅

- **Cause.** Capture nodes only ever came from a one-off SQL backfill on 2026-08-13 (run alongside the `vocabulary_and_graph_spine` migration, which itself only creates tables). No script created them, so the 100 inbox rows added since 2026-08-14 (66 X bookmarks, 20 Telegram links, 10 voice notes, 4 thoughts) never reached the graph, tagging, embedding or Tonidexbot.
- **`scripts/sync_captures.py`** (new, untracked). Creates a `kind='capture'`, `source_table='inbox'` node for every inbox row without one. Same projection as the backfill, checked against all 902 backfilled nodes: `title` = `inbox.title`, else the first 120 chars of `full_text`; `body` = `full_text`; `url` = `inbox.url`; `occurred_at` = `source_created_at`, else `captured_at`. Nodes have no image fields: `tag_images.py` reads `media_urls` from the inbox row. Insert-only, upserts with `ignore_duplicates` on `(source_table, source_id)`, so re-runs are safe. `--dry-run` supported. Never deletes; nodes whose inbox row is gone are reported only.
- **Workflow:** `tag-and-embed.yml` now runs `sync_captures.py` first, before `tag_captures.py` (uncommitted, along with `sync_captures.py` and the three model changes).
- **Backfill run:** the 100 nodes were inserted (ids 1127–1226) with the same projection in SQL through the Supabase MCP, because neither the cloud shell nor the Mac's sandboxed shell can reach Supabase or Gemini (§7.9 in the atlas). Missing count checked afterwards: **0**. 1,003 capture nodes, 1,226 nodes in total.
- **`sync_post_edges()` run:** 6 edges added. All 7 posts with a `[[voice:]]` token now have their `from_voice_note` edge (7 in total), plus 12 `started_from` and 2 `discusses`.
- **Tagged and embedded ✅** (run on the Mac, 2026-09-28): all 100 new nodes text-tagged on `gemini-3.8-flash` (263 tag links, 222 concept links); the 40 with media went through the visual pass (37 tagged, 3 images unfetchable); all 100 embedded. Checked in the database afterwards: missing 0, unembedded 0, untagged captures 1 (the old one the tagger has nothing to tag in). The ~900 older captures keep their 3.5-flash-lite tags on purpose.
- **One orphan node:** capture node for inbox `49ea0331-9ae8-4730-942a-c7751dcd3d01`, whose inbox row was deleted. Left in place.
- **Drift not synced:** the script only inserts. One backfilled node (a TikTok link whose inbox `full_text` later grew from 32 to ~2,000 chars) still carries the old text.
- **Models:** the three Python taggers now default to `gemini-3.8-flash` (tag_captures was on 3.5-flash-lite, the others on 3.7-flash). Confirmed working on the 2026-09-28 backfill run.
- **Housekeeping:** a `git status` from the sandboxed shell left an empty `.git/index.lock` it couldn't remove. Moved to `_to_delete/git-index.lock.stale-2026-09-28` so git works; safe to delete.

## 2026-09-28: blog posts published, linked into the graph, functions locked down ✅

- **Six new posts published** from blog-candidate voice notes (agents, Apple event, Stripe/OpenRouter, personal superintelligence, Dyson CameraJet, shortification), plus Foldables. All 8 published posts are in the graph (`kind='post'`, real `/blog/<slug>` URL), embedded and tagged.
- **Post links are now real graph edges.** New SQL function `sync_post_edges()` (migration `20260928000001`) turns each post's links into `edge` rows with `origin='post_links'`: `started_from` (post → take, from `commentary_ids`), `discusses` (post → project, from `related_project_ids`), `from_voice_note` (post → capture, from `[[voice:]]` tokens). Idempotent; `sync_posts.py` calls it at the end of every run, so links set or removed in the admin follow on the next sync. Before this, those links only lived as arrays on `published_posts`.
- **Takes linked** by hand after reading them (similarity alone ranks the same few takes top for every post): GEO and Stripe → the Reddit/GEO take; Foldables and Apple → the Meta Muse take; Agents → the custom-MCPs take; Superintelligence → the Private Cloud Compute take. Projects deliberately left mostly empty: the suggestions were ~0.63 matches to unrelated uni projects.
- **Security gap closed.** `retag-item`, `semantic-search`, `answer-question`, `presign-media` and `backfill-voice-audio` now require a signed-in user or the service role key (checked: anon key → 401 on all five; signed-in admin calls work). `answer-question` also accepts an `x-shortcut-key` header for the iOS Shortcut; the key is `SHORTCUT_KEY` in `.env` and only its SHA-256 is stored, in `public.function_keys` (migration `20260928000002`). The Shortcut in `scripts/ios_shortcut_guide.md` was never built, so nothing uses the header yet.
- **Admin:** Run check now shows the real error (e.g. Gemini spend cap) instead of "non-2xx". `admin-post-media` accepts article links as image addresses (uses the page's share image; `resolve_image` action).
- **GEO post slug** is now `why-geo-will-rely-on-human-influencers`; `/blog/untitled-mtdm8gna` redirects (vercel.json).
- **`drafts-lab.html`** (repo root, untracked, local only): the one-off page used to lay out the voice-note drafts: Gemini shape and cutouts, found images and links, an editor like the admin's, "Make it a draft". Its work lives in the browser's IndexedDB. Kept for now; delete when no longer useful, never commit it.

## 2026-09-23: the blog rebuild (pushed, live) ✅

Commit `6d8121d`, plus `7a692b0` for the `/blog/<slug>` rewrite. Full detail is in `blog_editorial_rebuild_2026-09-23.md` (repo root).

- **Public blog** (`blog.html`): the Codex editorial layout from `SITE-HANDOFF.md`, with a serif title, opening paper note, numbered sections, pull quote, margin cutouts, "Sources & sparks" and the particle hydrangea footer. Posts live at `/blog/<slug>`. Under each article there is a reader zone: a collapsed voice note (1× / 1.5× / 2×), comments that need your approval before they appear, a mailing-list sign-up, "Also check this out" and links to X, LinkedIn and GitHub.
- **Shared renderer** (`assets/blog/editorial.js`): the admin preview is the real page, loaded in an iframe. Posts are still plain markdown with a few conventions: `> ` opening note, `## [LABEL] Heading`, `>> ` pull quote, `[[cutout:id]]`, `[[image:id]]` and `[[voice:id]]`.
- **Admin Blog tab**:
  - Drafts are only created once they have real content (the same rule as `sync_posts.py`), then autosave. Live posts wait for "Update live post".
  - Tabs:
    - Write: links, images from a URL, sources & sparks.
    - Shape: a verbatim Gemini pass, with the transcript kept in `transcript_md` and a sentence-by-sentence comparison.
    - Images: Gemini cutouts with the three prototype cutouts as style references, green background keyed out to a transparent PNG, moved beside any section.
    - Links & graph: graph status, plus the closest projects and takes.
    - Details: slug, date and tags.
  - A publish check blocks em dashes and images without alt text.
  - The 💬 Readers panel approves comments and lists sign-ups.
- **Supabase**:
  - Edge functions: `blog-studio` and `public-post-media` are new. `blog-link-check`, `admin-post-media` and `public-voice-presign` are updated.
  - Migrations: editorial fields, `transcript_md` hidden from the public key, `match_nodes_by_kind`, `blog_subscribers` and `blog_comments`. All are in `supabase/migrations/20260923*`.
- **Security fix**: `blog-studio`, `blog-link-check` and `admin-post-media` now require a signed-in user. `verify_jwt` alone accepts the public anon key.
- **Published GEO post**: now carries the Codex article and its three cutouts. The original text is kept in `transcript_md`.

---

## What changed since the last version

The 2026-08-12 version of this file is substantially out of date. Corrections:

| It said | Actually ✅ |
|---|---|
| 4 hats, 19 project cards | **5 hats, 54 cards** — `feat/contracting-hat` was merged (PRs #1 and #2) and pushed |
| `blog.html` is a "coming soon" placeholder | **Blog is live**, rebuilt 2026-09-23 in the editorial layout (see above) |
| `published_posts` is empty | **3 rows**: 1 published (GEO), 2 drafts with real content. The 13 empty drafts were deleted on 2026-09-22, and the new editor cannot create more |
| 460 captures untagged | **1** — the backlog was cleared, and tagging now runs weekly in CI |
| Admin has 6 tabs | **6 tabs, different set** — Explore, Tagging, Pics, Pending, Q&A, Blog |
| Nothing from the PRD has been built | Still true of the *Astro rebuild*, but the brain, blog and a live-data prototype now exist |
| "In the Lab" ideas are not surfaced | **Most are now on the site** — see the remaining gaps below |

---

## Layer 2 — the site

### Live now ✅

| File | State |
|---|---|
| `index.html` | 1,561 lines, single static file. Five hats: contracting, thinking, artisting, engineering, marketing. 54 project cards. **Zero live database calls** — every card's copy, quote and link is typed into `data-note` / `data-link` attributes by hand |
| `blog.html` | Editorial layout, rendered by `assets/blog/editorial.js`. Index and article views, `/blog/<slug>` through the `vercel.json` rewrite, images via `public-post-media`, voice via `public-voice-presign`, comments and sign-ups through the anon key (insert only) |
| `admin.html` | About 2,900 lines, single file, no build step. Tabs: Repos, Q&A, Digest, Pending, Explore, Pics, Tagging, Blog. Blog has a full-screen editor with a live preview and the 💬 Readers panel |

Design system: background `#030303` · Space Grotesk 300/400/500/700 · hat colours contracting `#A78BFA` · thinking `#C4956A` · artisting `#6EE7B7` · engineering `#5BB8FF` · marketing `#FBBF24`.

### Built but never wired up: the "connected" prototype ✅

**This is the most important undocumented thing in the repo.** The long-standing "the site can't read the database" problem is further along than any doc says.

- **`connected/index.html`** — 84 KB, dated 2026-08-25, **untracked in git**. It is `index.html` (same five hats, same 54 cards) *plus* a live data layer: it calls `functions/v1/public-project-data`.
- **`public-project-data`** — a deployed, ACTIVE edge function (`verify_jwt: false`, created ~2026-08-26). `GET ?project_id=<slug>` returns that project's answered Q&A rows plus its GitHub repo metadata. It uses the service-role key server-side so the browser never gets direct access to `project_qna_sessions` or `github_sync_cache`, both of which are RLS-locked to `authenticated`. It filters out `[meta]` Q&A rows (internal curation answers) and never returns `raw_data`.

So the read path from site → database exists, is deployed, and has a working front-end prototype. It has simply never replaced `index.html`. **Deciding whether to promote `connected/index.html` to the live site is the single highest-leverage open decision in this project.**

Before promoting it: it was built 2026-08-25, so check it against the current `index.html` for any card edits made since, and confirm `public-project-data` still returns what the page expects.

### Stale content on the live site

| Item | Site says | Should be |
|---|---|---|
| MSc status | "Distinction, September 2025" | Completed — graduated July 2025 |

---

## Layer 1 — the brain (summary)

Full detail and verification queries in `system_atlas.md` (repo root). Current shape ✅:

| | |
|---|---|
| `inbox` | 997 rows — 963 from X bookmarks, 34 from Telegram, across 24 folders |
| `node` | 1,116 — 903 captures, 96 Q&A answers, 74 portfolio entries, 29 repos, 12 commentary, 2 posts/drafts |
| Embedded | 1,116 of 1,116 |
| Captures untagged | 1 |
| Concepts | 251 · doors 12 · domains 13 · tags 2,254 · edges 128 |
| Links | 2,787 concept · 1,890 door · 587 domain · 3,935 tag |
| Q&A | 96 answered, **78 still unanswered** |

Tagging and embedding run weekly in GitHub Actions (Mondays 06:00 UTC). Four runs so far, all green; the job currently finds nothing to do because the backlog is clear. It resumes real work when new captures arrive — which for bookmarks means running the Chrome extension export.

### Knowledge-graph design *(carried forward — still accurate)*

The four sources share one shape, so a single query answers "what else connects to this". The original tables were not changed; nodes are a projection on top of them.

**Doors replaced skill clusters.** `product_engineering` became `design_engineering` and covers mechanical, hardware, robotics and 3D printing only, never web. `creative_media` and `creative_tech` are separate, because one is making media and the other is building creative software. `product_management` and `entrepreneurship` are new doors. Families: Intelligence, Building, Craft, Business.

**Domains are a second axis.** Discipline says what skill was used; domain says what world the work was in. This exists because several tagging answers tried to put an industry into the discipline field. Events and weddings is the largest domain by a distance, covering seven projects.

**Concepts have three tiers.** Technical concepts came from the portfolio JSON. Topic concepts were added afterwards, because the bookmarks are about what Toni is interested in and the JSON only described what he had built with — so drones, AR, wearables and AI-and-jobs had nowhere to go. Entities are freeform, and the Promote panel in the admin turns a recurring one into a real concept in one click.

**Privacy.** Every table has RLS on. The graph tables have no anonymous policy and `anon` grants are revoked, so they're blocked twice. `published_posts` keeps its public read policy, which is correct for the blog. Since 2026-08-29 every auth-only policy also carries an explicit `WITH CHECK` — without it, anyone holding the public anon key could write.

**Model notes.** `text-embedding-004` is retired and 404s. `gemini-embedding-2` returns one blended vector when handed a list, so `embed_nodes.py` checks the count it gets back and drops to one call per item rather than assigning a wrong vector. `generate_digest.py` and `generate_questions.py` are still on the retired `google.generativeai` SDK; `tag_posts.py` needs the current `google-genai` SDK instead.

---

## New since 2026-09-21: the query bot ✅

A **second Telegram bot** now exists — `telegram-query` — for *querying* the second brain rather than capturing into it. Not mentioned in any other doc.

- Source: `supabase/functions/telegram-query/index.ts`, 30 KB, dated 2026-09-21 — **untracked in git**
- Deployed and ACTIVE as `telegram-query`, version 1, `verify_jwt: false`
- Auth: `X-Telegram-Bot-Api-Secret-Token` header plus a whitelist on the sender's Telegram user ID, both checked before touching the database
- Its own secrets: `TG_QUERY_BOT_TOKEN`, `TG_QUERY_WEBHOOK_SECRET`; shares `TELEGRAM_ALLOWED_USER_ID`, `GEMINI_API_KEY`, `R2_*`, `SUPABASE_*`
- Serves cards from the graph with semantic search (`match_nodes`), tag search, folder counts and related concepts, with R2 images presigned in-function
- Live-tested end to end on 2026-09-22: text and photo replies, folder inference from misheard voice terms, related-tag chips. Working.

All six database helpers from migration `telegram_query_bot_support` are confirmed present and working (an earlier version of this doc said two were missing — that was wrong, verified directly against `information_schema` on 2026-09-22, not carried forward):

| Helper | Confirmed | Called by the bot |
|---|---|---|
| `bot_tag_search` | ✅ | 3× |
| `bot_cards` | ✅ | 3× |
| `bot_folder_counts` | ✅ | 2× |
| `bot_related_concepts` | ✅ | 2× |
| `bot_node_card` (view) | ✅ | 2× |
| `bot_query_session` (table) | ✅ — has 1 live row from real use | 4× |

---

## New since 2026-09-22: captures/drafts/commentary all tag on their own now ✅

The tagging pipeline now covers everything that gets written, not just published posts:

- **`sync_posts.py`** — widened from published-only to any post/draft with real content (a non-placeholder title or ≥20 chars of body). Draft nodes get `kind='draft'` and no `url` (nothing to link to yet); published ones get `kind='post'` and their real `/blog/{slug}` url. Editing a synced post clears its embedding **and** `tagged_at`, and deletes its gemini-origin doors/domains/concepts/tags, so the next tagging run redoes it instead of leaving stale tags next to new content. `topic_tags` links are now fully reconciled each run (added and removed), not just added.
  - **Bug found and fixed 2026-09-22:** the first version selected a non-existent `node_tag.id` column when reconciling `topic_tags` links (the real PK is the composite `(node_id, tag_id)`) — crashed the whole run on the first node processed, before it ever reached the new draft. Fixed; reran clean.
- **`sync_commentary.py`** — new. Pushes `commentary` (the takes you write on a capture or a digest item) into the graph as their own nodes, `kind='commentary'`, so a thought is searchable the moment you write it, whether or not it ever becomes a post. Title is synthesised from the take's first line, since commentary has no title field. URL is set to the originating capture's URL when the take is about exactly one inbox item, left null for digest takes clustering several.
- **`tag_posts.py`** — generalised with `--source {published_posts,commentary}` instead of being hardcoded to posts, so one tagger now covers both. Default model bumped from `gemini-3.5-flash-lite` (copied from `tag_captures.py`'s default without checking) to `gemini-3.7-flash`, matching `tag_images.py`. Your one published post was tagged once under the old default before this fix — cosmetic only, rerun with `--retag` if you want it redone.
- **Workflow (`tag-and-embed.yml`)** now runs, in order: `sync_captures.py` (added 2026-09-28) → `tag_captures.py` → `tag_images.py` → `sync_posts.py` → `tag_posts.py --all` → `sync_commentary.py` → `tag_posts.py --source commentary --all` → `embed_nodes.py`. **Still uncommitted — see below.**
- Result as of 2026-09-22: 12/12 commentary rows and 2/2 post/draft rows in the graph, all tagged, all embedded. Full node counts below are current.

**Update 2026-09-23:** `related_project_ids` and `commentary_ids` can now be set from the editor (Links & graph). Suggestions come from `blog-link-check` through `match_nodes_by_kind`, and you confirm each one.

**Resolved 2026-09-23:** `da88cf93…` was reworked in place as the test draft, now titled "When Generative Engines Need *Human Influencers*".

**Resolved 2026-09-28:** `tag_captures.py`, `tag_images.py` and `tag_posts.py` all default to `gemini-3.8-flash` now (was 3.5-flash-lite / 3.7-flash). Edge functions stay on the `gemini-flash-latest` alias.

---

## Uncommitted and untracked work in the repo

As of `7a692b0`, the blog work, `sync_posts.py`, `tag_posts.py`, `sync_commentary.py`, the workflow change and the `telegram-query` source are all committed. Still untracked, and deliberately left out:

| Path | What it is |
|---|---|
| `connected/` | the live-data site prototype, still unpromoted |
| `Toni-Avalon-Summary.md`, `toni-avalon-contextnew.md` | Avalon engagement context |
| `assetsforsite/*.jpg/png` | new portraits and a white contracting hat |
| `_to_delete/` | scratch, including `codex-cutouts/`, which is safe to delete |
| `assetsforsite/portdesign [Auto-saved].pptx` | modified by PowerPoint autosave |

**Migrations:** the 2026-09-23 migrations are in `supabase/migrations/20260923*`. The earlier RLS `WITH CHECK` fix and `telegram_query_bot_support` were applied straight to the database and are still not written back, so the repo still can't rebuild the whole schema.

---|---|
| `.github/workflows/tag-and-embed.yml` | adds two steps between the visual tagging pass and embedding: `sync_posts.py`, then `tag_posts.py --all`. **Not pushed, so the live weekly job does not run them** |
| `.gitignore` | adds `applicationZZ/` — job-search material, correctly kept out of a repo with a public remote |

**Untracked:**

| Path | What it is |
|---|---|
| `scripts/sync_posts.py` | 2026-09-22, revised same day. Pushes posts AND real-content drafts into the graph — see "captures/drafts/commentary" section above for the full current behaviour. The `node_tag.id` bug is fixed |
| `scripts/tag_posts.py` | 2026-09-22, revised same day. Now `--source`-generalised for both `published_posts` and `commentary`; default model is `gemini-3.7-flash` |
| `scripts/sync_commentary.py` | 2026-09-22, new. Pushes `commentary` takes into the graph — see above |
| `supabase/functions/telegram-query/` | the query bot above — deployed, but its source is untracked |
| `connected/` | the live-data site prototype above |
| `Toni-Avalon-Summary.md`, `toni-avalon-contextnew.md` | Avalon engagement context |
| `assetsforsite/*.jpg/png` | new portraits and a white contracting hat |
| `_to_delete/` | scratch |

**Also worth knowing:** `supabase/migrations/` contains only the three original August files. The RLS `WITH CHECK` fix and `telegram_query_bot_support` were applied straight to the database and never written back as migration files, so the repo cannot rebuild the current schema.

---

## What the JSON still has that the site doesn't

Most of the previous version's gap list has closed — the five-hat rebuild surfaced the idea-stage work. Verified still missing from `index.html` ✅:

| ID | Title |
|---|---|
| `plantain_detector` | Plantain Ripeness Detector (Meta glasses) |
| `cranfield_predictive` | Predictive Maintenance — Aircraft Engines |
| `cranfield_networks` | Aviation Network Analysis (NetworkX) |

Skill clusters are still not surfaced at all — eight clusters with full skill lists and project cross-links sit in the JSON, and the PRD calls for them as interactive nodes. The experience timeline is still partial: the JSON holds nine roles.

`sync_portfolio.py` has not been run since **2026-08-13**, so the graph's copy of the portfolio predates the five-hat rebuild. It is not part of any schedule.

---

## A category of work that is in none of this

`toni_esan_portfolio_unfin.json` only covers code projects. A large body of work — ChatGPT Work workflow suites, reusable skills, document packs, Apple Shortcuts, native apps, demo environments and training material — is in neither the JSON, the graph, nor the site. It is inventoried in `portfolio_context_from_gpt.md` (repo root), which is currently its only structured record, along with an editorial brief for writing it up and an evidence map of source paths.

---

## Still to do

Moved to `TODO.md` (repo root) on 2026-09-28, so there is one to-do list for both layers. This file only records what exists and how it works.

---

## Related docs

| Doc | For |
|---|---|
| `TODO.md` (repo root) | Everything still to do, both layers |
| `system_atlas.md` (repo root) | Layer 1 pipeline, verification queries, gotchas |
| `portfolio_context_from_gpt.md` (repo root) | inventory of non-GitHub work + writing brief |
| `admin_drafts_rebuild_brief.md` (repo root) | 2026-09-22 handoff brief for reworking the admin Blog/drafts UI around the tagging pipeline (now done) |
| `blog_editorial_rebuild_2026-09-23.md` (repo root) | what the blog rebuild changed, in detail |
| `toni_esan_portfolio_platform_prd.md` | the Astro rebuild spec — still unbuilt |
| `second_brain_architecture.md` (repo root) | earlier graph write-up |

**Note on paths:** every doc reference in this file is now a real, verified path as of 2026-09-22. Earlier versions pointed at a `claude/` subfolder that never existed on disk (`claude/system_atlas.md`, `claude/architecture.md`, etc.) — everything actually lives at the repo root. If a future edit adds a doc reference, verify the path exists before writing it in.
