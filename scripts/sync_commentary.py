"""
sync_commentary.py
───────────────────
Pushes `commentary` — the takes you write on a capture (Pending/All Captures)
or on a digest item — into the graph as their own nodes, so a thought is
searchable through Tonidexbot as soon as you write it, whether or not it ever
becomes a blog post.

Unlike published_posts, commentary rows are never abandoned-empty by
construction (the admin UI only inserts a row once you've actually typed a
take — see admin.html's saveTake/commentary insert calls), so there's no
placeholder filtering here.

node.title is synthesised from the first line of the take, since commentary
has no title field of its own. node.url is set to the single capture's URL
when the take is about exactly one inbox item (the common case); left null
when it's a digest take clustering several items, since there's no one URL
to point at — the bot's "what's linked" view still finds it by tag/concept
either way.

Editing a take's body clears its embedding and tagged_at (and any
gemini-origin doors/domains/concepts/tags), same as sync_posts.py, so
tag_posts.py --source commentary re-tags it fresh next run instead of
leaving stale tags sitting next to edited content.

Run whenever you write or edit a take:
  python scripts/sync_commentary.py
  python scripts/sync_commentary.py --dry-run
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

MAX_BODY = 2000
TITLE_CHARS = 90

DIM, RESET, GREEN, YELLOW, BLUE = "\033[2m", "\033[0m", "\033[32m", "\033[33m", "\033[34m"


def make_title(body: str) -> str:
    first_line = (body or "").strip().split("\n", 1)[0]
    first_line = " ".join(first_line.split())
    if len(first_line) <= TITLE_CHARS:
        return first_line or "(untitled take)"
    return first_line[:TITLE_CHARS].rsplit(" ", 1)[0] + "…"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    args = ap.parse_args()

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    rows = (sb.table("commentary")
            .select("id,body,inbox_ids,digest_item_id,created_at")
            .execute().data)

    # Only look up a URL when a take is tied to exactly one capture — with several,
    # there's no single thing to link to.
    single_inbox_ids = [r["inbox_ids"][0] for r in rows
                        if r.get("inbox_ids") and len(r["inbox_ids"]) == 1]
    url_by_inbox_id = {}
    if single_inbox_ids:
        for i in range(0, len(single_inbox_ids), 500):
            chunk = single_inbox_ids[i:i + 500]
            page = sb.table("inbox").select("id,url").in_("id", chunk).execute().data
            for r in page:
                if r.get("url"):
                    url_by_inbox_id[r["id"]] = r["url"]

    wanted = {}
    for r in rows:
        body = (r.get("body") or "").strip()
        if not body:
            continue
        sid = r["id"]
        url = None
        if r.get("inbox_ids") and len(r["inbox_ids"]) == 1:
            url = url_by_inbox_id.get(r["inbox_ids"][0])
        wanted[sid] = {
            "title": make_title(body),
            "body": body[:MAX_BODY],
            "url": url,
        }

    existing = {}
    off = 0
    while True:
        page = (sb.table("node").select("id,source_id,title,body,url")
                .eq("source_table", "commentary")
                .order("id").range(off, off + 999)).execute().data
        if not page:
            break
        for r in page:
            existing[r["source_id"]] = r
        off += 1000
        if len(page) < 1000:
            break

    created, updated, retag_flagged, unchanged = [], [], [], 0

    for sid, w in wanted.items():
        cur = existing.get(sid)

        if not cur:
            created.append(sid)
            if not args.dry_run:
                sb.table("node").insert({
                    "kind": "commentary", "source_table": "commentary", "source_id": sid,
                    "title": w["title"], "body": w["body"], "url": w["url"],
                }).execute()
            continue

        node_id = cur["id"]
        changes = {}
        if (cur.get("title") or "") != w["title"]:
            changes["title"] = w["title"]
        if (cur.get("body") or "") != w["body"]:
            changes["body"] = w["body"]
        if (cur.get("url") or None) != w["url"]:
            changes["url"] = w["url"]

        content_changed = "title" in changes or "body" in changes
        if not changes:
            unchanged += 1
            continue

        updated.append((sid, sorted(changes)))
        if not args.dry_run:
            if content_changed:
                changes["embedding"] = None
                changes["embedded_at"] = None
                changes["tagged_at"] = None
                changes["tagged_model"] = None
            sb.table("node").update(changes).eq("id", node_id).execute()
            if content_changed:
                for tbl in ("node_concept", "node_door", "node_domain", "node_tag"):
                    sb.table(tbl).delete().eq("node_id", node_id).eq("origin", "gemini").execute()
        if content_changed:
            retag_flagged.append(sid)

    print(f"{GREEN}created{RESET}   {len(created)}")
    for s in created:
        print(f"  {DIM}+ {s}{RESET}")
    print(f"{GREEN}updated{RESET}   {len(updated)}")
    for s, fields in updated:
        flag = f" {BLUE}[content changed — will re-tag]{RESET}" if s in retag_flagged else ""
        print(f"  {DIM}~ {s}  ({', '.join(fields)}){RESET}{flag}")
    print(f"unchanged {unchanged}")

    if args.dry_run:
        print(f"\n{YELLOW}Dry run — nothing was written.{RESET}")
    elif created or retag_flagged:
        print("\nRun next so the graph catches up:")
        print("  python scripts/tag_posts.py --source commentary --all")
        print("  python scripts/embed_nodes.py")


if __name__ == "__main__":
    main()
