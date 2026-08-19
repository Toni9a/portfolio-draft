# Enrichment Worker Setup

The enrichment worker runs on your laptop and enriches Telegram captures with media, captions, and transcripts. It stores everything to R2 and updates the database.

## Prerequisites

### 1. Install dependencies

```bash
pip install yt-dlp whisper boto3 requests python-dotenv supabase
```

Optional but recommended:
```bash
# For better subtitle handling
pip install pycaption
```

### 2. Update your `.env` file

You already have the R2 credentials from Part 1. Make sure these are set:

```
R2_ACCOUNT_ID=eb8193d2791bec64568e1115104e2e1d
R2_ACCESS_KEY_ID=your-key-id
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET=capture-media
```

Plus your existing Supabase keys:
```
SUPABASE_URL=https://...
SUPABASE_SERVICE_ROLE_KEY=...
```

### 3. FFmpeg (required for audio extraction)

The worker uses FFmpeg to extract audio from videos. Install it:

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html

## How it works

When you run the worker, it:

1. **Queries** for inbox items where `status = 'new'` and `url` is not null
2. **Detects** the source type (YouTube, TikTok, Instagram, or generic link)
3. **Enriches** based on type:
   - **YouTube**: Downloads captions via yt-dlp, stores to `youtube/<inbox_id>/captions.srt`
   - **TikTok**: Downloads captions (if available) + audio-only (m4a), stores to `tiktok/<inbox_id>/`
   - **Instagram**: Downloads audio + image thumbnail, stores to `instagram/<inbox_id>/`
   - **Links**: Fetches page title + text, appends to `full_text`
4. **Stores** all files to R2 in the `capture-media` bucket
5. **Records** the object keys in `stored_media[]`
6. **Updates** status to `'pending'` so the item flows into digest/tagging

## Running it

### First time (dry-run to check):
```bash
cd ~/personal\ port
python scripts/enrich_captures.py --dry-run --limit 5
```

This shows what would happen without actually writing anything.

### Process all waiting items:
```bash
python scripts/enrich_captures.py
```

### Process just a few:
```bash
python scripts/enrich_captures.py --limit 10
```

### Retry previously failed items:
```bash
python scripts/enrich_captures.py --retry-failed
```

## What gets stored where

All files land in the `capture-media` R2 bucket:

```
youtube/<inbox_id>/captions.srt          # YouTube captions
tiktok/<inbox_id>/captions_en.srt        # TikTok captions (if available)
tiktok/<inbox_id>/audio.m4a              # TikTok audio
instagram/<inbox_id>/audio.m4a           # Instagram audio (from video)
instagram/<inbox_id>/image.jpg           # Instagram image/thumbnail
```

The `inbox.stored_media[]` array records which files were stored for that item. `inbox.full_text` gets appended with transcripts and page text.

## Troubleshooting

### yt-dlp not found
```bash
pip install --upgrade yt-dlp
```

### FFmpeg not found
Check your FFmpeg installation:
```bash
which ffmpeg
ffmpeg -version
```

### TikTok/Instagram videos fail to download
These platforms change their APIs frequently. Make sure yt-dlp is up to date:
```bash
pip install --upgrade yt-dlp
```

### Whisper takes forever or runs out of memory
The `--base` model is the smallest. If it's still too slow on your machine, you can switch to the `tiny` model in the script (line ~228), but accuracy will drop.

### Some TikToks have no captions
That's normal — if the creator didn't enable captions in TikTok, there's nothing to fetch. The worker stores the audio and tries Whisper if available, which works for speech-heavy content.

## Automation (optional)

You can set this to run periodically via a cron job (macOS/Linux) or Task Scheduler (Windows).

### macOS/Linux cron

Edit your crontab:
```bash
crontab -e
```

Add a line to run every hour:
```
0 * * * * cd ~/personal\ port && python scripts/enrich_captures.py >> /tmp/enrich.log 2>&1
```

Or every day at 2am:
```
0 2 * * * cd ~/personal\ port && python scripts/enrich_captures.py >> /tmp/enrich.log 2>&1
```

## When to run it

The enrichment worker polls for items that:
- Are sourced from Telegram (`telegram_link`, `telegram_voice`, etc.)
- Have `status = 'new'` (not yet processed)
- Have a URL (or text, for voice notes)

So it's safe to run anytime. If there's nothing waiting, it exits silently. Once an item is enriched, it moves to `status = 'pending'` and won't be touched again (unless you explicitly pass `--retry-failed`).

## Next steps

Once items are `'pending'`, they're ready for:
1. **Tagging** — `scripts/tag_images.py` (for visual items)
2. **Digest clustering** — `scripts/generate_digest.py`
3. **Blog selection** — mark `is_blog_candidate = true` in admin, then draft a post
