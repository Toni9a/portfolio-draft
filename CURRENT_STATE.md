# Portfolio — Current State
**Date:** 2026-08-12 · **Last git push:** 2026-04-01

---

## What exists

### Files
| File | Purpose |
|---|---|
| `index.html` | Main portfolio — 878 lines, single-file HTML/CSS/JS |
| `blog.html` | Blog placeholder — "coming soon" screen only |
| `admin.html` | Admin UI — magic-link auth, 4 tabs: Repos, Q&A, Digest, Pending (see below) |
| `toni_esan_portfolio_unfin.json` | Full data source — projects, skills, experience, identity |
| `toni_esan_portfolio_platform_prd.md` | Platform PRD written 2026-06-28 — full Astro rebuild spec |
| `docs/telegram_ingest_prd.md` | Telegram capture bot PRD — implemented 2026-08-12 |
| `portdesign.pdf` | Original design moodboard |
| `assetsforsite/` | Hat images (thinking/artisting/engineering/marketing), hydrangea, name |
| `context/` | CV PDF, Cranfield project docs, new cv aid doc |

### Telegram capture bot (live, 2026-08-12)
- Supabase edge function `telegram-ingest` deployed to `dmlwcrbjetpgqacblvqp`, webhook registered with BotFather bot `tonipp`
- Routes voice notes (Gemini transcription + auto-tagging), links (dynamic folder-button keyboard, top 6 + full-list fallback), plain text (auto-tagged as "thought"), and a catch-all "other" bucket — all landing in `inbox` with `source` prefixed `telegram_`
- Uses `gemini-flash-latest` alias (not a pinned version) after `gemini-2.5-flash` was retired mid-project without notice
- Folder replies work with or without Telegram's explicit reply gesture (falls back to "most recent pending folder question for this user" if not an explicit reply)
- Every bot confirmation message has an inline 🗑️ Delete button wired to the row's id
- `folder1, folder2` syntax in a folder reply files under folder1 and adds the rest as `topic_tags` (chosen over an array-typed `folder` column to avoid touching `generate_digest.py`/admin queries elsewhere)
- Security: `TELEGRAM_ALLOWED_USER_ID` whitelist + `X-Telegram-Bot-Api-Secret-Token` header check, both as edge function secrets (never in code)

### Admin UI — Pending tab (new, 2026-08-12)
- Added to `admin.html` alongside existing Repos/Q&A/Digest tabs, same visual system
- "Needs folder" view: telegram-sourced rows with `folder IS NULL` (nav badge shows live count)
- "All captures" view: every telegram-sourced row regardless of folder, with transcript/text/link preview, tags, and folder label
- Inline folder-assignment input (re-filing supported) and delete, no schema changes — reuses the same `inbox` table the bot writes to

### Live site sections (index.html)
1. **Hero** — "Toni" cyan / "Esan" white, 4 hat nav links, hydrangea card
2. **Work** — 4 hat subsections (thinking / artisting / engineering / marketing), 19 project cards
3. **AI Built** — 6 cards (Claude, GPT, Gemini builds) — *not in JSON*
4. **Consulting** — 4 service cards + CTA — *not in JSON*
5. **About** — bio, contact, education, interests, languages
6. **Footer**

### Design system
- Background: `#030303` · Cyan: `#5BB8FF` · Font: Space Grotesk 300/400/500/700
- Hat colours: thinking `#C4956A` · artisting `#6EE7B7` · engineering `#5BB8FF` · marketing `#FBBF24`
- Nav: 3 dot-matrix tiles (E → work, i → about, heart → blog.html), Resumé pill
- Leaf SVG decoration in 3 corners

---

## What the JSON has that the site doesn't show

### "In the Lab" — 16 idea-stage projects (status: "idea")
None are surfaced on the site. PRD calls for a dedicated section.

| ID | Title |
|---|---|
| `magkit_photo_alert` | MagKit Auto Photo Alert & Album Viewer |
| `plantain_detector` | Plantain Ripeness Detector (Meta glasses) |
| `gym_segmentation` | Gym Segmentation & Muscle Visualisation |
| `photo_order_helper` | Photo Order Helper (facial age sort) |
| `clothing_3d_wardrobe` | Clothing Autodetect & Virtual Wardrobe |
| `instagram_maps` | Instagram × Google Maps Integration |
| `explored_map` | Explored — % of Area Explored App |
| `spotify_memory` | Spotify Memory (photos + music timeline) |
| `pacetune` | Pacetune (running playlists from pace splits) |
| `rag_youtube` | RAG for YouTube Videos (quiz generation) |
| `pastor_assist` | PastorAssist (sermon transcription + Telegram bot) |
| `telegram_gym_streaks` | Telegram Gym Streaks |
| `physio_app` | Physio App — Pain & Muscle Visualisation |
| `cv_retail_analytics` | CV for Purchase Detection (Retail Analytics) |
| `knock_to_light` | Knock-to-Light Translator |
| `ccard_gpt` | CCard from GPT Chats (infographic cards) |
| `spotify_outfit_match` | Spotify Outfit Match |
| `keys_site` | Timikeys Project Site |
| `meta_glasses_networking` | Meta Glasses — Event Face Detection & Networking |

### Shipped projects missing from site
| ID | Title |
|---|---|
| `cranfield_networks` | Aviation Network Analysis (NetworkX) |
| `cranfield_predictive` | Predictive Maintenance — Aircraft Engines |
| `cranfield_optimisation` | Search & Optimization (Genetic Algorithms) |
| `aston_smart_cot` | Smart Cot for Baby Monitoring (Arduino) |
| `livia_soft` | LiviaSoft — GNSS & Bluetooth Research |

### Skill clusters — not surfaced at all
8 clusters defined in JSON with full skill lists and project cross-links. PRD calls for interactive nodes.

| ID | Label |
|---|---|
| `ai_ml` | AI & Machine Learning |
| `computer_vision` | Computer Vision |
| `data_analytics` | Data Analytics & Simulation |
| `product_engineering` | Product Engineering & Prototyping |
| `web_software` | Web & Software Development |
| `creative_media` | Creative & Visual Production |
| `automation_iot` | Automation & IoT |
| `business_consulting` | Business, Consulting & GTM |

### Experience timeline — only partially shown
Site shows Leveret + Santander. JSON has 9 roles:
- Leveret AI — Technical Officer (Jun 2024–Present)
- Self-Employed Consulting — Founder (Dec 2022–Present)
- Santander HQ — Events & Operations (Jan 2024–Present)
- GXO Logistics / John Lewis — Product Engineer (Jan–Nov 2023)
- Drain Doctor — Field Engineering Coordinator (Oct 2021–Jul 2022)
- Beaconsfield Dental — IT Operator (Sep 2020–Feb 2021)
- LiviaSoft Technologies — Research Assistant (Sep 2019–Apr 2020)
- W Motors — Design Intern, Dubai (Apr 2018)
- Navya — AV Work Experience (2019)

---

## What the site has that isn't in the JSON

- **AI Built section** — 6 cards showcasing Claude/GPT/Gemini-assisted work
- **Consulting section** — 4 service cards (AI automation, web builds, CV prototyping, social strategy)
- **Leaf SVG decoration** — botanical motif across 3 sections

---

## Stale content on live site

| Item | Site says | Should be |
|---|---|---|
| MSc status | "Distinction, September 2025" | Completed — graduated July 2025 |
| Blog | "Coming soon" | Still placeholder — no posts |

---

## PRD summary (toni_esan_portfolio_platform_prd.md)

Written 2026-06-28. Specifies a full platform rebuild — not just a site refresh.

**Recommended stack:** Astro + React islands · Supabase (pgvector) · Vercel Cron · Browser extension (xarchive fork)

**Three systems:**
1. Core portfolio — Astro content collections from the JSON
2. Cool News pipeline — Twitter bookmarks → digest → commentary → blog
3. Project expansion pipeline — GitHub sync → Q&A intake → rich project pages

**Build phases:**
- Phase 0 — Astro parity rebuild (port JSON, match current visual)
- Phase 1 — Brain foundations (Supabase schema, bookmark capture, review page)
- Phase 2 — Pipeline automation (cron digest, publish flow, blog pages)
- Phase 3 — Project pipeline (GitHub sync, Q&A intake, media galleries)
- Phase 4 — Polish (repurpose flags, build logs, Obsidian mirror)

**Nothing from the PRD has been built yet.** Still on the original single-file HTML site.

---

---

## Knowledge graph (2026-08-13)

The four sources now share one shape, so a single query answers "what else connects to this".
The original tables were not changed. Nodes are a projection on top of them.

### Numbers

| | |
|---|---|
| Nodes | 1,103 — 903 captures, 96 answers, 59 projects, 29 repos, 11 roles and qualifications, 4 ventures, 1 commentary |
| Embedded | 1,103 of 1,103 |
| Captures tagged | 443 of 903 |
| Concepts | 251 |
| Loose entities | 330 not yet promoted to concepts |
| Links | 745 concept, 699 door, 146 domain, 1,330 tag, 128 edges |

### Tables

`door` (11 doors in 4 families) · `concept` · `domain` · `tag` · `node` · `edge` ·
and the joins `node_door`, `node_concept`, `node_domain`, `node_tag`.

View `node_full` gives a node with its doors, domains, concepts and tags as arrays. Its columns
are listed explicitly rather than `select n.*`, because `*` freezes at creation and silently
misses columns added later. Function `related_nodes(node_id)` returns everything one hop out with
a reason attached. Function `match_nodes(vector, count)` does similarity search. All are
`security_invoker` and revoked from `anon`.

### Doors replaced skill clusters

`product_engineering` became `design_engineering` and covers mechanical, hardware, robotics and
3D printing only, never web. `creative_media` and `creative_tech` are separate, because one is
making media and the other is building creative software. `product_management` and
`entrepreneurship` are new doors. Families: Intelligence, Building, Craft, Business.

### Domains are a second axis

Discipline says what skill was used, domain says what world the work was in. This exists because
several tagging answers tried to put an industry into the discipline field. Events and weddings
is the largest domain by a distance, covering seven projects.

### Concepts have three tiers

Technical concepts came from the portfolio JSON. Topic concepts were added afterwards, because
the bookmarks are about what Toni is interested in and the JSON only described what he had built
with, so drones, AR, wearables and AI-and-jobs had nowhere to go. Entities are freeform, and the
Promote panel in the admin turns a recurring one into a real concept in one click.

### Privacy

Every table has RLS on. The graph tables have no anonymous policy and `anon` grants are revoked,
so it is blocked twice. `published_posts` keeps its public read policy, which is correct for the
future blog.

## Scripts

| Script | What it does |
|---|---|
| `sync_portfolio.py` | Pushes the JSON into the graph. Run after editing the JSON. Clears the embedding on anything whose text changed. |
| `tag_captures.py` | Tags captures against the concept list with `gemini-3.5-flash-lite`. Never touches `inbox.folder` and never creates an edge. Folder matching is case-insensitive. |
| `embed_nodes.py` | Embeds nodes with `gemini-embedding-2` at 768 dimensions. |
| `generate_embeddings.py` | Same, for `commentary`. |
| `generate_digest.py`, `generate_questions.py` | Still on the retired `google.generativeai` SDK and `gemini-2.5-flash`. Not yet moved over. |

Model notes: `text-embedding-004` is retired and 404s. `gemini-embedding-2` returns one blended
vector when handed a list, so `embed_nodes.py` checks the count it gets back and drops to one per
call rather than assigning a wrong vector.

## Admin

Six tabs now. Repos, Q&A, Digest, Pending, **Explore**, **Tagging**.

Explore loads all 1,103 nodes once and filters in the browser. Filters stack across types and
combine within a type. Clicking an item shows what it connects to, ordered by how rare the shared
thing is, so real edges come first and common concepts like Python sink and are dimmed.

Tagging shows the script running live, refreshing every five seconds, with the item text and link
so tags can be judged. Wrong strips only what the model added. Promote turns a recurring entity
into a concept and links every item already carrying it.

The magic link now returns to `window.location.pathname`, so it works on `/admin.html` locally and
`/admin` on Vercel.

## Still to do

- **460 captures untagged** — interaction design 133, MJ aesthetic 114, web design 109, hard pics 101.
  Mostly a handle and a link with the content in an image, so tagging sees little. Embeddings cover them.
- **Images are never read.** `gemini-embedding-2` is multimodal, so a pass over `media_urls` is possible.
  Costs about $0.00012 an image. Not attempted.
- **330 loose entities.** Mostly company names, which make poor concepts. Promote selectively.
- **78 unanswered Q&A questions** still sitting in the admin.
- **`index.html` does not read the JSON.** The site is hand written and the JSON has never driven it.
- **No claims layer yet.** The atomic reusable statements for job applications. Distil from the 96 answers.
- **No publish step.** `published_posts` is still empty and `blog.html` is still a placeholder.
