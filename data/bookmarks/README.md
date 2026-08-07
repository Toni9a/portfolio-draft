# Bookmark Exports

Raw xarchive exports live here. Never edit these manually — they're the source of truth that the pipeline reads from.

## Files
- `xarchive_YYYY-MM-DD.json` — full xarchive export from X/Twitter. Bookmarks are tagged by folder name in the `folders[]` field on each bookmark.

## Re-exporting
1. Open Chrome with the xarchive extension installed
2. Browse to x.com (just needs to be open so the extension captures auth)
3. Open the xarchive extension popup → Start Export
4. Export completes in ~5–10 min depending on bookmark count
5. Save the output JSON to this folder as `xarchive_YYYY-MM-DD.json`
6. The pipeline script will diff against the previous export and only process new items

## Folder reference (as of 2026-08-06)
| Folder | Count | Purpose |
|---|---|---|
| cool news | 167 | Blog pipeline source — AI, tech, science |
| Hard projects | 135 | Project inspo / reference |
| interaction design | 135 | UI/UX reference |
| MJ aesthetic | 116 | Visual / aesthetic reference |
| web design | 110 | Web design reference |
| hard pics | 101 | Visual reference / photography |
| code | 35 | Dev snippets / tools |
| Teaching | 26 | Education content |
| Papers | 20 | Academic papers |
| uk culture | 19 | UK culture reference |
| [unfiled] | 1062 | Pre-folder bookmarks, not yet categorised |
