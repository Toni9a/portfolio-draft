"""
tag_captures.py
───────────────
Tags captured items (bookmarks, links, voice notes, thoughts) against your own
concept list, and assigns doors and domains.

What it does NOT do:
  - it never touches inbox.folder, and never removes a folder tag
  - it never creates an edge, so a bookmark never becomes part of a project
  - it never invents a concept. Anything the model returns that is not in your
    concept table is stored as a freeform entity tag instead, so you can look at
    it later and decide whether it deserves to be a concept.

Usage
  python scripts/tag_captures.py --folder "cool news" --limit 20   # try a batch
  python scripts/tag_captures.py --folder "cool news"              # that folder
  python scripts/tag_captures.py --folders-like "ml qz,papers,code,robotics"
  python scripts/tag_captures.py --all                             # everything

Re-running is safe. Rows already tagged are skipped unless you pass --retag.
Watch it live in the admin Tagging tab while this runs.

Needs the current SDK, not the retired one the other scripts use:
    pip install google-genai
"""

import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

# One place to change the model.
MODEL = os.environ.get("GEMINI_TAGGING_MODEL", "gemini-3.5-flash-lite")

BATCH = 20
MAX_ITEM_CHARS = 900

DIM, RESET, BOLD = "\033[2m", "\033[0m", "\033[1m"
GREEN, YELLOW, RED, BLUE = "\033[32m", "\033[33m", "\033[31m", "\033[34m"


# ── prompt ────────────────────────────────────────────────────────────────────

PROMPT = """You are tagging saved items from someone's personal knowledge base.
He is an applied AI and computer vision engineer who also builds web software,
hardware and creative tools.

Tag each item using ONLY the vocabulary below. Do not invent doors or domains.

DOORS (pick 0 to 2, only if clearly right):
{doors}

DOMAINS (pick 0 to 2, only if clearly right):
{domains}

CONCEPTS (pick 0 to 5, only ones that genuinely apply):
{concepts}

Also give up to 3 "entities": specific named things in the item that are NOT in
the concept list, e.g. a product name, a company, a paper, a technique. Lowercase,
hyphenated, specific. Not category words like "design" or "ai".

Rules:
  - Tag the SUBJECT of the item, not just its technology. A post about AI taking
    London jobs is about ai-and-jobs and london-tech-scene, even though it names
    no tool. A post about a marketing trend is about marketing-and-branding.
    Industry, economy, policy and society count as subject matter.
  - Return empty lists ONLY when there is genuinely nothing to tag, e.g. a bare
    link with no text, a one word reaction, or a joke with no topic. Empty is a
    correct answer for those and only those.
  - Do not stretch to a tag that is merely adjacent. Wrong is worse than empty.

Return ONLY a JSON array, one object per item, in the same order, like:
[{{"i": 0, "doors": [], "domains": [], "concepts": [], "entities": []}}]

ITEMS:
{items}"""


# ── helpers ───────────────────────────────────────────────────────────────────

def slugify(s: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:60]


def item_text(row: dict) -> str:
    bits = [row.get("title") or "", row.get("body") or ""]
    text = "\n".join(b for b in bits if b).strip()
    return text[:MAX_ITEM_CHARS] if text else (row.get("url") or "")


def parse_json(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end < 0:
        raise ValueError("no JSON array in the reply")
    return json.loads(raw[start:end + 1])


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", help="one folder, exactly as it appears in inbox")
    ap.add_argument("--folders-like", help="comma separated list of folders")
    ap.add_argument("--all", action="store_true", help="every untagged capture")
    ap.add_argument("--limit", type=int, help="stop after this many items")
    ap.add_argument("--retag", action="store_true", help="include already tagged rows")
    ap.add_argument("--empty-only", action="store_true",
                    help="only revisit rows that came back with nothing last time")
    ap.add_argument("--dry-run", action="store_true", help="show tags, write nothing")
    args = ap.parse_args()

    if not (args.folder or args.folders_like or args.all):
        ap.error("pick one of --folder, --folders-like or --all")

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
    )

    doors = sb.table("door").select("id,label,family").order("sort").execute().data
    domains = sb.table("domain").select("id,label").order("label").execute().data
    concepts = sb.table("concept").select("id,slug,label,door_id").execute().data
    concept_by_slug = {c["slug"]: c for c in concepts}
    door_ids = {d["id"] for d in doors}
    domain_ids = {d["id"] for d in domains}

    doors_txt = "\n".join(f"  {d['id']} — {d['label']}" for d in doors if d["id"] != "cross_door")
    domains_txt = "\n".join(f"  {d['id']}" for d in domains)
    concepts_txt = ", ".join(sorted(concept_by_slug))

    # Which captures are we doing? Folder lives on inbox, so pick ids there first.
    # Matched case-insensitively, because "papers" and "Papers" are the same folder
    # to a human and silently different to Postgres.
    inbox_rows, off = [], 0
    while True:
        page = sb.table("inbox").select("id,folder").order("id").range(off, off + 999).execute().data
        if not page:
            break
        inbox_rows += page
        off += 1000
        if len(page) < 1000:
            break

    if args.all:
        wanted = {str(r["id"]) for r in inbox_rows}
    else:
        names = [args.folder] if args.folder else args.folders_like.split(",")
        names = {n.strip().lower() for n in names if n.strip()}
        wanted = {str(r["id"]) for r in inbox_rows
                  if (r.get("folder") or "").lower() in names}
        found = {(r.get("folder") or "") for r in inbox_rows
                 if (r.get("folder") or "").lower() in names}
        missing = names - {f.lower() for f in found}
        if missing:
            print(f"{YELLOW}No folder called: {', '.join(sorted(missing))}{RESET}")
        if found:
            print(f"{DIM}Folders matched: {', '.join(sorted(found))}{RESET}")

    if not wanted:
        print("No inbox rows matched that folder.")
        return

    # Rows that got nothing last time, so --empty-only can revisit just those.
    empty_ids = set()
    if args.empty_only:
        seen = 0
        while True:
            page = (sb.table("node_full")
                    .select("id,doors,concepts,domains,tags")
                    .eq("kind", "capture").not_.is_("tagged_at", "null")
                    .order("id").range(seen, seen + 999)).execute().data
            if not page:
                break
            for r in page:
                entities = [t for t in (r.get("tags") or []) if not t.startswith("folder-")]
                if not (r.get("doors") or r.get("concepts") or r.get("domains") or entities):
                    empty_ids.add(r["id"])
            seen += 1000
            if len(page) < 1000:
                break

    rows, seen = [], 0
    while True:
        q = (sb.table("node")
             .select("id,title,body,url,source_id,tagged_at")
             .eq("source_table", "inbox")
             .order("id").range(seen, seen + 999))
        page = q.execute().data
        if not page:
            break
        for r in page:
            if r["source_id"] not in wanted:
                continue
            if args.empty_only:
                if r["id"] not in empty_ids:
                    continue
            elif r.get("tagged_at") and not args.retag:
                continue
            rows.append(r)
        seen += 1000
        if len(page) < 1000:
            break

    if args.limit:
        rows = rows[:args.limit]
    if not rows:
        print("Nothing left to tag there. Use --retag to go over them again.")
        return

    print(f"{BOLD}Tagging {len(rows)} captures with {MODEL}{RESET}")
    print(f"{DIM}Folders are never changed. Watch the admin Tagging tab as this runs.{RESET}\n")

    stats = {"tagged": 0, "empty": 0, "failed": 0, "concepts": 0, "entities": 0}

    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        listing = "\n\n".join(
            f"[{i}] {item_text(r)}" for i, r in enumerate(batch)
        )
        prompt = PROMPT.format(doors=doors_txt, domains=domains_txt,
                               concepts=concepts_txt, items=listing)

        try:
            reply = client.models.generate_content(model=MODEL, contents=prompt, config=cfg)
            results = parse_json(reply.text)
        except Exception as e:
            stats["failed"] += len(batch)
            print(f"{RED}batch {start // BATCH + 1} failed: {e}{RESET}")
            time.sleep(3)
            continue

        by_index = {r.get("i"): r for r in results if isinstance(r, dict)}

        for i, row in enumerate(batch):
            res = by_index.get(i, {})
            picked_doors = [d for d in res.get("doors", []) if d in door_ids][:2]
            picked_doms = [d for d in res.get("domains", []) if d in domain_ids][:2]
            good, unknown = [], []
            for c in res.get("concepts", [])[:5]:
                (good if c in concept_by_slug else unknown).append(c)
            entities = [slugify(e) for e in res.get("entities", [])[:3] if e]
            entities = [e for e in entities if e] + [slugify(u) for u in unknown]

            # Show enough of the item to actually judge the tags. On a dry run
            # show the lot, since reading it is the whole point of a dry run.
            full = " ".join((row.get("title") or "").split())
            label = full if args.dry_run else full[:110]
            if len(full) > len(label):
                label += "…"
            link = row.get("url") or ""

            if not (picked_doors or picked_doms or good or entities):
                stats["empty"] += 1
                print(f"  {DIM}{label}{RESET}")
                print(f"      {DIM}nothing — left untagged{RESET}")
            else:
                shown = " ".join(
                    [f"{BLUE}{d}{RESET}" for d in picked_doors]
                    + [f"{GREEN}{c}{RESET}" for c in good]
                    + [f"{YELLOW}{e}{RESET}" for e in entities])
                print(f"  {label}")
                print(f"      {shown}")
                stats["tagged"] += 1
                stats["concepts"] += len(good)
                stats["entities"] += len(entities)
            if link:
                print(f"      {DIM}{link}{RESET}")
            print()

            if args.dry_run:
                continue

            nid = row["id"]
            if picked_doors:
                sb.table("node_door").upsert(
                    [{"node_id": nid, "door_id": d, "origin": "gemini"} for d in picked_doors]
                ).execute()
            if picked_doms:
                sb.table("node_domain").upsert(
                    [{"node_id": nid, "domain_id": d, "origin": "gemini"} for d in picked_doms]
                ).execute()
            if good:
                sb.table("node_concept").upsert(
                    [{"node_id": nid, "concept_id": concept_by_slug[c]["id"],
                      "origin": "gemini"} for c in good]
                ).execute()
            for e in entities:
                tag = sb.table("tag").upsert({"slug": e, "label": e.replace("-", " ")},
                                             on_conflict="slug").execute().data
                if tag:
                    sb.table("node_tag").upsert(
                        {"node_id": nid, "tag_id": tag[0]["id"], "origin": "gemini"}
                    ).execute()
            sb.table("node").update({"tagged_at": "now()", "tagged_model": MODEL}) \
                .eq("id", nid).execute()

        done = min(start + BATCH, len(rows))
        print(f"{DIM}  ── {done}/{len(rows)}{RESET}\n")
        time.sleep(0.4)

    print(f"\n{BOLD}Done.{RESET} {stats['tagged']} tagged, {stats['empty']} left empty, "
          f"{stats['failed']} failed. {stats['concepts']} concepts, {stats['entities']} new entities.")
    if args.dry_run:
        print(f"{YELLOW}Dry run — nothing was written.{RESET}")


if __name__ == "__main__":
    main()
