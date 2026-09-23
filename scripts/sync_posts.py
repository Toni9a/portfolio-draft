"""
sync_posts.py
─────────────
Pushes published_posts into the graph — both drafts and published posts, so a
thought is searchable through Tonidexbot as soon as it has real content, not
only once it goes live. Draft nodes get kind='draft' and no url (nothing to
link to yet); published ones get kind='post' and their real /blog/{slug} url.

"Real content" means a non-placeholder title or a non-empty body — this
excludes the empty "New draft" rows the admin editor creates the moment you
click + New draft, before you've typed anything (see CURRENT_STATE.md /
claude/system_atlas.md §7.7 on why those pile up). Nothing is ever deleted
here, including those empty rows — they're just not synced into the graph.

Editing a synced post (title or body changes) clears its embedding AND its
tagged_at, and removes any gemini-origin doors/domains/concepts/tags — so the
next run of tag_posts.py picks it up fresh instead of leaving stale tags from
before the edit sitting alongside new content. topic_tags links are always
fully reconciled (added and removed) to match the post's current topic_tags
column, since blog-link-check may add or drop tags between runs.

Run whenever you start, edit, or publish a post:
  python scripts/sync_posts.py
  python scripts/sync_posts.py --dry-run
"""

import argparse
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

SITE_ORIGIN = os.environ.get("SITE_ORIGIN", "https://toniesan.com")
MAX_BODY = 3000
MIN_BODY_CHARS = 20  # below this, a draft is treated as not-yet-real-content

DIM, RESET, GREEN, YELLOW, BLUE = "\033[2m", "\033[0m", "\033[32m", "\033[33m", "\033[34m"


def slugify(s: str) -> str:
    s = (s or "").lower().replace("&", "and").replace("+", "plus")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")


def flatten(*parts) -> str:
    out = []
    for p in parts:
        if not p:
            continue
        out.append(p if isinstance(p, str) else str(p))
    return " ".join(" ".join(out).split())[:MAX_BODY]


def readable(body_md: str) -> str:
    """The post as a reader sees it, for tagging and embedding.

    The editorial blog (2026-09-23) adds a few markers to body_md:
    [[cutout:id]] / [[image:id]] / [[voice:id]] tokens, "## [LABEL] Heading"
    section labels and ">>" pull quotes. Strip the markup, keep the words.
    """
    text = re.sub(r"\[\[(?:cutout|image|voice):[^\]]+\]\]", " ", body_md or "")
    text = re.sub(r"^\s*##\s*\[[^\]]*\]\s*", "## ", text, flags=re.M)
    text = re.sub(r"^\s*>>\s?", "", text, flags=re.M)
    return text.replace("*", "")


def has_real_content(title: str, body_md: str) -> bool:
    t = (title or "").strip()
    has_title = bool(t) and t.lower() not in ("untitled post", "untitled")
    has_body = len((body_md or "").strip()) >= MIN_BODY_CHARS
    return has_title or has_body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="show changes, write nothing")
    args = ap.parse_args()

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    posts = (sb.table("published_posts")
             .select("id,slug,title,excerpt,body_md,topic_tags,published_at")
             .execute().data)

    wanted = {}  # source_id -> dict
    skipped_empty = 0
    for p in posts:
        title, body_md = p.get("title"), p.get("body_md")
        if not has_real_content(title, body_md):
            skipped_empty += 1
            continue
        sid = p["id"]
        slug = p.get("slug") or slugify(title or sid)
        published = bool(p.get("published_at"))
        wanted[sid] = {
            "kind": "post" if published else "draft",
            "title": (title or "Untitled post").replace("*", ""),
            "body": flatten(p.get("excerpt"), readable(body_md)),
            "url": f"{SITE_ORIGIN}/blog/{slug}" if published else None,
            "topic_tags": [t for t in (p.get("topic_tags") or []) if t],
        }

    existing = {}
    off = 0
    while True:
        page = (sb.table("node").select("id,source_id,kind,title,body,url")
                .eq("source_table", "published_posts")
                .order("id").range(off, off + 999)).execute().data
        if not page:
            break
        for r in page:
            existing[r["source_id"]] = r
        off += 1000
        if len(page) < 1000:
            break

    created, updated, retag_flagged, unchanged, tag_links = [], [], [], 0, 0

    for sid, w in wanted.items():
        cur = existing.get(sid)
        node_id = None

        if not cur:
            created.append((sid, w["kind"]))
            if not args.dry_run:
                row = sb.table("node").insert({
                    "kind": w["kind"], "source_table": "published_posts", "source_id": sid,
                    "title": w["title"], "body": w["body"] or None, "url": w["url"],
                }).execute().data
                node_id = row[0]["id"]
        else:
            node_id = cur["id"]
            changes = {}
            if (cur.get("kind") or "") != w["kind"]:
                changes["kind"] = w["kind"]
            if (cur.get("title") or "") != w["title"]:
                changes["title"] = w["title"]
            if (cur.get("body") or "") != (w["body"] or ""):
                changes["body"] = w["body"] or None
            if (cur.get("url") or None) != w["url"]:
                changes["url"] = w["url"]

            content_changed = "title" in changes or "body" in changes
            if not changes:
                unchanged += 1
            else:
                updated.append((sid, sorted(changes)))
                if not args.dry_run:
                    if content_changed:
                        changes["embedding"] = None
                        changes["embedded_at"] = None
                        changes["tagged_at"] = None
                        changes["tagged_model"] = None
                    sb.table("node").update(changes).eq("id", node_id).execute()
                    if content_changed:
                        for tbl, col in [("node_concept", "concept_id"), ("node_door", "door_id"),
                                          ("node_domain", "domain_id"), ("node_tag", "tag_id")]:
                            sb.table(tbl).delete().eq("node_id", node_id).eq("origin", "gemini").execute()
                if content_changed:
                    retag_flagged.append(sid)

        # Fully reconcile topic_tags links (add missing, drop ones no longer on the post) —
        # blog-link-check can both add and remove tags between runs.
        if node_id and not args.dry_run:
            want_slugs = {slugify(t): t for t in w["topic_tags"] if slugify(t)}
            have = (sb.table("node_tag").select("tag_id,tag:tag_id(slug)")
                    .eq("node_id", node_id).eq("origin", "topic_tags").execute().data)
            have_slugs = {row["tag"]["slug"]: row["tag_id"] for row in have if row.get("tag")}

            for slug in have_slugs.keys() - want_slugs.keys():
                sb.table("node_tag").delete().eq("node_id", node_id) \
                    .eq("tag_id", have_slugs[slug]).eq("origin", "topic_tags").execute()

            for slug, label in want_slugs.items():
                if slug in have_slugs:
                    continue
                tag_row = sb.table("tag").upsert({"slug": slug, "label": label},
                                                  on_conflict="slug").execute().data
                if tag_row:
                    sb.table("node_tag").upsert(
                        {"node_id": node_id, "tag_id": tag_row[0]["id"], "origin": "topic_tags"}
                    ).execute()
                    tag_links += 1

    orphans = [s for s in existing if s not in wanted]

    print(f"{GREEN}created{RESET}   {len(created)}")
    for s, k in created:
        print(f"  {DIM}+ {s}  ({k}){RESET}")
    print(f"{GREEN}updated{RESET}   {len(updated)}")
    for s, fields in updated:
        flag = f" {BLUE}[content changed — will re-tag]{RESET}" if s in retag_flagged else ""
        print(f"  {DIM}~ {s}  ({', '.join(fields)}){RESET}{flag}")
    print(f"unchanged {unchanged}")
    print(f"topic_tags links added/removed this run: {tag_links}")
    print(f"{DIM}skipped (no real content yet): {skipped_empty}{RESET}")
    if orphans:
        print(f"{YELLOW}in the graph but no longer has content: {len(orphans)}{RESET}")
        for s in orphans:
            print(f"  {DIM}? {s}{RESET}")
        print(f"{DIM}  left alone on purpose — content being cleared doesn't delete its node.{RESET}")

    if args.dry_run:
        print(f"\n{YELLOW}Dry run — nothing was written.{RESET}")
    elif created or retag_flagged:
        print("\nRun next so the graph catches up:")
        print("  python scripts/tag_posts.py --all")
        print("  python scripts/embed_nodes.py")


if __name__ == "__main__":
    main()
