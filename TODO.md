# To do

**Last updated:** 2026-09-28 · Replaces `claude/next_session_todo.md` (2026-08-29), whose open items are folded in below.

This is the single to-do list for both layers. `CURRENT_STATE.md` says what exists and how it works; this file says what's left. When something here is done, delete it here and record it in `CURRENT_STATE.md` under a dated heading. Update the date above whenever you edit this file.

---

## Quick wins

- [ ] **MSc line on the homepage.** `index.html` still says "Distinction, September 2025"; it should say completed July 2025.
- [ ] **Delete the test draft** "When Generative Engines Need Human Influencers" (`da88cf93…`) in the admin. It's a copy of the published GEO post and is still in the graph as a draft.
- [ ] **Apple post title.** The whole title is wrapped in `*asterisks*`, so it all renders italic blue, and it's lowercase after the first word.
- [ ] **Delete `drafts-lab.html`** (repo root, untracked, local only) once it's no longer useful. Never commit it.
- [ ] **Delete `_to_delete/`** (repo root): the copied Codex cutouts and a stale git lock file.

## Layer 2: the site

- [ ] **Decide the homepage.** Promote `connected/index.html` (reads live from the data) to the live site, or fold its data layer into `index.html`. Today the live homepage shows 2 of 9 roles, misses 5 shipped projects, and has nowhere for the 16 "in the lab" ideas. This is the biggest gap on the site.
- [ ] **Render skill clusters and the full experience timeline.** The data is in `toni_esan_portfolio_unfin.json` and the graph; nothing shows it.
- [ ] **Mailing list sending.** Sign-ups are stored in `blog_subscribers`; nothing sends. Needs Resend (or similar), an unsubscribe link and double opt-in.
- [ ] **Link Shortification and Dyson to takes** if a relevant take is ever written. None fit today.

## Layer 1: the second brain

- [ ] **Answer the 78 unanswered Q&A questions** (admin → Q&A). They feed the graph and the claims layer below.
- [ ] **Claims layer.** Distil reusable statements for job applications from the 96 answered questions.
- [ ] **`sync_portfolio.py` is stale and unscheduled.** Refresh it and add it to `.github/workflows/tag-and-embed.yml`.
- [ ] **Semantic search cap.** `match_nodes()` goes through the HNSW index (ef_search 40), so it never returns more than about 40 nodes. The admin's "search by meaning" is affected; the blog already uses the exact-scan `match_nodes_by_kind`. Raise ef_search or switch to an exact scan.
- [ ] **Re-run the Twitter bookmark capture** from the Chrome extension to pull in newer bookmarks. Dedup is safe: `bookmark-ingest` upserts by URL and `sync_captures.py` never creates a second node for the same inbox row. Still check what the extension sends for sub-folders and whether it lands in `inbox.folder`.
- [ ] **YouTube and Instagram.** `enrich_captures.py` has only been tested on TikTok. Test YouTube and Instagram, then scope real YouTube video analysis (transcript + frames into Gemini). Talk it through before building.
- [ ] **`enrich_captures.py` still runs on the Mac.** It needs a home IP (TikTok/YouTube block datacentre IPs), so it can't join the GitHub Actions job as-is. Tagging, image tagging and embedding already run there weekly.

## Security and housekeeping

- [ ] **`bookmark-ingest` accepts the public anon key** by design, because the Chrome extension calls it. Give it a key like `answer-question`'s (`x-shortcut-key` checked against a hash in `public.function_keys`).
- [ ] **Write missing migrations back into `supabase/migrations/`:** `telegram_query_bot_support`, the 2026-08-29 RLS `WITH CHECK` fix, and the 2026-08-13 one-off capture backfill (`sync_captures.py` is now the only record of its mapping).
- [ ] **Orphan capture node** for deleted inbox row `49ea0331-9ae8-4730-942a-c7751dcd3d01`. Left in place; delete only once you confirm.

## Rules that still apply

- Any new "auth only" RLS policy on a table the anon key can reach needs an explicit `WITH CHECK`, not just `USING`.
- Every edge function that spends Gemini credit or reads private data checks for a signed-in user itself; `verify_jwt` alone accepts the public anon key.
- Never commit `.env` or `applicationZZ/`. Never delete data without confirming which rows.
