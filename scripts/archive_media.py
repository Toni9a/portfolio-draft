"""
archive_media.py
────────────────
Downloads every image attached to a capture and puts it in Cloudflare R2, so you
own your pictures instead of pointing at Twitter's servers.

Nothing is destroyed. `media_urls` keeps the original source links untouched.
`stored_media` gains the R2 object keys alongside it.

Object keys are stored, not URLs, because a presigned URL expires. The admin asks
for a fresh one when it needs to show something.

Usage
  python scripts/archive_media.py --limit 5 --dry-run   # see what it would do
  python scripts/archive_media.py --limit 20            # try a small batch
  python scripts/archive_media.py                       # everything left
  python scripts/archive_media.py --folder "MJ aesthetic"
  python scripts/archive_media.py --url <key>           # print a link to one file

Re-running skips anything already archived. Safe to stop and restart.

Needs:  pip install boto3 httpx
Needs in .env:
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
"""

import argparse
import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from supabase import create_client, Client

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
except ImportError:
    sys.exit("boto3 is missing. Run: pip install boto3")

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.environ.get("R2_BUCKET", "capture-media")

FETCH_TIMEOUT = 30
MAX_BYTES = 25_000_000
PRESIGN_SECONDS = 3600

DIM, RESET, BOLD = "\033[2m", "\033[0m", "\033[1m"
GREEN, YELLOW, RED = "\033[32m", "\033[33m", "\033[31m"

EXT_FOR = {
    "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif",
    "image/webp": "webp", "video/mp4": "mp4", "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
}


def r2():
    missing = [n for n, v in [
        ("R2_ACCOUNT_ID", R2_ACCOUNT_ID),
        ("R2_ACCESS_KEY_ID", R2_ACCESS_KEY_ID),
        ("R2_SECRET_ACCESS_KEY", R2_SECRET_ACCESS_KEY),
    ] if not v]
    if missing:
        sys.exit(f"Missing from .env: {', '.join(missing)}")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        region_name="auto",
    )


def key_for(source: str, inbox_id, index: int, content_type: str, url: str) -> str:
    ext = EXT_FOR.get((content_type or "").split(";")[0].strip())
    if not ext:
        tail = url.split("?")[0].rsplit(".", 1)
        ext = tail[-1].lower() if len(tail) > 1 and len(tail[-1]) <= 4 else "bin"
    src = (source or "unknown").split("_")[0]
    return f"{src}/{inbox_id}/{index}.{ext}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--redo", action="store_true", help="include rows already archived")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--url", help="print a temporary link for one object key, then exit")
    args = ap.parse_args()

    client = r2()

    if args.url:
        print(client.generate_presigned_url(
            "get_object", Params={"Bucket": R2_BUCKET, "Key": args.url},
            ExpiresIn=PRESIGN_SECONDS))
        return

    # Fail early and clearly if the bucket is wrong, rather than 740 times.
    try:
        client.head_bucket(Bucket=R2_BUCKET)
    except ClientError as e:
        sys.exit(f"Cannot reach bucket '{R2_BUCKET}': {e}")

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    rows, off = [], 0
    while True:
        page = (sb.table("inbox")
                .select("id,folder,source,media_urls,stored_media,media_archived_at")
                .order("id").range(off, off + 999)).execute().data
        if not page:
            break
        rows += page
        off += 1000
        if len(page) < 1000:
            break

    todo = []
    for r in rows:
        if not (r.get("media_urls") or []):
            continue
        if args.folder and (r.get("folder") or "").lower() != args.folder.lower():
            continue
        if r.get("media_archived_at") and not args.redo:
            continue
        todo.append(r)

    if args.limit:
        todo = todo[:args.limit]
    if not todo:
        print("Nothing left to archive.")
        return

    images = sum(len(r["media_urls"]) for r in todo)
    print(f"{BOLD}Archiving {images} files from {len(todo)} captures into "
          f"r2://{R2_BUCKET}{RESET}")
    print(f"{DIM}media_urls is never changed. This only adds stored_media.{RESET}\n")

    http = httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0"})
    stats = {"stored": 0, "already": 0, "dead": 0, "skipped": 0, "bytes": 0}

    for n, row in enumerate(todo, 1):
        existing = row.get("stored_media") or []
        keys, errors = list(existing), []

        src = (row.get("source") or "unknown").split("_")[0]
        for i, url in enumerate(row["media_urls"]):
            # Keys look like twitter/8891/0.jpg, so this prefix identifies one file
            # regardless of what extension it turned out to have.
            prefix = f"{src}/{row['id']}/{i}."
            if not args.redo and any(k.startswith(prefix) for k in existing):
                stats["already"] += 1
                continue
            try:
                resp = http.get(url)
                resp.raise_for_status()
                if len(resp.content) > MAX_BYTES:
                    raise ValueError(f"{len(resp.content)} bytes is over the cap")
                ctype = resp.headers.get("content-type", "")
                key = key_for(row.get("source"), row["id"], i, ctype, url)
                if not args.dry_run:
                    client.put_object(
                        Bucket=R2_BUCKET, Key=key, Body=resp.content,
                        ContentType=ctype or "application/octet-stream",
                    )
                keys.append(key)
                stats["stored"] += 1
                stats["bytes"] += len(resp.content)
                print(f"  {DIM}{n}/{len(todo)}{RESET} {GREEN}{key}{RESET} "
                      f"{DIM}{len(resp.content)//1024}KB{RESET}")
            except Exception as e:
                # A dead link is a fact worth recording, not a crash.
                msg = f"{type(e).__name__}: {str(e)[:120]}"
                errors.append(f"[{i}] {msg}")
                stats["dead"] += 1
                print(f"  {DIM}{n}/{len(todo)}{RESET} {RED}gone{RESET} {DIM}{url[:70]}{RESET}")

        if args.dry_run:
            continue

        sb.table("inbox").update({
            "stored_media": keys,
            "media_archived_at": "now()",
            "media_error": "; ".join(errors) if errors else None,
        }).eq("id", row["id"]).execute()
        time.sleep(0.05)

    b = stats["bytes"]
    size = f"{b/1_000_000_000:.1f}GB" if b >= 1_000_000_000 else \
           f"{b/1_000_000:.0f}MB" if b >= 1_000_000 else f"{b//1024}KB"
    print(f"\n{BOLD}Done.{RESET} {stats['stored']} stored ({size}), "
          f"{stats['already']} already there, {stats['dead']} could not be fetched.")
    if stats["dead"]:
        print(f"{YELLOW}Those {stats['dead']} were already lost. The reason is in "
              f"inbox.media_error.{RESET}")
    if args.dry_run:
        print(f"{YELLOW}Dry run — nothing was uploaded or written.{RESET}")


if __name__ == "__main__":
    main()
