# Portfolio — Current State

**Date:** 2026-09-22 · **Branch:** `main`, in sync with `origin/main` · **Supersedes** the 2026-08-12 version

Everything marked ✅ below was verified on this date directly against the Supabase project (`dmlwcrbjetpgqacblvqp`), the deployed edge-function list, the GitHub Actions tab and the working copy. Claims carried over from the previous version without re-checking are marked *(carried forward)*.

Companion doc: `claude/system_atlas.md` — the same system from the Layer 1 / pipeline side, with verification queries. This doc is the Layer 2 / site-and-repo view. Don't duplicate between them.

---

## What changed since the last version

The 2026-08-12 version of this file is substantially out of date. Corrections:

| It said | Actually ✅ |
|---|---|
| 4 hats, 19 project cards | **5 hats, 54 cards** — `feat/contracting-hat` was merged (PRs #1 and #2) and pushed |
| `blog.html` is a "coming soon" placeholder | **Blog is live** — 486 lines, reads `published_posts`, renders posts, tags, sources and voice clips |
| `published_posts` is empty | **15 rows** — 1 published, 14 abandoned empty drafts |
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
| `blog.html` | 486 lines. Reads `published_posts` directly via the anon key. Post list, detail view, markdown, tags, sources section, voice playback via `public-voice-presign`, `#slug` deep links |
| `admin.html` | 2,002 lines, single file, no build step. Six tabs: Explore, Tagging, Pics, Pending, Q&A, Blog |

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

Full detail and verification queries in `claude/system_atlas.md`. Current shape ✅:

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
- **Workflow (`tag-and-embed.yml`)** now runs, in order: `tag_captures.py` → `tag_images.py` → `sync_posts.py` → `tag_posts.py --all` → `sync_commentary.py` → `tag_posts.py --source commentary --all` → `embed_nodes.py`. **Still uncommitted — see below.**
- Result as of 2026-09-22: 12/12 commentary rows and 2/2 post/draft rows in the graph, all tagged, all embedded. Full node counts below are current.

**Deliberately not done:** `related_project_ids` is still never populated on any post — matching post content against the project graph is a separate, bigger piece of work, out of scope for today.

**Open question, needs you:** one `published_posts` row (`da88cf93…`) is a second `kind='draft'` node, still titled "Untitled post," with tags nearly identical to the published GEO post. Unclear whether it's a genuine second draft or an abandoned editor session on the same post before it went live. Not deleted — nothing here deletes anything.

**Open question, needs you:** `tag_captures.py` is still on `gemini-3.5-flash-lite`, the one model version left unaudited. Everything else that does text tagging is now on `3.7-flash` or the `gemini-flash-latest` alias.

---

## Uncommitted and untracked work in the repo ⚠️

The working copy contains real work that is not in git. None of it is on `origin`.

**Modified, not committed:**

| File | Change |
|---|---|
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

`toni_esan_portfolio_unfin.json` only covers code projects. A large body of work — ChatGPT Work workflow suites, reusable skills, document packs, Apple Shortcuts, native apps, demo environments and training material — is in neither the JSON, the graph, nor the site. It is inventoried in `claude/portfolio_context_from_gpt.md`, which is currently its only structured record, along with an editorial brief for writing it up and an evidence map of source paths.

---

## Still to do

**Decisions**
- Promote `connected/index.html` to the live site, or fold its data layer into `index.html`? The read path is already deployed.
- Commit the untracked work, or keep it local? Nothing above is on `origin`.

**Fixes**
- Push the workflow change, or the blog posts/commentary never sync in CI (it currently only runs locally, on demand).
- Write the applied migrations back into `supabase/migrations/` (`telegram_query_bot_support` included).
- MSc copy on the live site.
- Decide the `tag_captures.py` model version (still 3.5-flash-lite) and the duplicate "Untitled post" draft — both flagged above, both need you, neither touched.

**Known gaps**
- `sync_portfolio.py` is stale and unscheduled.
- 78 unanswered Q&A questions.
- 13 empty draft rows in `published_posts` — the editor has no autosave, so abandoned drafts accumulate. (One further row now has real content and is a graphed `draft` node — see open question above.)
- `related_project_ids` is never populated, so posts stay off the project graph.
- Skill clusters and the full experience timeline are unrendered.
- No claims layer — the reusable statements for job applications, to be distilled from the 96 answers.
- YouTube enrichment has never executed; there are no YouTube captures at all.

---

## Related docs

| Doc | For |
|---|---|
| `claude/system_atlas.md` | Layer 1 pipeline, verification queries, gotchas |
| `claude/portfolio_context_from_gpt.md` | inventory of non-GitHub work + writing brief |
| `claude/architecture.md` | build history and deeper background |
| `toni_esan_portfolio_platform_prd.md` | the Astro rebuild spec — still unbuilt |
| `second_brain_architecture.md` (repo root) | earlier graph write-up |
