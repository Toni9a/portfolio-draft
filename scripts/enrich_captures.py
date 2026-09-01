"""
enrich_captures.py
──────────────────
Enrichment worker for Telegram captures. Runs on your laptop.
Polls for new Telegram items and enriches them based on source:
  • YouTube: fetch captions via yt-dlp (no video download)
  • TikTok: fetch captions + audio metadata (no video download)
  • Instagram: fetch image + audio metadata (no video download)
  • Links: fetch page title + text

All media goes to R2 (capture-media bucket), paths recorded in stored_media[].
When done, marks status as 'pending' so the item flows into digest/tagging.

Run on your laptop:
  python scripts/enrich_captures.py

Options:
  --limit 5              Process max 5 items (default: all waiting)
  --dry-run              Print what would happen without writing
  --retry-failed         Include items that previously failed (default: skip)
"""

import os
import json
import re
import sys
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv
from supabase import create_client, Client
import boto3
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Try yt-dlp
try:
    import yt_dlp
    HAS_YT_DLP = True
except ImportError:
    HAS_YT_DLP = False
    print("⚠️  yt-dlp not found. Install with: pip install yt-dlp")

# Whisper for audio transcription
try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False
    print("⚠️  whisper not found. Install with: pip install openai-whisper")

# Locate ffmpeg explicitly. yt-dlp's audio postprocessor shells out to ffprobe/ffmpeg,
# and that subprocess doesn't always inherit the same PATH as the parent Python
# process (e.g. when running inside a conda env) — so resolve it once here and
# pass ffmpeg_location explicitly rather than relying on PATH at call time.
_FFMPEG_BIN = (
    shutil.which("ffmpeg")
    or next((p for p in ["/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg"] if Path(p).exists()), None)
)
FFMPEG_LOCATION = str(Path(_FFMPEG_BIN).parent) if _FFMPEG_BIN else None
if not FFMPEG_LOCATION:
    print("⚠️  ffmpeg not found (checked PATH, /opt/homebrew/bin, /usr/local/bin). "
          "Audio extraction for TikTok fallback will fail. Install with: brew install ffmpeg")

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.environ.get("R2_BUCKET", "capture-media")

# Validate credentials
if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
    print("❌ Missing credentials. Check .env file:")
    print(f"   SUPABASE_URL: {bool(SUPABASE_URL)}")
    print(f"   SUPABASE_SERVICE_ROLE_KEY: {bool(SUPABASE_SERVICE_ROLE_KEY)}")
    print(f"   R2_ACCOUNT_ID: {bool(R2_ACCOUNT_ID)}")
    print(f"   R2_ACCESS_KEY_ID: {bool(R2_ACCESS_KEY_ID)}")
    print(f"   R2_SECRET_ACCESS_KEY: {bool(R2_SECRET_ACCESS_KEY)}")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# R2 client (S3-compatible)
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    region_name="auto",
)

# Resilient HTTP session
session = requests.Session()
retry = Retry(connect=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; bot/1.0)"})


def is_url(text: str) -> bool:
    """Check if text is a URL."""
    return bool(re.match(r"https?://", text.strip()))


def detect_source_type(url: str) -> str:
    """Detect what kind of URL this is."""
    domain = urlparse(url).netloc.lower()

    if "youtube.com" in domain or "youtu.be" in domain:
        return "youtube"
    elif "tiktok.com" in domain:
        return "tiktok"
    elif "instagram.com" in domain or "instagr.am" in domain:
        return "instagram"
    elif "twitter.com" in domain or "x.com" in domain:
        return "twitter"
    else:
        return "generic"


def fetch_page_text(url: str, inbox_id: str) -> tuple[str | None, str | None]:
    """Fetch page title + text for a generic link."""
    try:
        resp = session.get(url, timeout=10)
        resp.raise_for_status()

        # Extract title
        title_match = re.search(r"<title>([^<]+)</title>", resp.text, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else None

        # Simple text extraction
        text = re.sub(r"<script[^>]*>.*?</script>", "", resp.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()[:2000]

        return title, text if text else None
    except Exception as e:
        print(f"   ⚠️  Failed to fetch page text: {e}")
        return None, None


def fetch_youtube_captions(url: str, inbox_id: str) -> tuple[list[str], str | None]:
    """Fetch captions from YouTube. Returns (stored_keys, transcript)."""
    if not HAS_YT_DLP:
        print("   ⚠️  yt-dlp not available")
        return [], None

    try:
        work_dir = Path(f"/tmp/yt_{inbox_id}")
        work_dir.mkdir(exist_ok=True)

        with yt_dlp.YoutubeDL({
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "subtitlesformat": "srt",
            "outtmpl": str(work_dir / "video_%(id)s"),
        }) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")

            # Look for downloaded subtitle files
            caption_files = list(work_dir.glob(f"video_{video_id}.*.srt"))
            if caption_files:
                with open(caption_files[0]) as f:
                    srt_content = f.read()
                    # Parse SRT: extract text, skip timestamps
                    transcript = "\n".join([
                        line for line in srt_content.split("\n")
                        if line.strip() and not re.match(r"^\d+$", line.strip())
                        and not re.match(r"^\d{2}:\d{2}:\d{2}", line.strip())
                    ])

                    # Store to R2
                    key = f"youtube/{inbox_id}/captions.srt"
                    s3.put_object(Bucket=R2_BUCKET, Key=key, Body=srt_content)
                    print(f"   ✓ Stored YouTube captions")

                    return [key], transcript if transcript.strip() else None

        return [], None
    except Exception as e:
        print(f"   ⚠️  YouTube failed: {e}")
        return [], None


def fetch_tiktok_audio_whisper(url: str, inbox_id: str) -> tuple[list[str], str | None]:
    """
    Fallback for TikToks with no captions (regular or auto).
    Extracts audio only (no video download) and transcribes via Whisper.
    Per PRD: ~1MB/min audio vs ~15MB/min video.
    """
    if not HAS_YT_DLP:
        print("   ⚠️  yt-dlp not available for audio fallback")
        return [], None
    if not HAS_WHISPER:
        print("   ⚠️  whisper not available — install with: pip install openai-whisper")
        return [], None

    work_dir = Path(f"/tmp/tiktok_audio_{inbox_id}")
    work_dir.mkdir(exist_ok=True)
    audio_template = str(work_dir / "audio")

    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": audio_template + ".%(ext)s",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            }],
        }
        if FFMPEG_LOCATION:
            ydl_opts["ffmpeg_location"] = FFMPEG_LOCATION

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_files = list(work_dir.glob("audio.*"))
        if not audio_files:
            print("   ⚠️  No audio extracted")
            return [], None

        audio_path = audio_files[0]

        print("   🎧 Transcribing audio with Whisper (this can take a moment)...")
        model = whisper.load_model("base")
        result = model.transcribe(str(audio_path))
        transcript = (result.get("text") or "").strip()

        stored_keys = []

        # Store the audio itself, per PRD: same bucket, under audio/
        with open(audio_path, "rb") as f:
            audio_key = f"audio/tiktok/{inbox_id}.m4a"
            s3.put_object(Bucket=R2_BUCKET, Key=audio_key, Body=f.read())
            stored_keys.append(audio_key)
            print(f"   ✓ Stored TikTok audio ({audio_path.stat().st_size // 1024} KB)")

        if transcript:
            transcript_key = f"tiktok/{inbox_id}/whisper_transcript.txt"
            s3.put_object(Bucket=R2_BUCKET, Key=transcript_key, Body=transcript)
            stored_keys.append(transcript_key)
            print(f"   ✓ Whisper transcript ({len(transcript)} chars)")
        else:
            print("   ⚠️  Whisper produced no text (likely music/no speech)")

        return stored_keys, transcript if transcript else None
    except Exception as e:
        print(f"   ⚠️  TikTok audio/Whisper fallback failed: {e}")
        return [], None
    finally:
        # Cleanup temp files regardless of outcome
        for f in work_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            work_dir.rmdir()
        except OSError:
            pass


def fetch_tiktok_enrichment(url: str, inbox_id: str) -> tuple[list[str], str | None]:
    """Fetch TikTok captions (subtitles + automatic), returns metadata only."""
    if not HAS_YT_DLP:
        print("   ⚠️  yt-dlp not available")
        return [], None

    stored_keys = []
    transcript = None

    work_dir = Path(f"/tmp/tiktok_captions_{inbox_id}")
    work_dir.mkdir(exist_ok=True)

    try:
        # NOTE: extract_info(download=False) never populates a "data" key on
        # subtitle/automatic_caption entries — those only carry a "url" to fetch
        # the file from. Use download=True with skip_download so yt-dlp fetches
        # only the subtitle files (not the video) and writes them to work_dir,
        # then read them from disk. Mirrors fetch_youtube_captions() above.
        tiktok_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writesubtitles": True,
            "writeautosub": True,
            # TikTok usually only offers vtt/json, not srt directly — request srt
            # with vtt as fallback, and convert whatever comes down to srt via
            # ffmpeg so the glob below always finds a .srt file.
            "subtitlesformat": "srt/vtt/best",
            "outtmpl": str(work_dir / "tiktok_%(id)s"),
            "postprocessors": [{"key": "FFmpegSubtitlesConvertor", "format": "srt"}],
        }
        if FFMPEG_LOCATION:
            tiktok_opts["ffmpeg_location"] = FFMPEG_LOCATION

        with yt_dlp.YoutubeDL(tiktok_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get("id")

            # yt-dlp doesn't reliably distinguish manual vs. auto captions in the
            # filename, so just take whatever it wrote. Fall back to any raw
            # subtitle file (e.g. .vtt) in case the srt conversion didn't run.
            caption_files = sorted(work_dir.glob(f"tiktok_{video_id}.*.srt"))
            if not caption_files:
                caption_files = sorted(
                    f for f in work_dir.glob(f"tiktok_{video_id}.*")
                    if f.suffix in (".vtt", ".srt")
                )
            if caption_files:
                cap_path = caption_files[0]
                cap_content = cap_path.read_text()
                lang_match = re.search(r"\.([a-zA-Z-]+)\.(?:srt|vtt)$", cap_path.name)
                lang = lang_match.group(1) if lang_match else "unknown"

                transcript = "\n".join([
                    line for line in cap_content.split("\n")
                    if line.strip() and not re.match(r"^\d+$", line.strip())
                    and not re.match(r"^\d{2}:\d{2}:\d{2}", line.strip())
                    and not line.strip().startswith("WEBVTT")
                ])[:2000]

                key = f"tiktok/{inbox_id}/captions_{lang}{cap_path.suffix}"
                s3.put_object(Bucket=R2_BUCKET, Key=key, Body=cap_content)
                stored_keys.append(key)
                print(f"   ✓ Stored TikTok captions ({lang}, {cap_path.suffix.lstrip('.')})")

            if not stored_keys:
                print(f"   ⚠️  No captions found on this TikTok — falling back to audio + Whisper")

        # No captions of either kind — try audio extraction + Whisper transcription.
        if not stored_keys:
            audio_keys, audio_transcript = fetch_tiktok_audio_whisper(url, inbox_id)
            stored_keys.extend(audio_keys)
            if audio_transcript:
                transcript = audio_transcript

        return stored_keys, transcript if transcript else None
    except Exception as e:
        # TikTok is currently blocking yt-dlp's webpage-challenge solver platform-wide
        # (open upstream bug: https://github.com/yt-dlp/yt-dlp/issues/17403, unresolved
        # as of 2026-08-18). This is not "this TikTok has no captions" — it's "TikTok
        # extraction is broken right now." Re-raise so the caller records the real error
        # and leaves the item as retryable ('new' + media_error) instead of marking it
        # 'pending' as if enrichment genuinely completed with no content.
        if "Unexpected response from webpage request" in str(e) or "_solve_challenge_and_set_cookies" in str(e):
            print(f"   ❌ TikTok extraction blocked platform-wide (yt-dlp issue #17403, not item-specific): {e}")
            raise
        print(f"   ⚠️  TikTok failed: {e}")
        return [], None
    finally:
        for f in work_dir.glob("*"):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            work_dir.rmdir()
        except OSError:
            pass


def fetch_instagram_enrichment(url: str, inbox_id: str) -> tuple[list[str], str | None]:
    """Fetch Instagram info (no video download). Returns (stored_keys, transcript)."""
    if not HAS_YT_DLP:
        print("   ⚠️  yt-dlp not available")
        return [], None

    try:
        insta_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "writeinfojson": True,
            "outtmpl": f"/tmp/insta_{inbox_id}",
        }
        # Instagram requires a logged-in session for nearly everything now.
        # Pull cookies from a local browser (default: chrome) rather than
        # requiring a manual cookies.txt export. Override with
        # INSTAGRAM_COOKIES_BROWSER=firefox/edge/safari/none in .env.
        cookies_browser = os.environ.get("INSTAGRAM_COOKIES_BROWSER", "chrome").strip().lower()
        if cookies_browser and cookies_browser != "none":
            insta_opts["cookiesfrombrowser"] = (cookies_browser,)

        with yt_dlp.YoutubeDL(insta_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            # Store metadata
            title = info.get("title", "")
            description = info.get("description", "")
            caption = f"{title}\n{description}".strip()

            if caption:
                key = f"instagram/{inbox_id}/metadata.txt"
                s3.put_object(Bucket=R2_BUCKET, Key=key, Body=caption)
                print(f"   ✓ Stored Instagram metadata")
                return [key], caption if caption else None

        return [], None
    except Exception as e:
        print(f"   ⚠️  Instagram failed: {e}")
        return [], None


def enrich_item(item: dict, dry_run: bool = False) -> bool:
    """
    Enrich a single inbox item.
    Returns True if successful, False otherwise.
    """
    inbox_id = item["id"]
    source = item.get("source", "")
    url = item.get("url")

    print(f"\n📦 {source.upper()}: {inbox_id}")

    if not url or not is_url(url):
        print(f"   ⚠️  No URL, skipping")
        return False

    source_type = detect_source_type(url)
    stored_keys = []
    new_text = None

    try:
        if source_type == "youtube":
            print(f"   🎬 YouTube")
            stored_keys, new_text = fetch_youtube_captions(url, inbox_id)
        elif source_type == "tiktok":
            print(f"   🎵 TikTok")
            stored_keys, new_text = fetch_tiktok_enrichment(url, inbox_id)
        elif source_type == "instagram":
            print(f"   📸 Instagram")
            stored_keys, new_text = fetch_instagram_enrichment(url, inbox_id)
        else:
            print(f"   🔗 Generic link")
            title, text = fetch_page_text(url, inbox_id)
            if text:
                new_text = f"{title}\n\n{text}" if title else text
                print(f"   ✓ Fetched page text ({len(text)} chars)")

    except Exception as e:
        print(f"   ❌ Enrichment error: {e}")
        if not dry_run:
            supabase.table("inbox").update({
                "media_error": str(e),
                "media_archived_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", inbox_id).execute()
        return False

    if not dry_run:
        update_data = {
            "status": "pending",
            "media_archived_at": datetime.now(timezone.utc).isoformat(),
        }

        if stored_keys:
            existing = item.get("stored_media") or []
            update_data["stored_media"] = existing + stored_keys

        if new_text:
            existing_text = item.get("full_text") or ""
            if new_text not in existing_text:
                update_data["full_text"] = f"{existing_text}\n\n{new_text}".strip()

        # Fetchers swallow their own errors and return ([], None) rather than
        # raising, so an enrichment attempt that genuinely found nothing looks
        # identical here to one that succeeded. Flag it via media_error so it
        # stays queryable/distinguishable, without blocking the item from
        # flowing to 'pending' — a URL-bearing item with no content is still
        # information, per the PRD's "capture never fails" rule.
        if source_type in ("youtube", "tiktok", "instagram") and not stored_keys and not new_text:
            update_data["media_error"] = "no content found (no captions/transcript/media)"
            print(f"   ⚠️  Nothing usable found — flagging media_error, still moving to 'pending'")

        result = supabase.table("inbox").update(update_data).eq("id", inbox_id).execute()
        if result.data:
            print(f"   ✓ Updated status to 'pending'")
            return True
        else:
            print(f"   ❌ Failed to update row")
            return False
    else:
        print(f"   [DRY RUN] Would store {len(stored_keys)} files, update status to 'pending'")
        return True


def main():
    parser = argparse.ArgumentParser(description="Enrich Telegram captures")
    parser.add_argument("--limit", type=int, default=None, help="Max items to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to Supabase/R2")
    parser.add_argument("--retry-failed", action="store_true", help="Include previously failed items")
    args = parser.parse_args()

    print(f"🔄 Enrichment worker starting...")
    print(f"   R2 bucket: {R2_BUCKET}")
    print(f"   yt-dlp: {'✓' if HAS_YT_DLP else '✗'}")
    print(f"   whisper: {'✓' if HAS_WHISPER else '✗'}")
    if args.dry_run:
        print(f"   [DRY RUN MODE]")

    # Query for items needing enrichment (Telegram sources only)
    query = supabase.table("inbox").select("*").eq("status", "new").neq("url", None)
    query = query.ilike("source", "telegram_%")

    if not args.retry_failed:
        query = query.is_("media_error", None)

    if args.limit:
        query = query.limit(args.limit)

    result = query.execute()
    items = result.data or []

    if not items:
        print(f"✓ No items waiting for enrichment")
        return

    print(f"\n📋 Found {len(items)} items to enrich\n")

    success = 0
    failed = 0

    for item in items:
        if enrich_item(item, dry_run=args.dry_run):
            success += 1
        else:
            failed += 1

    print(f"\n\n✅ Done: {success} succeeded, {failed} failed")


if __name__ == "__main__":
    main()
