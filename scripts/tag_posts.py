"""
tag_posts.py
────────────
Gemini tagging pass for your own writing — blog posts/drafts AND commentary
(the takes you write on a capture or a digest item) — same job as
tag_captures.py does for inbox captures: assigns doors, domains and curated
concepts from your existing vocabulary, plus freeform entity tags for
anything specific that isn't in that vocabulary yet.

Run sync_posts.py or sync_commentary.py first so the nodes exist. This only
tags nodes that are already in the graph, filtered by --source.

What it does NOT do:
  - it never touches published_posts.topic_tags (sync_posts.py already turns
    those into node_tag links, reconciled each run — this pass only adds
    doors/domains/curated concepts on top)
  - it never populates related_project_ids — that's a separate, bigger piece
    of work (matching post content against the project graph) and is not in
    scope here. See claude/system_atlas.md §6.

Usage
  python scripts/tag_posts.py --all                          # published_posts, default
  python scripts/tag_posts.py --source commentary --all
  python scripts/tag_posts.py --limit 5
  python scripts/tag_posts.py --retag            # include already-tagged rows
  python scripts/tag_posts.py --dry-run

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

MODEL = os.environ.get("GEMINI_TAGGING_MODEL", "gemini-3.7-flash")

BATCH = 20
MAX_ITEM_CHARS = 1400  # posts run longer than captures, give the model more to read

DIM, RESET, BOLD = "\033[2m", "\033[0m", "\033[1m"
GREEN, YELLOW, RED, BLUE = "\033[32m", "\033[33m", "\033[31m", "\033[34m"


PROMPT = """You are tagging writing by an applied AI and computer vision
engineer who also builds web software, hardware and creative tools. These are
his own words — blog posts, drafts, or short dictated takes on something he
saved — not saved bookmarks written by someone else.

Tag each item using ONLY the vocabulary below. Do not invent doors or domains.

DOORS (pick 0 to 2, only if clearly right):
{doors}

DOMAINS (pick 0 to 2, only if clearly right):
{domains}

CONCEPTS (pick 0 to 5, only ones that genuinely apply):
{concepts}

Also give up to 3 "entities": specific named things in the post that are NOT
in the concept list, e.g. a product name, a company, a paper, a technique.
Lowercase, hyphenated, specific. Not category words like "design" or "ai".

Rules:
  - Tag the SUBJECT of the post, not just its technology.
  - Return empty lists ONLY when there is genuinely nothing to tag. Wrong is
    worse than empty.

Return ONLY a JSON array, one object per item, in the same order, like:
[{{"i": 0, "doors": [], "domains": [], "concepts": [], "entities": []}}]

ITEMS:
{items}"""


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="every untagged node for --source")
    ap.add_argument("--source", default="published_posts",
                     choices=["published_posts", "commentary"],
                     help="which source_table to tag (default: published_posts)")
    ap.add_argument("--limit", type=int, help="stop after this many items")
    ap.add_argument("--retag", action="store_true", help="include already tagged rows")
    ap.add_argument("--dry-run", action="store_true", help="show tags, write nothing")
    args = ap.parse_args()

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(temperature=0, response_mime_type="application/json")

    doors = sb.table("door").select("id,label,family").order("sort").execute().data
    domains = sb.table("domain").select("id,label").order("label").execute().data
    concepts = sb.table("concept").select("id,slug,label,door_id").execute().data
    concept_by_slug = {c["slug"]: c for c in concepts}
    door_ids = {d["id"] for d in doors}
    domain_ids = {d["id"] for d in domains}

    doors_txt = "\n".join(f"  {d['id']} — {d['label']}" for d in doors if d["id"] != "cross_door")
    domains_txt = "\n".join(f"  {d['id']}" for d in domains)
    concepts_txt = ", ".join(sorted(concept_by_slug))

    rows, seen = [], 0
    while True:
        page = (sb.table("node")
                .select("id,title,body,url,source_id,tagged_at")
                .eq("source_table", args.source)
                .order("id").range(seen, seen + 999)).execute().data
        if not page:
            break
        for r in page:
            if r.get("tagged_at") and not args.retag:
                continue
            rows.append(r)
        seen += 1000
        if len(page) < 1000:
            break

    if args.limit:
        rows = rows[:args.limit]
    sync_hint = "sync_posts.py" if args.source == "published_posts" else "sync_commentary.py"
    if not rows:
        print(f"Nothing left to tag in {args.source}. Run {sync_hint} first if you just added "
              "something, or use --retag to go over it again.")
        return

    print(f"{BOLD}Tagging {len(rows)} {args.source} nodes with {MODEL}{RESET}\n")

    stats = {"tagged": 0, "empty": 0, "failed": 0, "concepts": 0, "entities": 0}

    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        listing = "\n\n".join(f"[{i}] {item_text(r)}" for i, r in enumerate(batch))
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
