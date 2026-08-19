"""
tag_images.py
─────────────
Tags captures by looking at their attached image, not just their text.

This is the pass that covers the visual folders. A bookmark saved purely for a
screenshot has almost no text, so tag_captures.py correctly left it empty. This
one sends the actual picture.

Uses gemini-3.7-flash, which takes image input natively.

What it does NOT do:
  - it never touches inbox.folder or media_urls
  - it never creates an edge, so a bookmark never becomes part of a project
  - it never overwrites what tag_captures.py already found. It only adds.
  - it never invents a concept. Unknown ones become freeform entity tags.

Usage
  python scripts/tag_images.py --limit 1 --dry-run          # look at one first
  python scripts/tag_images.py --folder "MJ aesthetic" --limit 10 --dry-run
  python scripts/tag_images.py --folder "MJ aesthetic"
  python scripts/tag_images.py --all

Re-running skips anything already image-tagged unless you pass --retag.

Needs:  pip install google-genai httpx
"""

import argparse
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

MODEL = os.environ.get("GEMINI_VISION_MODEL", "gemini-3.7-flash")

IMAGES_PER_ITEM = 1        # first image only, to keep the bill down
MAX_TEXT_CHARS = 600
MAX_IMAGE_BYTES = 8_000_000
FETCH_TIMEOUT = 20

DIM, RESET, BOLD = "\033[2m", "\033[0m", "\033[1m"
GREEN, YELLOW, RED, BLUE = "\033[32m", "\033[33m", "\033[31m", "\033[34m"

MIME = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
        "gif": "image/gif", "webp": "image/webp"}


PROMPT = """Look at this image and tag what it actually shows.

It was saved as a bookmark by an applied AI and computer vision engineer who also
builds web software, hardware and creative tools. The text saved with it is below,
and is often useless on its own, which is why you are being shown the picture.

Tag using ONLY this vocabulary. Do not invent doors or domains.

DOORS (0 to 2, only if clearly right):
{doors}

DOMAINS (0 to 2, only if clearly right):
{domains}

CONCEPTS (0 to 5, only ones that genuinely apply):
{concepts}

Also give up to 4 "entities": specific things visible in the image that are not in
the concept list. For a screenshot of an interface, name the pattern or the product,
e.g. bento-grid, command-palette, figma. For a photograph or artwork, name the style
or subject, e.g. brutalist-architecture, long-exposure, double-exposure-portrait.
Lowercase and hyphenated. Not vague words like "design" or "cool".

Describe what is there, not what it might relate to. If the image is a plain
screenshot of text, tag the subject of the text. If it is a meme or a photo with no
subject worth filing, return empty lists.

Saved text: {text}

Return ONLY a JSON object:
{{"doors": [], "domains": [], "concepts": [], "entities": [], "caption": "one short factual sentence"}}"""


def slugify(s: str) -> str:
    out = "".join(c if c.isalnum() else "-" for c in (s or "").lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out[:60]


def mime_for(url: str) -> str:
    stem = url.split("?")[0].rsplit(".", 1)
    return MIME.get(stem[-1].lower() if len(stem) > 1 else "", "image/jpeg")


def parse_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < 0:
        raise ValueError("no JSON object in the reply")
    return json.loads(raw[a:b + 1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder")
    ap.add_argument("--folders-like")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--retag", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not (args.folder or args.folders_like or args.all):
        ap.error("pick one of --folder, --folders-like or --all")

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(
        temperature=0,
        response_mime_type="application/json",
        # Low, because naming what is in a picture is not a reasoning problem.
        # "minimal" is rejected by this model.
        thinking_config=types.ThinkingConfig(thinking_level="low"),
    )

    doors = sb.table("door").select("id,label").order("sort").execute().data
    domains = sb.table("domain").select("id,label").order("label").execute().data
    concepts = sb.table("concept").select("id,slug").execute().data
    concept_by_slug = {c["slug"]: c for c in concepts}
    door_ids = {d["id"] for d in doors}
    domain_ids = {d["id"] for d in domains}

    doors_txt = "\n".join(f"  {d['id']} — {d['label']}" for d in doors if d["id"] != "cross_door")
    domains_txt = "\n".join(f"  {d['id']}" for d in domains)
    concepts_txt = ", ".join(sorted(concept_by_slug))

    # Pull inbox rows that actually have an image.
    inbox_rows, off = [], 0
    while True:
        page = (sb.table("inbox").select("id,folder,media_urls,full_text")
                .order("id").range(off, off + 999)).execute().data
        if not page:
            break
        inbox_rows += page
        off += 1000
        if len(page) < 1000:
            break

    if args.all:
        chosen = inbox_rows
    else:
        names = [args.folder] if args.folder else args.folders_like.split(",")
        names = {n.strip().lower() for n in names if n.strip()}
        chosen = [r for r in inbox_rows if (r.get("folder") or "").lower() in names]
        found = {(r.get("folder") or "") for r in chosen}
        missing = names - {f.lower() for f in found}
        if missing:
            print(f"{YELLOW}No folder called: {', '.join(sorted(missing))}{RESET}")
        if found:
            print(f"{DIM}Folders matched: {', '.join(sorted(found))}{RESET}")

    by_source = {str(r["id"]): r for r in chosen if (r.get("media_urls") or [])}
    if not by_source:
        print("Nothing there has an image attached.")
        return

    nodes, off = [], 0
    while True:
        page = (sb.table("node").select("id,source_id,title,image_tagged_at")
                .eq("source_table", "inbox").eq("kind", "capture")
                .order("id").range(off, off + 999)).execute().data
        if not page:
            break
        for r in page:
            if r["source_id"] not in by_source:
                continue
            if r.get("image_tagged_at") and not args.retag:
                continue
            nodes.append(r)
        off += 1000
        if len(page) < 1000:
            break

    if args.limit:
        nodes = nodes[:args.limit]
    if not nodes:
        print("Nothing left to do. Use --retag to go over them again.")
        return

    print(f"{BOLD}Looking at {len(nodes)} images with {MODEL}{RESET}")
    print(f"{DIM}Folders and existing tags are never removed. This only adds.{RESET}\n")

    stats = {"tagged": 0, "empty": 0, "failed": 0, "unfetchable": 0}
    http = httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0"})

    for n, node in enumerate(nodes, 1):
        src = by_source[node["source_id"]]
        urls = (src.get("media_urls") or [])[:IMAGES_PER_ITEM]
        text = " ".join((src.get("full_text") or "").split())[:MAX_TEXT_CHARS]

        parts = []
        for u in urls:
            try:
                r = http.get(u)
                r.raise_for_status()
                if len(r.content) > MAX_IMAGE_BYTES:
                    raise ValueError(f"{len(r.content)} bytes is too big")
                parts.append(types.Part.from_bytes(data=r.content, mime_type=mime_for(u)))
            except Exception as e:
                print(f"  {RED}could not fetch image: {e}{RESET}")

        if not parts:
            stats["unfetchable"] += 1
            if not args.dry_run:
                sb.table("node").update({"image_tagged_at": "now()",
                                         "image_tagged_model": "unfetchable"}) \
                    .eq("id", node["id"]).execute()
            continue

        prompt = PROMPT.format(doors=doors_txt, domains=domains_txt,
                               concepts=concepts_txt, text=text or "(none)")
        try:
            reply = client.models.generate_content(
                model=MODEL, contents=parts + [prompt], config=cfg)
            res = parse_json(reply.text)
        except Exception as e:
            stats["failed"] += 1
            print(f"  {RED}{n}. failed: {e}{RESET}")
            time.sleep(2)
            continue

        picked_doors = [d for d in res.get("doors", []) if d in door_ids][:2]
        picked_doms = [d for d in res.get("domains", []) if d in domain_ids][:2]
        good, unknown = [], []
        for c in res.get("concepts", [])[:5]:
            (good if c in concept_by_slug else unknown).append(c)
        entities = [slugify(e) for e in res.get("entities", [])[:4] if e]
        entities = [e for e in entities if e] + [slugify(u) for u in unknown]
        caption = " ".join((res.get("caption") or "").split())[:200]

        label = " ".join((node.get("title") or "").split())[:70] or "(no text)"
        print(f"  {DIM}{n}/{len(nodes)}{RESET} {label}")
        if caption:
            print(f"      {DIM}sees: {caption}{RESET}")
        if not (picked_doors or picked_doms or good or entities):
            stats["empty"] += 1
            print(f"      {DIM}nothing worth tagging{RESET}")
        else:
            stats["tagged"] += 1
            print("      " + " ".join(
                [f"{BLUE}{d}{RESET}" for d in picked_doors]
                + [f"{GREEN}{c}{RESET}" for c in good]
                + [f"{YELLOW}{e}{RESET}" for e in entities]))
        print(f"      {DIM}{urls[0]}{RESET}\n")

        if args.dry_run:
            continue

        nid = node["id"]
        if picked_doors:
            sb.table("node_door").upsert(
                [{"node_id": nid, "door_id": d, "origin": "gemini-image"} for d in picked_doors]
            ).execute()
        if picked_doms:
            sb.table("node_domain").upsert(
                [{"node_id": nid, "domain_id": d, "origin": "gemini-image"} for d in picked_doms]
            ).execute()
        if good:
            sb.table("node_concept").upsert(
                [{"node_id": nid, "concept_id": concept_by_slug[c]["id"],
                  "origin": "gemini-image"} for c in good]
            ).execute()
        for e in entities:
            tag = sb.table("tag").upsert({"slug": e, "label": e.replace("-", " ")},
                                         on_conflict="slug").execute().data
            if tag:
                sb.table("node_tag").upsert(
                    {"node_id": nid, "tag_id": tag[0]["id"], "origin": "gemini-image"}
                ).execute()
        sb.table("node").update({"image_tagged_at": "now()", "image_tagged_model": MODEL}) \
            .eq("id", nid).execute()
        time.sleep(0.15)

    print(f"\n{BOLD}Done.{RESET} {stats['tagged']} tagged, {stats['empty']} nothing to tag, "
          f"{stats['unfetchable']} images would not load, {stats['failed']} failed.")
    if args.dry_run:
        print(f"{YELLOW}Dry run — nothing was written.{RESET}")


if __name__ == "__main__":
    main()
