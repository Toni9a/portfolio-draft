"""
fetch_covers.py  (2026-11-18)
─────────────────────────────
Gets the cover image(s) of saved Instagram/TikTok posts in chosen folders, copies
them to R2 and fills inbox.media_urls + stored_media, so tag_images.py can tag them
and they appear in Tonidex Visuals. Meant for visual folders only (e.g. Aesth);
everything else doesn't need images.

Run on the Mac (home IP + Chrome cookies for Instagram):
  python3 scripts/fetch_covers.py --folder Aesth --dry-run
  python3 scripts/fetch_covers.py --folder Aesth
  python3 scripts/tag_images.py --all          # right after: IG cover links expire
Re-runs skip rows that already have an R2 image. Never deletes anything.
Needs: yt-dlp, boto3, httpx; .env with SUPABASE_* and R2_*.
"""
import argparse, json, random, subprocess, sys, time
from pathlib import Path

import httpx
sys.path.insert(0, str(Path(__file__).parent))
from archive_media import R2_BUCKET, key_for, r2, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  # noqa: E402
from supabase import create_client  # noqa: E402

IMG_RE = (".jpg", ".jpeg", ".png", ".webp", ".gif")
MAX_PER_POST = 3


def cover_urls(url: str, cookies: str) -> list[str]:
    cmd = ["yt-dlp", "--dump-single-json", "--skip-download", "--ignore-no-formats-error",
           "--no-warnings", "--socket-timeout", "30", url]
    if cookies:
        cmd[1:1] = ["--cookies-from-browser", cookies]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if not p.stdout.strip():
        raise RuntimeError((p.stderr or "no output").strip().splitlines()[-1][:160])
    info = json.loads(p.stdout)
    out = []
    for e in (info.get("entries") or [info]):
        t = (e or {}).get("thumbnail")
        if not t and (e or {}).get("thumbnails"):
            t = e["thumbnails"][-1].get("url")
        if t and t not in out:
            out.append(t)
        if len(out) >= MAX_PER_POST:
            break
    if not out and info.get("thumbnail"):
        out.append(info["thumbnail"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True, help="comma-separated inbox.folder values")
    ap.add_argument("--source", default="instagram_save,tiktok_save")
    ap.add_argument("--cookies-from-browser", default="chrome")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    rows = (sb.table("inbox").select("id,source,url,folder,media_urls,stored_media")
            .in_("folder", [f.strip() for f in a.folder.split(",")])
            .in_("source", [s.strip() for s in a.source.split(",")]).execute().data)
    todo = [r for r in rows if r.get("url") and not any(str(k).lower().endswith(IMG_RE) for k in (r.get("stored_media") or []))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(rows)} rows in {a.folder}; {len(todo)} without an R2 image")
    s3 = None if a.dry_run else r2()
    ok = fail = 0
    for n, r in enumerate(todo, 1):
        try:
            urls = cover_urls(r["url"], a.cookies_from_browser if "instagram" in r["source"] else "")
            if not urls:
                raise RuntimeError("no cover found")
            if a.dry_run:
                print(f"  {n}/{len(todo)} {r['url']}  → {len(urls)} cover(s)"); ok += 1; continue
            keys = list(r.get("stored_media") or [])
            for i, u in enumerate(urls):
                resp = httpx.get(u, timeout=30, follow_redirects=True); resp.raise_for_status()
                ctype = resp.headers.get("content-type", "image/jpeg")
                key = key_for(r["source"], r["id"], i, ctype, u)
                s3.put_object(Bucket=R2_BUCKET, Key=key, Body=resp.content, ContentType=ctype)
                keys.append(key)
            upd = {"stored_media": keys, "media_archived_at": "now()", "media_error": None}
            if not (r.get("media_urls") or []):
                upd["media_urls"] = urls
            sb.table("inbox").update(upd).eq("id", r["id"]).execute()
            print(f"  {n}/{len(todo)} ✓ {r['url']}  ({len(urls)})"); ok += 1
        except Exception as e:
            print(f"  {n}/{len(todo)} ✗ {r['url']}  {e}"); fail += 1
        time.sleep(random.uniform(3, 7))
    print(f"done: {ok} ok, {fail} failed" + ("  (dry run, nothing written)" if a.dry_run else ""))


if __name__ == "__main__":
    main()
