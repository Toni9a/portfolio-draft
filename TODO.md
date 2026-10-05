# To do

**Last updated:** 2026-10-05 · Replaces `claude/next_session_todo.md` (2026-08-29), whose open items are folded in below.

This is the single to-do list for both layers. `CURRENT_STATE.md` says what exists and how it works; this file says what's left. When something here is done, delete it here and record it in `CURRENT_STATE.md` under a dated heading. Update the date above whenever you edit this file.

---

## Quick wins

None open.

## Layer 2: the site

- [ ] **Homepage: wire in the live data.** The butterfly homepage is live (2026-10-05) but its cards are still hand-written. Next: fold in `connected/index.html`'s `public-project-data` layer. Old note: **Decide the homepage.** Promote `connected/index.html` (reads live from the data) to the live site, or fold its data layer into `index.html`. Today the live homepage shows 2 of 9 roles, misses 5 shipped projects, and has nowhere for the 16 "in the lab" ideas. This is the biggest gap on the site. The butterfly hero/flock is ready to fold into whichever wins: preview at `/index-butterfly.html` (local, see `content/butterfly/README.md`).
- [ ] **Render skill clusters and the full experience timeline.** Scaffold built 2026-10-01: `about.html` (local). Next: style pass, link from the homepage, move the Avalon role into the JSON. The data is in `toni_esan_portfolio_unfin.json` and the graph; nothing shows it.
- [ ] **Mailing list sending.** Sign-ups are stored in `blog_subscribers`; nothing sends. Needs Resend (or similar), an unsubscribe link and double opt-in.
- [ ] **Link Shortification and Dyson to takes** if a relevant take is ever written. None fit today.

- [ ] **Add newer work to `toni_esan_portfolio_unfin.json`:** the Avalon role and the case-study projects, so `sync_portfolio.py` (now scheduled) carries them.

- [ ] **Grandma TV:** add the NFC cards photo/video (placeholder box on the case study).
- [ ] **Kraft sketches:** swap the generated doodles for Toni's own sketches (`content/work/screenshots-to-add/sketches/`).
- [ ] **Work page:** add the background switch and orb transitions to `work.html` too.

## Layer 1: the second brain

- [ ] **Answer the 78 unanswered Q&A questions** (admin → Q&A). They feed the graph and the claims layer below.
- [ ] **Claims layer.** Draft in `claims_draft_2026-10-01.md`: approve/reword, then load into a `claim` table. Distil reusable statements for job applications from the 96 answered questions.
- [ ] **Re-run the Twitter bookmark capture** from the Chrome extension to pull in newer bookmarks. Dedup is safe: `bookmark-ingest` upserts by URL and `sync_captures.py` never creates a second node for the same inbox row. Still check what the extension sends for sub-folders and whether it lands in `inbox.folder`.
- [ ] **YouTube and Instagram.** `enrich_captures.py` has only been tested on TikTok. Test YouTube and Instagram, then scope real YouTube video analysis (transcript + frames into Gemini). Talk it through before building.
- [ ] **`enrich_captures.py` still runs on the Mac.** It needs a home IP (TikTok/YouTube block datacentre IPs), so it can't join the GitHub Actions job as-is. Tagging, image tagging and embedding already run there weekly.

## Security and housekeeping

- [ ] **`bookmark-ingest` accepts the public anon key** by design, because the Chrome extension calls it. Give it a key like `answer-question`'s (`x-shortcut-key` checked against a hash in `public.function_keys`).

## Rules that still apply

- Any new "auth only" RLS policy on a table the anon key can reach needs an explicit `WITH CHECK`, not just `USING`.
- Every edge function that spends Gemini credit or reads private data checks for a signed-in user itself; `verify_jwt` alone accepts the public anon key.
- Never commit `.env` or `applicationZZ/`. Never delete data without confirming which rows.
