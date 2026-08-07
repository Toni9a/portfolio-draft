"""
seed_from_xarchive.py
─────────────────────
Reads the xarchive JSON export and upserts bookmarks into the Supabase inbox table.
Runs a diff so re-running is safe — only inserts new items, never duplicates.

Usage:
  pip install -r requirements.txt
  cp ../.env.example ../.env  # fill in your keys
  python seed_from_xarchive.py

Options:
  --folder "cool news"   Only seed bookmarks from this folder (can pass multiple times)
  --all                  Seed all bookmarks regardless of folder
  --dry-run              Print what would be inserted without touching Supabase
"""

import os
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# ── Config ─────────────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

# Default: only seed the folders relevant to the pipeline
# Add more here as you create new source folders
DEFAULT_FOLDERS = {"cool news"}

XARCHIVE_PATH = Path(__file__).parent.parent / "data" / "bookmarks"


# ── Helpers ────────────────────────────────────────────────────────────────────

def find_latest_export(path: Path) -> Path:
    exports = sorted(path.glob("xarchive_*.json"), reverse=True)
    if not exports:
        raise FileNotFoundError(f"No xarchive_*.json found in {path}")
    print(f"Using export: {exports[0].name}")
    return exports[0]


def parse_twitter_date(date_str: str) -> str | None:
    """Convert Twitter's date format to ISO 8601."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%a %b %d %H:%M:%S +0000 %Y")
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def tweet_to_inbox_row(tweet: dict) -> dict:
    """Transform a raw xarchive tweet object into an inbox table row."""
    urls = [
        u.get("expanded_url") or u.get("url")
        for u in tweet.get("entities", {}).get("urls", [])
        if u.get("expanded_url") or u.get("url")
    ]

    media_urls = [m["url"] for m in tweet.get("media", []) if m.get("url")]

    author = tweet.get("author", {})
    author_handle = author.get("screen_name")
    author_name = author.get("name")

    # Use first external URL as canonical URL if available, else tweet permalink
    tweet_id = tweet.get("tweet_id", "")
    canonical_url = urls[0] if urls else f"https://x.com/i/web/status/{tweet_id}"

    folders = tweet.get("folders", [])
    folder = folders[0] if folders else None  # primary folder

    return {
        "url": canonical_url,
        "source": "twitter",
        "folder": folder,
        "source_item_id": tweet_id,
        "title": tweet.get("full_text", "")[:280],
        "full_text": tweet.get("full_text"),
        "author_name": author_name,
        "author_handle": author_handle,
        "media_urls": media_urls,
        "status": "new",
        "topic_tags": [],
        "related_item_ids": [],
        "source_created_at": parse_twitter_date(tweet.get("created_at")),
        "raw_data": tweet,
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed Supabase inbox from xarchive export")
    parser.add_argument("--folder", action="append", dest="folders",
                        help="Folder name to include (default: 'cool news'). Pass multiple times.")
    parser.add_argument("--all", action="store_true", dest="all_folders",
                        help="Include all bookmarks regardless of folder")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print rows that would be inserted, don't touch Supabase")
    args = parser.parse_args()

    target_folders = set(args.folders) if args.folders else DEFAULT_FOLDERS
    include_all = args.all_folders

    # Load export
    export_path = find_latest_export(XARCHIVE_PATH)
    with open(export_path) as f:
        data = json.load(f)

    bookmarks = data.get("bookmarks", [])
    print(f"Loaded {len(bookmarks)} bookmarks from export")

    # Filter by folder
    if include_all:
        filtered = bookmarks
        print("Including all bookmarks (--all flag)")
    else:
        filtered = [
            b for b in bookmarks
            if any(folder in target_folders for folder in b.get("folders", []))
        ]
        print(f"Filtered to {len(filtered)} bookmarks in folders: {target_folders}")

    if not filtered:
        print("Nothing to seed. Done.")
        return

    # Transform
    rows = [tweet_to_inbox_row(b) for b in filtered]

    if args.dry_run:
        print(f"\n─── DRY RUN: {len(rows)} rows would be upserted ───")
        for r in rows[:5]:
            print(f"  [{r['folder']}] {r['url'][:80]}")
        if len(rows) > 5:
            print(f"  ... and {len(rows) - 5} more")
        return

    # Upsert to Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # Batch in chunks of 100 to avoid request size limits
    chunk_size = 100
    total_upserted = 0

    for i in range(0, len(rows), chunk_size):
        chunk = rows[i:i + chunk_size]
        result = supabase.table("inbox").upsert(
            chunk,
            on_conflict="url",          # skip duplicates on URL
            ignore_duplicates=True      # don't overwrite existing annotations
        ).execute()
        total_upserted += len(chunk)
        print(f"  Upserted chunk {i // chunk_size + 1}: {len(chunk)} rows")

    print(f"\n✓ Done. {total_upserted} rows upserted into inbox.")
    print(f"  Re-running is safe — duplicates are skipped on URL.")


if __name__ == "__main__":
    main()
