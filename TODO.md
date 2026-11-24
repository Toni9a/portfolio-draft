# To do

**Last updated:** 2026-11-24 · Replaces `claude/next_session_todo.md` (2026-08-29), whose open items are folded in below.

This is the single to-do list for both layers. `CURRENT_STATE.md` says what exists and how it works; this file says what's left. When something here is done, delete it here and record it in `CURRENT_STATE.md` under a dated heading. Update the date above whenever you edit this file.

---

## Quick wins

None open.

## Layer 2: the site

- [ ] **Screenshots for the older homepage cards** (LyricVid, Gymscrap, Write-sync and the rest): the new `.card-thumb` slot is ready; needs an image per card.
- [ ] **Tonidex Map on the live site** shows a long column of tiles above the constellation (seen 2026-11-24). Probably unclustered nodes; check `tonidex.html` layout.
- [ ] **Add the Nov 2026 projects to `toni_esan_portfolio_unfin.json`** (Fit with Faith, local florist, Northants Fridge, ChristyHome, Fuel Log, Adizero, HM posters) so the graph links them.
- [ ] **Unused files to delete:** `content/work/media/local-florist/home.jpg`, `bento.jpg`.
- [ ] **Homepage: wire in the live data.** The butterfly homepage is live (2026-10-05) but its cards are still hand-written. Next: fold in `connected/index.html`'s `public-project-data` layer. Old note: **Decide the homepage.** Promote `connected/index.html` (reads live from the data) to the live site, or fold its data layer into `index.html`. Today the live homepage shows 2 of 9 roles, misses 5 shipped projects, and has nowhere for the 16 "in the lab" ideas. This is the biggest gap on the site. The butterfly hero/flock is ready to fold into whichever wins: preview at `/index-butterfly.html` (local, see `content/butterfly/README.md`).
- [ ] **Render skill clusters and the full experience timeline.** Scaffold built 2026-10-01: `about.html` (local). Next: style pass, link from the homepage, move the Avalon role into the JSON. The data is in `toni_esan_portfolio_unfin.json` and the graph; nothing shows it.
- [ ] **Mailing list sending.** Sign-ups are stored in `blog_subscribers`; nothing sends. Needs Resend (or similar), an unsubscribe link and double opt-in.
- [ ] **Link Shortification and Dyson to takes** if a relevant take is ever written. None fit today.

- [ ] **Add newer work to `toni_esan_portfolio_unfin.json`:** the Avalon role and the case-study projects, so `sync_portfolio.py` (now scheduled) carries them.

- [ ] **Grandma TV:** add the NFC cards photo/video (placeholder box on the case study).
- [ ] **Kraft sketches:** swap the generated doodles for Toni's own sketches (`content/work/screenshots-to-add/sketches/`).
- [ ] **Work page:** add the background switch and orb transitions to `work.html` too.

## Layer 1: the second brain

- [ ] **Visuals, optional:** run `python3 scripts/embed_nodes.py --reembed-images` (cheap) so meaning search and `tonidex_similar` use image captions; later consider true image embeddings (~711 Gemini calls) for look-alike matching.

- [ ] **Run `python3 scripts/archive_media.py`** (Mac) so the 26 un-archived images from the 2026-11-17 X import show in Tonidex Visuals. Repeat after every X import, or add it to `tag-and-embed.yml` (the R2 secrets would need adding to GitHub).
- [ ] **Algorithm view, optional:** map TikTok searches/watch spikes to Tonidex concepts (needs embeddings of search terms); refresh `algo_snapshot` from a new export every few months (`ingest_social.py --apply`).
- [ ] **Tonidex next steps** (built 2026-10-15): push and try it on real data; decide whether a public, curated version belongs on the site (only images/ideas Toni marks public, never the raw bookmarks); image captions are done (746 of 748; 288 filled by `--missing-captions` on 2026-10-15). Delete the retired `caption-import` edge function, the empty `caption_import` table and the `caption-import-temp` row in `function_keys` (all temporary, from 2026-10-15).

- [ ] **Answer the 78 unanswered Q&A questions** (admin → Q&A). They feed the graph and the claims layer below.
- [ ] **Claims layer.** Draft in `claims_draft_2026-10-01.md`: approve/reword, then load into a `claim` table. Distil reusable statements for job applications from the 96 answered questions.
- [ ] **Re-run the Twitter bookmark capture** from the Chrome extension to pull in newer bookmarks. Dedup is safe: `bookmark-ingest` upserts by URL and `sync_captures.py` never creates a second node for the same inbox row. Still check what the extension sends for sub-folders and whether it lands in `inbox.folder`.
- [ ] **YouTube links (next).** Toni will send YouTube links. Fetch free yt-dlp subtitles in a separate background shell so other work isn't blocked. **No Gemini on them without asking Toni first.** Instagram is now covered by `watch_videos.py`.
- [ ] **`enrich_captures.py` still runs on the Mac.** It needs a home IP (TikTok/YouTube block datacentre IPs), so it can't join the GitHub Actions job as-is. Tagging, image tagging and embedding already run there weekly.

## Security and housekeeping

- [ ] **`bookmark-ingest` accepts the public anon key** by design, because the Chrome extension calls it. Give it a key like `answer-question`'s (`x-shortcut-key` checked against a hash in `public.function_keys`).

## Rules that still apply

- Any new "auth only" RLS policy on a table the anon key can reach needs an explicit `WITH CHECK`, not just `USING`.
- Every edge function that spends Gemini credit or reads private data checks for a signed-in user itself; `verify_jwt` alone accepts the public anon key.
- Never commit `.env` or `applicationZZ/`. Never delete data without confirming which rows.
