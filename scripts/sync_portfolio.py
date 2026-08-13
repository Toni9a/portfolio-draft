"""
sync_portfolio.py
─────────────────
Pushes toni_esan_portfolio_unfin.json into the graph.

For every project, role and qualification in the JSON it creates or updates the
matching `node`, including the full descriptive text. That text is what gets
embedded, so a project with only a title embeds badly and a project with its
description, contributions and metrics embeds well.

If the text of a node changes, its embedding is cleared so the next run of
embed_nodes.py picks it up. Nothing else is touched — doors, domains, concepts
and edges are left exactly as they are.

Run this whenever you edit the JSON:
  python scripts/sync_portfolio.py
  python scripts/sync_portfolio.py --dry-run
"""

import argparse
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

JSON_PATH = ROOT / "toni_esan_portfolio_unfin.json"
MAX_BODY = 3000

DIM, RESET, GREEN, YELLOW = "\033[2m", "\033[0m", "\033[32m", "\033[33m"


def slugify(s: str) -> str:
    # "&" becomes "and" to match the ids already in the graph. Without this,
    # "Social & E-commerce" would slug differently and create a duplicate node.
    s = (s or "").lower().replace("&", "and").replace("+", "plus")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def flatten(*parts) -> str:
    """Everything worth embedding about one entry, as one block of text."""
    out = []
    for p in parts:
        if not p:
            continue
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, (list, tuple)):
            out.extend(str(x) for x in p if x)
        elif isinstance(p, dict):
            out.extend(str(v) for v in p.values() if isinstance(v, (str, int, float)))
        else:
            out.append(str(p))
    return " ".join(" ".join(out).split())[:MAX_BODY]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    args = ap.parse_args()

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    data = json.loads(JSON_PATH.read_text())

    wanted = {}   # source_id -> (kind, title, body, url)

    for p in data.get("projects", []):
        wanted[p["id"]] = (
            "project",
            p.get("title") or p["id"],
            flatten(p.get("short_description"), p.get("long_description"),
                    p.get("key_contributions"), p.get("metrics"),
                    p.get("learnings"), p.get("tech_tags")),
            p.get("live_url") or p.get("github_repo_url"),
        )

    for e in data.get("experience", []):
        org = e.get("company") or e.get("organisation") or ""
        sid = f"{slugify(org)}-{slugify((e.get('period') or '')[:9])}"
        wanted[sid] = (
            "role",
            f"{e.get('role','')} — {org}".strip(" —"),
            flatten(e.get("role"), org, e.get("location"), e.get("period"),
                    e.get("summary"), e.get("highlights"), e.get("key_contributions")),
            None,
        )

    for e in data.get("education", []):
        inst = e.get("institution") or ""
        qual = e.get("qualification") or e.get("degree") or ""
        sid = slugify(f"{inst}-{qual}")
        wanted[sid] = (
            "education",
            f"{qual} — {inst}".strip(" —"),
            flatten(qual, inst, e.get("grade"), e.get("graduation"),
                    e.get("highlights"), e.get("modules")),
            None,
        )

    # Ventures are prefixed because a venture and a project can share a name,
    # e.g. Cornerstore is both, and source_id has to stay unique.
    for v in data.get("ventures", []):
        wanted["venture-" + v["id"]] = ("venture", v.get("label") or v["id"],
                                        flatten(v.get("label"), v.get("projects")), None)

    existing = {}
    off = 0
    while True:
        page = (sb.table("node").select("id,source_id,kind,title,body,url")
                .eq("source_table", "portfolio_json")
                .order("id").range(off, off + 999)).execute().data
        if not page:
            break
        for r in page:
            existing[r["source_id"]] = r
        off += 1000
        if len(page) < 1000:
            break

    created, updated, unchanged = [], [], 0

    for sid, (kind, title, body, url) in wanted.items():
        cur = existing.get(sid)
        if not cur:
            created.append(sid)
            if not args.dry_run:
                sb.table("node").insert({
                    "kind": kind, "source_table": "portfolio_json", "source_id": sid,
                    "title": title, "body": body or None, "url": url,
                }).execute()
            continue

        changes = {}
        if (cur.get("title") or "") != title:
            changes["title"] = title
        if (cur.get("body") or "") != (body or ""):
            changes["body"] = body or None
        if (cur.get("url") or None) != url:
            changes["url"] = url

        if not changes:
            unchanged += 1
            continue

        updated.append((sid, sorted(changes)))
        if not args.dry_run:
            # Text changed, so the old vector no longer describes it.
            if "body" in changes or "title" in changes:
                changes["embedding"] = None
                changes["embedded_at"] = None
            sb.table("node").update(changes).eq("id", cur["id"]).execute()

    orphans = [s for s in existing if s not in wanted]

    print(f"{GREEN}created{RESET}   {len(created)}")
    for s in created:
        print(f"  {DIM}+ {s}{RESET}")
    print(f"{GREEN}updated{RESET}   {len(updated)}")
    for s, fields in updated:
        print(f"  {DIM}~ {s}  ({', '.join(fields)}){RESET}")
    print(f"unchanged {unchanged}")
    if orphans:
        print(f"{YELLOW}in the graph but no longer in the JSON: {len(orphans)}{RESET}")
        for s in orphans:
            print(f"  {DIM}? {s}{RESET}")
        print(f"{DIM}  left alone on purpose. Delete them by hand if you meant to remove them.{RESET}")

    if args.dry_run:
        print(f"\n{YELLOW}Dry run — nothing was written.{RESET}")
    elif updated or created:
        print("\nRun this next so the changed rows get a fresh embedding:")
        print("  python scripts/embed_nodes.py")


if __name__ == "__main__":
    main()
