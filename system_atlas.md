# System Atlas — toniesan.com

**Purpose:** orientation doc for a fresh Claude/LLM session. Read this before `claude/architecture.md` — this tells you what is *true right now*; `architecture.md` tells you *how things were built* in more depth.

**Last verified:** 2026-09-22, directly against the Supabase database (`dmlwcrbjetpgqacblvqp`), the deployed edge-function list, the GitHub Actions tab (`Toni9a/portfolio-draft`) and the working copy on Toni's Mac. Every number below was read from the live system on that date, not copied from older notes.

**Revised the same day, after inspecting the repo.** The first version of this doc inherited three wrong claims from `claude/architecture.md`: that `feat/contracting-hat` was unmerged (it is merged and pushed), that `blog.html` was a placeholder (it is live), and that nothing connected the site to the database (a deployed edge function and a working prototype do). Three deployed edge functions were missing entirely. Treat this as the standing lesson: **verify against the system, not against the notes.**

**Rule for future sessions:** the notes in this repo have drifted from reality before. If a claim matters, re-run the check in §9 rather than trusting the number written here.

---

## 0. Thirty-second orientation

- One Supabase project holds everything. One repo: `Toni9a/portfolio-draft`. One R2 bucket for media.
- **Layer 1 (second brain)** — capture → Gemini tagging → concept graph → semantic search. Built, live, automated, healthy.
- **Layer 2 (portfolio site)** — `toniesan.com`, a single hand-written `index.html`. Live, but stale and completely disconnected from Layer 1.
- **The central open problem:** Layer 2 doesn't read Layer 1. The data is in the graph; the website never queries it. See §6.
- Nothing scrapes autonomously. Every capture starts with a human action (a Telegram message, or clicking export on x.com).
- The only fully automated thing is a weekly GitHub Actions job that tags and embeds new captures.

---

## 1. The two layers

| | Layer 1 — Second brain | Layer 2 — Portfolio site |
|---|---|---|
| What it is | Capture, tag, graph, search system | Public portfolio at `toniesan.com` |
| Built of | Supabase (Postgres + Auth + Edge Functions + pgvector), Cloudflare R2, Python scripts, `admin.html` | A single static `index.html`, no build step |
| State | Live, automated, healthy | Live, hand-written, stale |
| Data source | Live database | Text typed into HTML attributes by hand |
| Who sees it | Only Toni (auth-gated admin UI) | Public |

They share a database but no data flow. That is the defining fact of this project's current state.

---

## 2. Live numbers

Verified 2026-09-22. Unchanged since 2026-09-17 — nothing new has been captured in that window.

| Metric | Value | Note |
|---|---|---|
| `inbox` rows | 997 | the single intake table |
| — from X bookmarks | 963 | via Chrome extension |
| — from Telegram | 34 | voice, links, thoughts |
| Distinct folders | 24 | |
| Rows with stored media | 994 | in R2 |
| Rows with a `media_error` | 38 | mostly TikTok rate limits / dead posts |
| `node` rows (graph) | 1,103 | see breakdown below |
| Nodes still untagged (text) | 1 | effectively cleared |
| Nodes missing an embedding | 0 | fully embedded |
| `concept` | 251 | curated — promoted by hand in the admin UI |
| `door` | 12 | top-level themes |
| `domain` | 13 | fields of knowledge |
| `tag` | 2,254 | freeform, machine-generated |
| `edge` | 128 | explicit node-to-node links |
| `node_concept` links | 2,782 | |
| `node_tag` links | 3,928 | |
| `project_qna_sessions` | 174 | your written answers about projects |
| `commentary` | 12 | your own takes, separately embedded |
| `published_posts` | 15 | **1** actually published, 14 drafts |
| `github_sync_cache` | 29 | repo READMEs |

### `node` breakdown by source

| `source_table` | Rows | Last written | Touched by the weekly job? |
|---|---|---|---|
| `inbox` | 903 | 2026-09-01 | **Yes** |
| `project_qna_sessions` | 96 | 2026-08-13 | No |
| `portfolio_json` | 74 | **2026-08-13** | No |
| `github_sync_cache` | 29 | 2026-08-13 | No |
| `commentary` | **12** | 2026-09-22 | Yes, since 22 Sep |
| `published_posts` | **2** | 2026-09-22 | Yes, since 22 Sep |

Total **1,116** nodes (was 1,103 on 17 Sep). All embedded, 0 missing. The 200 showing `tagged_at IS NULL` are the `portfolio_json`, `project_qna_sessions` and `github_sync_cache` rows, which are out of scope by design — not a backlog. Commentary and posts joined the pipeline on 22 Sep via `sync_commentary.py` and `sync_posts.py`; both are fully tagged.

**Important for any future session:** the tagging/embedding pipeline only operates on `source_table = 'inbox'`. Do **not** read `tagged_at IS NULL` counts on the other source tables as a backlog — they are out of scope by design.

`portfolio_json` = 59 projects, 9 roles, 4 ventures, 2 degrees.

### Biggest folders

| Folder | Rows |
|---|---|
| cool news | 197 |
| interaction design | 138 |
| Hard projects | 137 |
| MJ aesthetic | 120 |
| web design | 109 |
| hard pics | 106 |
| Teaching | 47 |
| code | 35 |

`cool news` is the folder the blog/digest pipeline draws from.

---

## 3. The full path, capture to surface

```
SOURCES            Telegram bot          Chrome extension        Manual / API
                   (voice/link/text)     (xarchive fork)         (shortcuts)
                        |                      |                      |
                        | webhook              | JSON export          | POST
                        v                      v                      v
INGEST             telegram-ingest       seed_from_xarchive.py   bookmark-ingest
                   (edge fn, v22)        (local script)          (edge fn)
                        |                      |                      |
                        +----------------------+----------------------+
                                               |  insert / upsert-by-URL (dedup)
                                               v
STORE                           inbox  (997 rows, Postgres)  <----+
                                   |                              |
                +------------------+------------------+           | writes
                | untagged rows                       | status=new| stored_media
                v                                     v           |
ENRICH   GitHub Actions (weekly, automated)    enrich_captures.py -+
         tag_captures.py                       (Mac only, home IP)
         tag_images.py                                |
         embed_nodes.py                               | media
                |                                     v
                |                          Cloudflare R2 (capture-media)
                |                                     |
                v                                     |
GRAPH    node (1,103) + concept/door/domain/tag       | presigned GET
         + pgvector embeddings (768d)                 |
                |                                     |
        +-------+--------+------------------+         |
        |                |                  |         |
        v                v                  v         v
SURFACE index.html    blog.html         admin.html <--+
        (NO live      (LIVE - reads     (Explore, Tagging,
         DB read)      published_posts)  Pics, Pending, Q&A, Blog)

        connected/index.html  -- prototype, untracked, never deployed
        (index.html + live reads via public-project-data)
```

Read the break as the point of the diagram: `blog.html` reads the database, `admin.html` reads the graph, and `index.html` — the actual portfolio — reads nothing, even though a working prototype that does sits beside it in the repo.

---

## 4. Component inventory

### Infrastructure

| Thing | Value |
|---|---|
| Supabase project | `dmlwcrbjetpgqacblvqp`, region eu-west-2 (London) |
| Supabase URL | `https://dmlwcrbjetpgqacblvqp.supabase.co` |
| R2 account / bucket | `eb8193d2791bec64568e1115104e2e1d` / `capture-media` (private, no public URL) |
| Repo | `Toni9a/portfolio-draft`, local at `~/personal port/` |
| Hosting | Vercel — `toniesan.com`, `portfolio-draft-ten.vercel.app` |
| Models | `gemini-2.5-flash` (text), `gemini-2.0-flash` (vision), `gemini-embedding-2` (768d) |

R2 was chosen over Supabase Storage deliberately: Supabase pauses after 7 days idle, and R2 egress is free (the Pics grid reloads many images).

### Core tables

| Table | Holds |
|---|---|
| `inbox` | every captured item; the single intake point. `url` nullable + unique, `folder`, `status`, `source`, `full_text`, `topic_tags`, `media_urls`, `stored_media`, `media_error`, `raw_data` |
| `node` | one row per graph item, `source_table` + `source_id` point back to origin. Carries `embedding`, `tagged_at`, `image_tagged_at` |
| `concept` / `door` / `domain` / `tag` | the four facet vocabularies |
| `node_concept` / `node_door` / `node_domain` / `node_tag` | many-to-many joins |
| `edge` | explicit node-to-node relationships |
| `commentary` | Toni's own takes, own embedding — the "backfeed corpus" |
| `published_posts` | blog posts. `slug`, `title`, `body_md`, `source_urls[]`, `related_project_ids[]`, `related_skill_cluster_ids[]`, `captured_on`, `published_at` |
| `project_qna_sessions` | Q&A answers, surfaced as modal quotes on the site |
| `github_sync_cache` | repo READMEs and metadata |
| `project_media` / `post_media` | media attachments |

### Edge functions

| Function | `verify_jwt` | Does |
|---|---|---|
| `telegram-ingest` | **false** | bot webhook; routes by message type, calls Gemini, archives voice to R2. **v22.** Guarded by user whitelist + secret header |
| `bookmark-ingest` | true | generic upsert-by-URL into `inbox` |
| `retag-item` | true | re-runs Gemini on one item from the admin UI |
| `presign-media` | true | short-lived signed R2 GET URLs; credentials never reach the browser |
| `semantic-search` | true | embeds a query, calls `match_nodes()`, returns ranked hits |
| `answer-question` | true | powers the Q&A tab and iOS shortcut |
| `blog-link-check` | true | Gemini pass over a draft: suggests bookmark links to cite, a title, and topic tags. **v2** |
| `public-voice-presign` | **false** | signs blog voice clips, only if the `[[voice:ID]]` token is in that post's body AND the post is published |
| `backfill-voice-audio` | true | one-off backfill of historical Telegram voice notes; idempotent |
| `public-project-data` | **false** | public read-only project summary for the site: answered Q&A + GitHub metadata, service-role server-side, `[meta]` rows and `raw_data` withheld. Deployed ~26 Aug. **Undocumented until 22 Sep** |
| `admin-post-media` | true | media handling for blog posts. Deployed ~28 Aug. Undocumented until 22 Sep |
| `telegram-query` | **false** | second bot — queries the brain (semantic + tag search, cards, folder counts, related concepts, presigned R2 images). Deployed 21 Sep, source untracked. Own secrets `TG_QUERY_BOT_TOKEN` / `TG_QUERY_WEBHOOK_SECRET`. **Two of its six DB helpers are missing — see §8** |

### Scripts (`scripts/`, run from `~/personal port/`)

Updated 2026-11-18. Every script in `scripts/` is listed. "Weekly, CI" means it runs in `tag-and-embed.yml` (Mondays 06:00 UTC). The rest run in Toni's Terminal on the Mac: neither cloud shell can reach Supabase or Gemini. Each script's docstring has the full usage.

**Ingest: getting things into `inbox`**

| Script | Runs | Does |
|---|---|---|
| `seed_from_xarchive.py` | after each xarchive export | Upserts X bookmarks from the xarchive JSON into `inbox` (`--file`, `--dry-run` shows the new count per folder). With no `--folder` it takes every foldered bookmark; unfoldered ones are skipped on purpose (gotcha 5). **Then run `archive_media.py`** (gotcha 5b). |
| `ingest_social.py` | after a new IG/TikTok export | Loads Instagram + TikTok saves into `inbox` and feed/algorithm data into `algo_snapshot` (`--dry-run`, `--apply`, `--skip-algo`). Exports live in `~/Downloads/social_exports/`, never committed. |
| `watch_videos.py` | Mac only, by hand | The video pass for social saves: yt-dlp metadata and subtitles, picks a `video_route`, and calls Gemini only where needed (`--run --source --folder --limit --max-spend-usd`, `--plan-only`). Needs a home IP. |
| `enrich_captures.py` | Mac only, by hand | The older enrichment worker for Telegram captures: YouTube/TikTok captions via yt-dlp, with a Whisper fallback. Setup is in `ENRICH_SETUP.md`. |
| `github_sync.py` | by hand | Syncs all GitHub repos (non-fork) into `github_sync_cache`. Inclusion is toggled in the admin. |

**Media: images into R2**

| Script | Runs | Does |
|---|---|---|
| `archive_media.py` | **by hand, after every X import** | Copies capture images to R2 and fills `inbox.stored_media`. Tonidex Visuals and the map's image layer only show items with an R2 image (`bot_node_card.image_key`). Re-runs skip what's done. Not in CI. |
| `fetch_covers.py` | Mac, by hand | `--folder Aesth` (comma-separated for more): gets IG/TikTok post covers via yt-dlp with Chrome cookies, copies them to R2, and fills `media_urls`/`stored_media`. Follow straight away with `tag_images.py --all`, because IG cover links expire. Only for visual folders. |

**Graph: inbox, posts and portfolio into `node`**

| Script | Runs | Does |
|---|---|---|
| `sync_captures.py` | weekly, CI | Creates one `capture` node per inbox row that has none. Insert-only. Holds back rows whose `video_route` is pending or triaged out. Has `--source` and `--folder` filters. |
| `sync_posts.py` | weekly, CI | Pushes blog posts and real-content drafts into the graph, then calls `sync_post_edges()`. |
| `sync_commentary.py` | weekly, CI | Pushes `commentary` (takes) into the graph as their own nodes. |
| `sync_portfolio.py` | weekly, CI | Pushes `toni_esan_portfolio_unfin.json` (projects, roles, degrees) into the graph. |

**Tagging and embedding**

| Script | Runs | Does |
|---|---|---|
| `tag_captures.py` | weekly, CI | Gemini text tagging of captures: doors, domains, concepts and tags. Never touches `inbox.folder`. |
| `tag_images.py` | weekly, CI | Gemini vision tagging of `media_urls`, and saves `node.image_caption`. `--missing-captions` fills captions only. |
| `tag_posts.py` | weekly, CI | The same tagging for posts/drafts (`--all`) and commentary (`--source commentary`). |
| `embed_nodes.py` | weekly, CI | Embeds nodes with no embedding (gemini-embedding-2, 768d), including `image_caption`. `--reembed-images` redoes captioned images once. |
| `generate_embeddings.py` | by hand | Embeds `commentary` rows in their own column (separate from node embeddings). |

**Content helpers**

| Script | Runs | Does |
|---|---|---|
| `generate_digest.py` | by hand | Clusters new `cool news` items into 5–8 digest items (`digest_items`). Still on the retired `google.generativeai` SDK. |
| `generate_questions.py` | by hand | Writes Q&A prompts per repo into `project_qna_sessions` for Toni to answer. Same old SDK. |

**Debug and one-offs**

| Script | Runs | Does |
|---|---|---|
| `debug_ffmpeg.py` | when broken | Isolates ffprobe / audio-extraction failures with verbose output. |
| `test_tiktok.py` | when broken | A 10-line yt-dlp check against one hard-coded TikTok URL. |

Other files: `requirements.txt` (pip deps for CI and Mac), `ENRICH_SETUP.md` (enrich_captures setup), `ios_shortcut_guide.md` (the iOS Shortcut for `answer-question`, never built).

**Common runs**
- **New X bookmarks:** `seed_from_xarchive.py --file <export>` → `sync_captures.py` → `tag_captures.py --all` → `tag_images.py --all` → `embed_nodes.py` → `archive_media.py`. The weekly job does every step except the first and last.
- **New IG/TikTok export:** `ingest_social.py --apply` → `watch_videos.py --run` → `sync_captures.py` → tag → embed. Then `fetch_covers.py` for visual folders.

### Admin UI — `admin.html`

Single file at repo root, ~1,300 lines, inline CSS + one `<script>`, no build step. Supabase Auth (password sign-in, magic link fallback). Tabs:

| Tab | Does |
|---|---|
| Explore | facet browsing (Kind/Doors/Domains/Concepts/Tags) + instant title filter + "🔮 Search meaning" semantic search |
| Tagging | progress + recent feeds for both passes; promote/reject entities; "Wrong" undo covers `gemini` and `gemini-image` origins |
| Pics | grid of items with stored media, presigned R2 URLs, lightbox, click a facet to filter the whole grid |
| Pending | every `telegram_%` item — tags, folder, blog flag, retag, delete, "needs folder" filter |
| Q&A | answers stored in `project_qna_sessions` |
| Blog | flagged-for-blog captures, draft editor, live preview, voice playback |

---

## 5. Automation — what runs without you

**`.github/workflows/tag-and-embed.yml`** — the only scheduled job in the system.

- Trigger: `cron: '0 6 * * 1'` (Mondays 06:00 UTC) + manual `workflow_dispatch`
- Steps: checkout → setup-python 3.11 → pip install → `tag_captures.py --all` → `tag_images.py --all` → `embed_nodes.py`
- Secrets: repo-level `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY`

Run history (verified 2026-09-22):

| # | Date | Trigger | Duration | Result |
|---|---|---|---|---|
| 1 | 1 Sep | manual | 32s | success |
| 2 | 7 Sep | scheduled | 29s | success |
| 3 | 14 Sep | scheduled | 37s | success |
| 4 | 21 Sep | scheduled | 28s | success |

Next due: Monday 28 Sep.

**The schedule is reliable — four consecutive Mondays, no intervention.** But the job is currently *idle*: both tagging steps log "Nothing left to tag there." / "Nothing left to do." because the backlog is cleared. It will stay that way until new rows land in `inbox`, which for bookmarks means clicking export in the Chrome extension.

Everything else — enrichment, portfolio sync, digest generation, commentary embedding, GitHub sync — is manual.

---

## 6. The seam — the central open problem

Two missing edges, one consequence.

**Break 1: `sync_portfolio.py` is not scheduled.** It pushes `toni_esan_portfolio_unfin.json` into the graph as `portfolio_json` nodes. It has run exactly once, on 2026-08-13. Anything added to that JSON since — including the five-hat site rebuild of 25 Aug — is not in the graph. It is not part of `tag-and-embed.yml` and no other schedule calls it.

**Break 2: `index.html` never queries the database — but the fix is already built.** All 54 cards' content (`data-note` quotes, `data-link` URLs, descriptions) is typed into HTML attributes by hand, even though 96 answered Q&A rows and 29 synced repos sit in the database ready to fill them.

What corrects the record (verified 2026-09-22): the read path exists and is deployed. `public-project-data` is an ACTIVE, public (`verify_jwt: false`) edge function that returns a project's answered Q&A plus its GitHub metadata, using the service-role key server-side so the RLS-locked tables are never exposed to the browser. And `connected/index.html` — 84 KB, dated 2026-08-25, untracked in git — is `index.html` plus a live data layer calling exactly that function. So Break 2 is not unbuilt; it is **built, deployed and unpromoted**. Deciding whether to promote it is the highest-leverage open decision in the project.

Consequence: closing either break alone changes nothing visible. A fresh sync puts current data into a graph nobody reads; wiring the site to the graph would render month-old data. **Both have to close for the portfolio to become self-updating** — which is the stated goal of this whole project.

Related: `blog-link-check` suggests a title, tags and bookmark links for a draft, but never `related_project_ids` — so blog posts stay disconnected from the project graph too, even though the column exists and the post template is designed to render those as "this came from / led to" chips. The project nodes to match against already exist in the graph (subject to Break 1's staleness).

**Break 3 (added 2026-09-22): a whole category of work is in neither layer.** `toni_esan_portfolio_unfin.json` — and therefore the graph, and therefore any future site wiring — only covers code projects, largely GitHub-backed ones. A large body of Toni's actual work is not in it: ChatGPT Work workflow suites, reusable skills, document packs, Apple Shortcuts, demo environments, native apps and training materials. That work is inventoried in `claude/portfolio_context_from_gpt.md`, which is currently the *only* structured record of it. Closing Breaks 1 and 2 would produce a self-updating portfolio that still shows none of it.

---

## 7. Gotchas — read before changing anything

1. **RLS needs an explicit `WITH CHECK`.** Eight tables once had an auth-only policy with `USING` but no `WITH CHECK`; Postgres does not fall back, so anyone with the public anon key (embedded in `blog.html` and `admin.html`) could write to them. Fixed 29 Aug via migration `fix_missing_with_check_on_auth_only_policies`. **Any new auth-only policy on an anon-reachable table needs both clauses.**

2. **Three separate secret stores, never synced.** Python scripts read `.env`; edge functions read Supabase function secrets (`supabase secrets set --env-file <f> --project-ref dmlwcrbjetpgqacblvqp`); the weekly job reads GitHub repo secrets. The same values live in all three. Rotating one does not touch the others.

3. **Redeploying `telegram-ingest` defaults to `verify_jwt: true`, which takes the bot down.** Telegram cannot send a Supabase JWT. Always redeploy with `verify_jwt: false`.

4. **`enrich_captures.py` cannot move to the cloud.** TikTok and Instagram bot-check datacenter IPs — confirmed again from a sandboxed shell on 1 Sep. It stays on the Mac (or a home-hosted runner). Instagram also needs browser cookies (`INSTAGRAM_COOKIES_BROWSER` in `.env`, defaults to Chrome).

5. **Unfoldered bookmarks are excluded on purpose.** `seed_from_xarchive.py` without `--all` only seeds bookmarks that are in a folder — 1,075 were correctly skipped in the last run. This is the extension's whole point (filter before Supabase), and `generate_digest.py` only surfaces items with a non-null folder anyway. Do not "fix" this.

5b. **An X import isn't finished until `archive_media.py` has run.** Order: `seed_from_xarchive.py` → `sync_captures.py` → tag → `tag_images.py` → embed → **`archive_media.py`**. Image tagging reads Twitter's URLs, so tags and captions work without R2, but Tonidex Visuals needs the R2 copy. Found 2026-11-18: 26 of the 2026-11-17 import's images were tagged but missing from Visuals for this reason. Twitter images that 404 (`media_error`) can't be recovered.

6. **`image_tagged_at IS NULL` is not an image backlog.** 163 inbox nodes have a null `image_tagged_at`, but `tag_images.py` reports nothing to do — because those rows have no images. The script filters on `media_urls`; a raw null count over-reports.

7. **The blog draft editor does not autosave.** "New draft" opens an editor; nothing is written to `published_posts` until an explicit save. Closing the tab loses the draft.

8. **Don't check for database objects in `pg_proc` alone.** A real mistake made on 22 Sep: `telegram-query`'s six `bot_*` helpers were checked with `select … from pg_proc where proname like 'bot\_%'`, which returned four, and the bot was wrongly written up as broken. `bot_node_card` is a **view** and `bot_query_session` is a **base table** — neither can ever appear in `pg_proc`. Query `information_schema.tables` as well, or the conclusion inverts. Verified: all six exist.

9. **The Supabase sandbox path is blocked from this environment.** A cloud session's shell cannot reach Supabase's REST API directly (403 at the egress proxy), though the Supabase MCP tools work fine. Scripts that hit PostgREST need to run on Toni's machine.

---

## 8. Status board

| Status | Item | Detail |
|---|---|---|
| ✅ Healthy | Capture, tagging, search | 997 captures, 1,103 nodes, all embedded, 1 text row untagged |
| ✅ Healthy | Weekly automation | 4/4 runs green, fires on schedule unattended |
| ✅ Fixed | RLS write hole | closed 29 Aug, verified with an anonymous request |
| ⏸ Idle | The weekly job | nothing left to process; needs new captures to do real work |
| 🔴 Stale | Portfolio graph copy | `sync_portfolio.py` last ran 13 Aug; not scheduled |
| ✅ Done | `feat/contracting-hat` | **merged and pushed** (PRs #1 and #2). Earlier docs called this blocked — that was stale. `main` is in sync with `origin/main` and carries the 5-hat site and the working blog |
| ✅ Working | `telegram-query` bot | a second bot (query the brain, not capture) deployed 21 Sep, source untracked. All six `bot_*` helpers exist and it was live-tested end to end on 22 Sep. An earlier version of this doc called it broken — that was **wrong**; see §7.9 |
| 🟡 Open | Blog sync not in CI | the workflow change adding `sync_posts.py` and `tag_posts.py` is uncommitted, so the live weekly job never syncs posts |
| 🟡 Open | YouTube enrichment | zero YouTube captures exist, so the code path has never executed. Post a link to the bot to make it testable |
| 🟡 Open | YouTube *analysis* | transcript + frames → Gemini, not just link capture. Scoped verbally, never built. Needs a scoping conversation first — do not start building unprompted |
| 🟡 Open | `related_project_ids` | never suggested or populated; blog posts stay off the project graph |
| 🟡 Open | MSc copy on site | says "Distinction, September 2025"; should be completed July 2025 |
| 🟡 Open | `embedded_at` timestamps | look stale on older rows despite embeddings being present; likely a script quirk, never investigated |
| 🟡 Open | Non-GitHub work is uninventoried outside one doc | see Break 3 in §6 — the JSON, the graph and the site all miss it |
| ⚠️ Verify | Undocumented local work in the repo | working copy is on `main` with uncommitted changes to `.github/workflows/tag-and-embed.yml` and `.gitignore`, plus **untracked** `scripts/sync_posts.py`, `scripts/tag_posts.py`, `supabase/functions/telegram-query/` and a `connected/` directory. None of these appear in any doc. Found 2026-09-22; scope unexamined — ask Toni before assuming what they do |
| ⚠️ Verify | Two doc contradictions | see below |

**Contradictions to settle, not to trust:**
- `architecture.md` says the admin UI is live at `toniesan.com/admin` in one section and "not deployed anywhere permanent, still `python3 -m http.server` locally" in another.
- The session notes record an 11m 55s "clean run" of the weekly job on 1 Sep. The Actions tab shows only four runs, the 1 Sep one lasting 32s. That longer run is not in the current history.

---

## 9. How to verify this doc

Re-run these rather than trusting the numbers above.

**Live counts:**
```sql
select
 (select count(*) from inbox) as inbox_total,
 (select count(distinct folder) from inbox where folder is not null) as folders,
 (select count(*) from node) as nodes,
 (select count(*) from node where source_table='inbox' and tagged_at is null) as untagged_text,
 (select count(*) from node where embedding is null) as unembedded,
 (select count(*) from published_posts) as posts;
```

**Is the portfolio sync stale?** (compare to the JSON's own last edit)
```sql
select max(created_at) from node where source_table = 'portfolio_json';
```

**Per-source node health:**
```sql
select source_table, count(*), max(tagged_at) as last_tagged
from node group by source_table order by source_table;
```

**Did the weekly job run?** → `https://github.com/Toni9a/portfolio-draft/actions/workflows/tag-and-embed.yml`
Check the run list for a new entry each Monday, and open the job to read the step logs — "Nothing left to tag there." means idle, not broken.

**Is the site updated?** → check whether `feat/contracting-hat` has been merged into the deployed branch.

---

## 10. Related docs

**Where these live (verified 2026-09-22):** the `claude/*.md` docs are docs in the **claude.ai Project**, not files in the repo — there is no `claude/` directory on disk. The repo root holds `CURRENT_STATE.md`, `second_brain_architecture.md`, the PRDs, and `toni_esan_portfolio_unfin.json`.

| Doc | What it's for |
|---|---|
| `claude/portfolio_context_from_gpt.md` | **inventory of non-GitHub work** — ChatGPT Work workflows, skills, document packs, Shortcuts, demos, training material — plus an editorial brief for turning it into portfolio content and an evidence map of source paths on the Mac. Compiled by GPT 2026-09-22; treat its status/limits notes as binding, and do not upgrade its claims |
| `claude/architecture.md` | deeper build detail and history; where this doc and that one disagree on a number, **this one was verified live** |
| `claude/next_session_todo.md` | Toni's own carried-forward notes |
| `claude/session_summary_2026-09-01.md` | GitHub Actions setup, bookmark re-capture, TikTok/Instagram fixes |
| `claude/session_summary_2026-08-29.md` | blog tab, voice playback, the RLS security fix |
| `claude/admin_pics_tagging_search_2026-08-19.md` | Pics tab, Tagging tab, semantic search build |
| `telegram_ingest_prd.md` | original bot spec (historical intent — the shipped code has moved past it) |
| `second_brain_capture_prd.md` | capture system spec |
| `toni_esan_portfolio_platform_prd.md` | the Astro rebuild PRD — **none of it is built**; still the original single-file site |
| `toni_esan_portfolio_unfin.json` | the richer portfolio data source; not read by `index.html`, synced into the graph by `sync_portfolio.py` |
| `CURRENT_STATE.md` (repo root) | Layer 2 status doc — **stale**: dated 2026-08-12, records "last git push 2026-04-01", and describes the older 4-hat / 19-card site, not the 5-hat rebuild |

---

## 11. If you're a fresh session, start here

1. Read §0, §6 and §7. That's the state, the problem, and the landmines.
2. Before quoting any number, re-run the relevant check in §9 — notes in this repo have drifted before.
3. Most infrastructure already exists. Check what's built before building anything.
4. Two things need a conversation with Toni before being started: YouTube video *analysis*, and anything that changes how the portfolio site renders.
