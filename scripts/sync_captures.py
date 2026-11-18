"""
sync_captures.py
────────────────
Pushes inbox captures into the graph: one node per inbox row, kind='capture',
source_table='inbox'. Until this script existed, capture nodes only came from
the one-off backfill run on 2026-08-13 alongside the vocabulary_and_graph_spine
migration, so every capture after that (bookmarks, Telegram links, thoughts and
voice notes) never reached the graph, tagging, embedding or Tonidexbot.

The projection matches what that backfill wrote (checked against all 902
backfilled nodes):
  title        inbox.title, or the first 120 chars of full_text when there's
               no title (Telegram links, thoughts and voice notes)
  body         inbox.full_text, untruncated (tag_captures.py and
               embed_nodes.py cap it themselves)
  url          inbox.url
  occurred_at  inbox.source_created_at, falling back to captured_at

Nodes carry no image fields: tag_images.py reads media_urls straight from the
inbox row via node.source_id, so a new node is picked up by the visual pass
automatically.

Insert-only and safe to re-run: rows that already have a node are left alone,
and the unique (source_table, source_id) constraint backs that up. Nothing is
ever deleted — nodes whose inbox row has gone are reported, not removed.

Runs weekly in CI before tag_captures.py. By hand:
  python scripts/sync_captures.py
  python scripts/sync_captures.py --dry-run
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

TITLE_CHARS = 120
BATCH = 200
# inbox.video_route values that must not become nodes yet (see ingest_social.py / watch_videos.py)
HOLD_ROUTES = {"pending", "triaged_out"}


def held(r: dict) -> bool:
    """Not ready (or never) for the graph: video pass pending, triaged out, or a dead
    video with no text at all (a node with only a URL can't be tagged or embedded)."""
    route = r.get("video_route")
    if route in HOLD_ROUTES:
        return True
    return route == "unavailable" and not (r.get("full_text") or r.get("title"))

DIM, RESET, GREEN, YELLOW = "\033[2m", "\033[0m", "\033[32m", "\033[33m"


def fetch_all(sb: Client, table: str, cols: str, **eq) -> list:
    rows, off = [], 0
    while True:
        q = sb.table(table).select(cols)
        for k, v in eq.items():
            q = q.eq(k, v)
        page = q.order("id").range(off, off + 999).execute().data
        rows.extend(page)
        if len(page) < 1000:
            return rows
        off += 1000


def to_node(r: dict) -> dict:
    full_text = r.get("full_text")
    title = r.get("title") or ((full_text or "")[:TITLE_CHARS] or None)
    return {
        "kind": "capture",
        "source_table": "inbox",
        "source_id": str(r["id"]),
        "title": title,
        "body": full_text,
        "url": r.get("url"),
        "occurred_at": r.get("source_created_at") or r.get("captured_at"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    ap.add_argument("--source", help="only sync inbox rows with this source")
    ap.add_argument("--folder", help="only sync inbox rows in these folders (comma-separated)")
    args = ap.parse_args()

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    inbox = fetch_all(sb, "inbox",
                      "id,source,folder,title,full_text,url,source_created_at,captured_at,created_at,video_route")
    have = {r["source_id"] for r in fetch_all(sb, "node", "id,source_id", source_table="inbox")}
    inbox_ids = {str(r["id"]) for r in inbox}

    # Social saves wait for watch_videos.py before they become nodes, so the node is
    # created with the transcript already in its body. Triaged-out TikToks never do.
    held_back = [r for r in inbox if held(r) and str(r["id"]) not in have]
    if held_back:
        print(f"{DIM}held back       {len(held_back)} (video pass pending, triaged out, or dead with no text){RESET}")
    missing = sorted((r for r in inbox
                      if str(r["id"]) not in have and not held(r)),
                     key=lambda r: r.get("created_at") or "")
    if args.source:
        missing = [r for r in missing if r.get("source") == args.source]
    if args.folder:
        wanted = {f.strip() for f in args.folder.split(",") if f.strip()}
        missing = [r for r in missing if r.get("folder") in wanted]
    if args.source or args.folder:
        print(f"{DIM}filter          source={args.source or '*'} folder={args.folder or '*'}{RESET}")
    orphans = have - inbox_ids

    by_source = {}
    for r in missing:
        by_source[r.get("source") or "?"] = by_source.get(r.get("source") or "?", 0) + 1

    print(f"inbox rows      {len(inbox)}")
    print(f"capture nodes   {len(have)}")
    print(f"{GREEN}to create{RESET}       {len(missing)}"
          + (f"  {DIM}({', '.join(f'{k} {v}' for k, v in sorted(by_source.items()))}){RESET}"
             if by_source else ""))
    for r in missing[:15]:
        t = (to_node(r)["title"] or "(no text)").replace("\n", " ")[:70]
        print(f"  {DIM}+ {r['created_at'][:10]}  {t}{RESET}")
    if len(missing) > 15:
        print(f"  {DIM}… and {len(missing) - 15} more{RESET}")
    if orphans:
        print(f"{YELLOW}nodes with no inbox row: {len(orphans)} (left alone){RESET}")

    if args.dry_run:
        print(f"\n{YELLOW}Dry run — nothing was written.{RESET}")
        return

    created = 0
    for i in range(0, len(missing), BATCH):
        chunk = [to_node(r) for r in missing[i:i + BATCH]]
        # ignore_duplicates keeps a concurrent run (or a node made elsewhere) from failing this one
        res = (sb.table("node")
               .upsert(chunk, on_conflict="source_table,source_id", ignore_duplicates=True)
               .execute())
        created += len(res.data or [])

    print(f"\n{GREEN}created {created}{RESET}")
    if created:
        print("Run next so the graph catches up:")
        print("  python scripts/tag_captures.py --all")
        print("  python scripts/tag_images.py --all")
        print("  python scripts/embed_nodes.py")


if __name__ == "__main__":
    main()
