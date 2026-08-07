# Portfolio — Current State
**Date:** 2026-06-29 · **Last git push:** 2026-04-01

---

## What exists

### Files
| File | Purpose |
|---|---|
| `index.html` | Main portfolio — 878 lines, single-file HTML/CSS/JS |
| `blog.html` | Blog placeholder — "coming soon" screen only |
| `toni_esan_portfolio_unfin.json` | Full data source — projects, skills, experience, identity |
| `toni_esan_portfolio_platform_prd.md` | Platform PRD written 2026-06-28 — full Astro rebuild spec |
| `portdesign.pdf` | Original design moodboard |
| `assetsforsite/` | Hat images (thinking/artisting/engineering/marketing), hydrangea, name |
| `context/` | CV PDF, Cranfield project docs, new cv aid doc |

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
