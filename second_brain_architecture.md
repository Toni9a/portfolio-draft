# Second Brain — Architecture & Current State
**Date:** 2026-08-12 · **Backend:** Supabase project `dmlwcrbjetpgqacblvqp`

---

## 1. What "second brain" means here

Two jobs, one store of raw material:

1. **Second brain** — capture everything (voice notes, links, thoughts), connect it (tags, folders, references between items), and make it browsable. No filtering for "is this good enough" — the whole point is a judgment-free net.
2. **Blog** — a small, deliberate slice of that material, written mostly in your own voice (voice notes verbatim, or a take you've added), published as actual posts.

The second brain is not a subset of the blog. The blog is a subset of the second brain. Everything below is designed around that direction.

---

## 2. What's actually in the database right now

This isn't just Telegram/Twitter captures — there are **four** distinct capture streams that should all feed the same graph. Two are running, two are built but not yet run.

### A. `inbox` — bookmarks, links, thoughts, voice notes

| Source | Rows | What it is |
|---|---|---|
| `twitter` | 897 | Bookmarked tweets, synced in via an existing bookmark-ingest pipeline (predates this session). Already has `folder`, `author_handle`, `url`, `title`. |
| `telegram_link` | 3 | Links sent to the Telegram capture bot |
| `telegram_thought` | 1 | Plain-text thoughts sent to the bot |
| `telegram_voice` | 1 | Voice notes, transcribed + tagged by Gemini |

**902 rows.** Two different capture pipelines, same table.

### B. `toni_esan_portfolio_unfin.json` — the static identity graph

This is not in Supabase, it's the source-of-truth JSON that drives the live site. It already contains a real graph, just not a database one:

- **39 projects**, each with `skills_used` (→ skill cluster ids), `tech_tags`, `category`, `key_contributions`, `metrics`, and a `learnings` field — genuine written reflection per project, already there.
- **8 skill clusters** (`ai_ml`, `computer_vision`, `data_analytics`, `product_engineering`, `web_software`, `creative_media`, `automation_iot`, `business_consulting`), each with a skill list and `related_project_ids` linking back to projects.
- **Education, experience (9 roles), interests/identity, design guidance.**

This is a hand-authored graph — projects ↔ skill clusters ↔ tech tags — that already does what the Telegram/Twitter tag system is trying to grow into organically.

### C. GitHub → Q&A pipeline — running, partially worked through

This is the "comments I've written on projects" mechanism, and it's already live:

1. `github_sync.py` → pulled your repos into `github_sync_cache`. **29 repos synced, all `included`.**
2. `generate_questions.py` → generated 5 targeted questions per repo (why you built it, what was technically hard, what hat it falls under, whether it's TikTok/LinkedIn-worthy) into `project_qna_sessions`. **174 questions across 29 projects.**
3. Admin's **Q&A tab** → you've answered **96** of them; **78 skipped** (not answered — the admin Q&A view only shows unanswered ones, so those 78 are still sitting there waiting whenever you want to go back through them).

So this pipeline is genuinely running and already holds real project commentary — 96 written answers. It's the biggest actual content source in the "portfolio commentary" side of the second brain, bigger than anything from Telegram/Twitter so far.

### D. Folder distribution in `inbox` (mostly from the Twitter pipeline)

| Folder | Count |
|---|---|
| cool news | 167 |
| interaction design | 133 |
| Hard projects | 129 |
| MJ aesthetic | 114 |
| web design | 109 |
| hard pics | 101 |
| code | 34 |
| Teaching | 26 |
| uk culture | 19 |
| Papers | 18 |
| film | 14 |
| ML qz | 11 |
| AR cool | 7 |
| 3D | 5 |
| Education | 4 |
| robotics | 4 |
| App design | 1 |
| Fashion | 1 |
| Gym port | 1 |
| personal ai | 1 |
| Stox | 1 |
| *(unfiled)* | 2 |

900 of 902 items already have a folder. Only 2 items have `topic_tags` at all — both are the Telegram voice/link items retagged this session with the sharpened prompt. **The 897 Twitter bookmarks have never been tagged** — they were sorted into folders (by you, on Twitter, before capture) but Gemini has never looked at their content.

### Tags that exist today (all from Telegram items, all new)

`apple-intelligence`, `dji-vs-gopro`, `geofencing-regulation`, `meta`, `muse-spark`, `optical-image-stabilization`, `osmo-pocket`, `personalized-ai-agents`, `private-cloud-compute`

This is the target shape going forward — specific entities and claims, not category words. The gap is scale: 9 tags exist against 902 captured items.

### E. Full Supabase schema

**`inbox`** — the capture layer, shared by the Telegram and Twitter pipelines.
`id, url, source, folder, source_item_id, title, full_text, author_name, author_handle, media_urls[], status, my_note, topic_tags[], related_item_ids[], source_created_at, captured_at, created_at, raw_data (jsonb), telegram_message_id, telegram_bot_question_msg_id, telegram_from_user_id, raw_message_type, is_blog_candidate, awaiting_take`

**`commentary`** — your take, on one item or a cluster of items.
`id, digest_item_id (→ digest_items, nullable), body, embedding (vector, unused so far), topic_tags[], inbox_ids[] (direct-to-commentary path), created_at, updated_at`
1 row exists (the DJI/GoPro take).

**`digest_items`** — clusters of related inbox items, surfaced for commentary. Built by the (currently local, manual) `generate_digest.py` script.
`id, inbox_ids[], summary, topic_tags[], surfaced_at, status, created_at`
0 rows — not run yet against the current data.

**`published_posts`** — *already scaffolded in the schema, never used.* This is the publish layer, and it already anticipates cross-linking to your portfolio:
`id, slug, title, body_md, excerpt, cover_image_url, source_urls[], commentary_ids[], related_project_ids[], related_skill_cluster_ids[], topic_tags[], published_at, created_at, updated_at`
0 rows. `related_project_ids` and `related_skill_cluster_ids` are exactly the hooks needed to connect a blog post back to your portfolio's project/skill-cluster data — nobody's written to them yet, but the plumbing is there.

**`github_sync_cache`** — synced repos: `repo_full_name, readme_md, description, topics[], homepage_url, stars, last_commit_at, included, display_name, raw_data`. **29 rows.**

**`project_qna_sessions`** — the project-commentary layer: `project_id, question, answer, answered_at`. **174 rows, 96 answered, 78 still open across 29 projects.** This is where your project comments actually live.

**`project_media`** — media attachments per project (`storage_path, type, caption, sort_order`). 0 rows.

---

## 3. The three-layer model (how it should work)

```
┌───────────────────────────────────────────────────────────────────────┐
│  CAPTURE  —  four streams, all feeding the same graph                  │
│   • inbox: Telegram bot (voice/link/thought) + Twitter bookmark sync   │
│   • github_sync_cache: 29 repos, pulled by github_sync.py             │
│   • project_qna_sessions: 174 Gemini-generated Qs about your repos,    │
│     96 answered by you so far — the "comments on projects" layer      │
│   • toni_esan_portfolio_unfin.json: hand-authored projects, skill      │
│     clusters, education, experience — the identity graph, already rich │
│  No judgment on any of these. Everything lands, always.                │
└───────────────────────────┬─────────────────────────────────────────┘
                             │  tags, folders, related_item_ids,
                             │  skills_used, tech_tags, related_project_ids
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  KNOWLEDGE GRAPH  —  the "second brain" proper                │
│  Not a new table — the existing connections made traversable, │
│  across ALL four streams, not just Telegram/Twitter:           │
│   • tags as browsable nodes ("show me everything tagged X")   │
│   • folders as coarse clusters                                │
│   • related_item_ids as edges between captures (bidirectional)│
│   • skill clusters ↔ projects ↔ tech tags (already in the JSON)│
│   • shared vocabulary needed to connect inbox tags to the same │
│     skill-cluster ids the portfolio JSON already uses          │
└───────────────────────────┬─────────────────────────────────┘
                             │  is_blog_candidate + commentary
                             │  (from inbox OR from project Q&A)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  PUBLISH  —  published_posts (schema exists, unused)          │
│  A small, curated slice. Prefers voice-sourced commentary.     │
│  Pulls in related_project_ids / related_skill_cluster_ids      │
│  to connect a post back to the portfolio.                      │
│  blog.html renders from here — not from inbox directly.        │
└─────────────────────────────────────────────────────────────┘
```

**Why the middle layer matters:** right now, "connections" only show up as a side effect of admin UI code (the related-items list on a card). There's no way to ask "what else do I have tagged `dji`?", "show me everything in `interaction design` across Twitter and Telegram," or "show me every bookmark connected to the Leveret project." That last one is the real prize — it means a bookmark you saved six months ago about dental CV models could surface itself against the Leveret project page automatically, because they'd share a tag or skill-cluster id. That's not built yet; it needs the inbox tag vocabulary and the portfolio's `skill_clusters`/project ids to actually overlap.

---

## 4. What's built vs. what's a gap

**Built:**
- Unified capture across Telegram (voice/link/text) and Twitter bookmarks into one `inbox` table
- Folder filing (two-tier button UX + free text + multi-folder-as-tags convention on Telegram)
- Gemini tagging tuned for specificity (entities/claims, not categories) — Telegram side only
- Retag button (single + bulk) to re-tag existing items with the sharpened prompt
- Bidirectional connection display in admin (voice note → thing it referenced, and reverse)
- Manual tag editing (add/remove) per item
- `is_blog_candidate` flag, decoupled from folder
- Direct-to-commentary path (skip digest clustering for a single voice note or link)
- `published_posts` table scaffolded with portfolio cross-link columns
- GitHub → Q&A pipeline running: 29 repos synced, 174 questions generated, 96 answered — real project commentary already exists

**Gaps:**
- **897 Twitter bookmarks have never been tagged.** They have folders (from Twitter itself) but no Gemini-generated tags — the biggest untapped chunk of the second brain.
- **78 of 174 project Q&A questions are still unanswered.** Not a pipeline problem — the admin Q&A tab already surfaces exactly these, just a "go finish this" item whenever you want.
- **No tag/folder browsing view.** You can't yet click a tag and see everything connected to it across sources.
- **`generate_digest.py` still runs locally, manually.** No automated clustering happening.
- **No publish step exists.** Nothing turns a `commentary` row or a `project_qna_sessions` answer into a `published_posts` row. `blog.html` is still a placeholder.
- **No shared vocabulary between the inbox and the portfolio JSON yet**, even though `published_posts` already has `related_project_ids` / `related_skill_cluster_ids` columns for exactly this. Inbox tags are freeform Gemini output; the JSON's skill clusters are a fixed set of 8 ids. Nothing maps one to the other yet.
- **Three capture conventions, not two.** Twitter items use folders only; Telegram items use folders + tags; the portfolio JSON and Q&A pipeline use their own fixed `skills_used`/`tech_tags`/`category`/`project_id` vocabulary. All of these need to eventually speak the same tag language for the graph to actually connect across them.

---

## 5. Suggested next steps (not yet started, for discussion)

1. Decide whether to batch-tag the 897 Twitter bookmarks with the same sharpened Gemini prompt (this is the single biggest lever for making the inbox side of the graph useful).
2. Work through the remaining 78 unanswered project Q&A questions in the admin Q&A tab whenever you've got the headspace — that's 78 more pieces of real project commentary sitting there waiting.
3. Build a simple "browse by tag/folder/skill-cluster/project" view in admin — the missing traversal layer, spanning inbox, Q&A answers, and the portfolio JSON together.
4. Decide how inbox tags should map onto the portfolio's 8 fixed skill-cluster ids (e.g. does a Gemini tag like `gimbal-stabilization` get associated with `computer_vision` automatically, or does that stay manual?).
5. Build the publish step: `commentary` (from a bookmark/voice note) or a `project_qna_sessions` answer → drafted `published_posts` row, preferring voice-sourced material.
6. Get `blog.html` reading from `published_posts` instead of showing "coming soon."
