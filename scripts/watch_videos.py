#!/usr/bin/env python3
"""
watch_videos.py — video pass for social saves (spec: social_ingest/social_ingest_spec_2026-11-15.md)

Modes:
    --ytdlp-only     Phase 0 sample test (no Gemini, no Supabase)
    --reroute-cached recompute Phase 0 routes from cached JSONs
    --cost-test      Gemini steps on 10 cached videos, prints cost
    --run            full pass over inbox rows with video_route='pending'
                     (add --plan-only for no Gemini/no writes; --limit, --max-spend-usd)

Phase 0:

    python3 scripts/watch_videos.py --ytdlp-only --limit 20 \
        --out ~/Downloads/social_exports/test_run/

Phase 0 = free yt-dlp test. No Gemini calls, no Supabase writes.
Picks a sample (10 TikTok collection videos split across Ai/learning and Veo,
5 unfiled TikTok favourites from 2025+, 5 Instagram reels from kept saves),
fetches metadata + native subtitles with yt-dlp (no media download), writes one
JSON per video and a summary.json, and reports which route each video *would*
take in the full pass.
"""
import argparse
import glob
import json
import os
import random
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXPORTS = Path.home() / "Downloads" / "social_exports"

# Routing rules (Toni, 2026-11-17; see spec "Video pass")
# Veo: never a full watch. Caption + native transcript (if any) + cover image tag.
NO_WATCH_FOLDERS = {"Veo"}
# Other visual folders: full watch only when there's no usable transcript.
VISUAL_FOLDERS = {"Flowers", "Art gallery etCz", "Food", "Aesth",
                  "Layout", "Canvas layout", "Content inspo"}
# Tool demo = caption names a tool/app AND transcript points at the screen.
SCREEN_PHRASES = re.compile(
    r"\b(look at this|as you can see|here'?s my setup|this setup|watch this|on screen|on the screen)\b", re.I)
TOOL_NAMES = re.compile(
    r"\b(apps?|tools?|software|plugin|extension|claude|chatgpt|gpt|gemini|cursor|figma|framer|notion|"
    r"canva|powerpoint|excel|keynote|photoshop|illustrator|blender|webflow|n8n|zapier|vs ?code|"
    r"github|macbook|iphone|ipad|vision pro)\b", re.I)
WPM_FLOOR = 60

# Instagram: decided in spec section A
IG_DROP_COLLECTIONS = {"Fitness stretch", "Safto", "MK", "Temi Teeeth", "Tennis", "Food ldn"}
IG_ALWAYS_KEEP = {"Aesth", "Patrick bs"}
IG_CUTOFF = datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp()
TT_UNFILED_CUTOFF = "2025-01-01"


# ───────────────────────── helpers ─────────────────────────

def fix_ig(s):
    """Instagram exports double-encode UTF-8."""
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def tt_id(url):
    m = re.search(r"/(?:video|photo)/(\d+)", url or "")
    return m.group(1) if m else None


def tt_norm(vid):
    return f"https://www.tiktok.com/@_/video/{vid}"


def ig_norm(url):
    return (url or "").split("?")[0].rstrip("/") + "/"


def ig_fields(label_values):
    """Flatten one Instagram {label_values:[...]} record (recursive walker)."""
    out = {"hashtags": [], "owner": None}
    for lv in label_values or []:
        title = lv.get("title")
        if "dict" in lv and title == "Hashtags":
            for d in lv["dict"]:
                for x in d.get("dict", []):
                    if x.get("label") == "Name":
                        out["hashtags"].append(fix_ig(x.get("value")))
        elif "dict" in lv and title == "Owner":
            for d in lv["dict"]:
                for x in d.get("dict", []):
                    if x.get("label") == "Username":
                        out["owner"] = fix_ig(x.get("value"))
        elif "label" in lv:
            out[lv["label"].lower()] = fix_ig(lv.get("value"))
    return out


# ───────────────────────── sample selection ─────────────────────────

def pick_tiktok_collections(coll_file, ai_file, n, rng):
    coll = json.load(open(coll_file))["collections"]
    ai = json.load(open(ai_file))["items"]
    pools = {
        "Ai/learning": [(u, c) for u, c in ai if "/video/" in u],
        "Veo": [(u, None) for u in coll["Veo"]["items"] if "/video/" in u],
    }
    half = n // 2
    picks = []
    for folder, k in (("Ai/learning", n - half), ("Veo", half)):
        for url, cap in rng.sample(pools[folder], min(k, len(pools[folder]))):
            vid = tt_id(url)
            picks.append({"platform": "tiktok", "group": "tiktok_collection",
                          "folder": folder, "video_id": vid, "url": tt_norm(vid),
                          "source_url": url, "scraped_caption": cap})
    # all collection IDs, so unfiled picks exclude them
    all_ids = {tt_id(u) for u, _ in ai}
    for name, c in coll.items():
        for u in c.get("items", []):
            all_ids.add(tt_id(u))
    return picks, all_ids


def pick_tiktok_unfiled(tiktok_file, collection_ids, n, rng):
    data = json.load(open(tiktok_file))
    favs = data["Likes and Favorites"]["Favorite Videos"]["FavoriteVideoList"]
    pool = [f for f in favs
            if f.get("Date", "") >= TT_UNFILED_CUTOFF
            and tt_id(f.get("Link")) and tt_id(f["Link"]) not in collection_ids]
    picks = []
    for f in rng.sample(pool, min(n, len(pool))):
        vid = tt_id(f["Link"])
        picks.append({"platform": "tiktok", "group": "tiktok_unfiled", "folder": "TikTok saves",
                      "video_id": vid, "url": tt_norm(vid), "source_url": f["Link"],
                      "saved_at": f["Date"]})
    return picks, len(pool)


def pick_instagram_reels(ig_dir, n, rng):
    saved = json.load(open(Path(ig_dir) / "saved" / "saved_posts.json"))
    colls = json.load(open(Path(ig_dir) / "saved" / "saved_collections.json"))
    url_to_colls = {}
    for c in colls:
        name = None
        for lv in c.get("label_values", []):
            if lv.get("label") == "Name":
                name = fix_ig(lv.get("value"))
        for lv in c.get("label_values", []):
            for d in lv.get("dict", []) or []:
                f = ig_fields(d.get("dict", []))
                if f.get("url"):
                    url_to_colls.setdefault(ig_norm(f["url"]), set()).add(name)
    pool = []
    for p in saved:
        f = ig_fields(p.get("label_values"))
        url = ig_norm(f.get("url"))
        if "/reel/" not in url:
            continue
        cs = url_to_colls.get(url, set())
        keep = bool(cs & IG_ALWAYS_KEEP) or (
            p.get("timestamp", 0) >= IG_CUTOFF and not (cs & IG_DROP_COLLECTIONS))
        if keep:
            pool.append((p, f, cs))
    picks = []
    for p, f, cs in rng.sample(pool, min(n, len(pool))):
        folder = sorted(cs)[0] if cs else "Instagram saves"
        picks.append({"platform": "instagram", "group": "instagram_reel", "folder": folder,
                      "collections": sorted(cs), "url": ig_norm(f["url"]),
                      "video_id": ig_norm(f["url"]).rstrip("/").split("/")[-1],
                      "saved_at": datetime.fromtimestamp(p["timestamp"], timezone.utc).isoformat(),
                      "scraped_caption": f.get("caption"), "export_owner": f.get("owner"),
                      "export_hashtags": f.get("hashtags")})
    return picks, len(pool)


# ───────────────────────── yt-dlp ─────────────────────────

def vtt_to_text(path):
    lines, last = [], None
    for raw in open(path, encoding="utf-8", errors="replace"):
        s = raw.strip()
        if (not s or s == "WEBVTT" or "-->" in s or s.isdigit()
                or s.startswith(("NOTE", "Kind:", "Language:", "STYLE"))):
            continue
        s = re.sub(r"<[^>]+>", "", s).strip()
        if s and s != last:
            lines.append(s)
            last = s
    return " ".join(lines).strip() or None


def pick_sub_file(files):
    """Prefer creator subs over ASR, English over other languages."""
    def rank(p):
        name = os.path.basename(p).lower()
        lang = name.rsplit(".", 2)[-2] if name.count(".") >= 2 else ""
        return (0 if lang.startswith(("en", "eng")) else 1, len(name))
    return sorted(files, key=rank)[0] if files else None


def run_ytdlp(item, workdir, cookies_browser):
    """One yt-dlp call: info json + subtitles, no media."""
    vid = item["video_id"]
    tmpl = str(workdir / f"{vid}.%(ext)s")
    cmd = ["yt-dlp", "--skip-download", "--no-warnings", "--no-progress",
           "--write-info-json", "--write-subs", "--write-auto-subs",
           "--sub-format", "vtt", "--sub-langs", "all,-live_chat",
           "--socket-timeout", "30", "-o", tmpl, item["url"]]
    if item["platform"] in ("instagram", "tiktok_cookies") and cookies_browser:
        cmd[1:1] = ["--cookies-from-browser", cookies_browser]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    elapsed = round(time.time() - t0, 1)
    info_path = workdir / f"{vid}.info.json"
    info = json.load(open(info_path)) if info_path.exists() else None
    subs = sorted(glob.glob(str(workdir / f"{vid}.*.vtt")))
    return proc, info, subs, elapsed


def classify_error(stderr):
    s = (stderr or "").lower()
    if "429" in s or "too many requests" in s or "rate-limit" in s or "rate limit" in s:
        return "rate_limited"
    if any(k in s for k in ("nodename nor servname", "name or service not known", "getaddrinfo",
                            "temporary failure in name resolution", "network is unreachable",
                            "connection reset", "connection refused", "timed out", "read timeout",
                            "connection aborted", "remote end closed", "ssl")):
        return "network"
    if "private" in s:
        return "private"
    # TikTok per-post region lock: other posts load fine, cookies don't help
    if "ip address is blocked from accessing this post" in s:
        return "region_blocked"
    if any(k in s for k in ("not available", "removed", "deleted", "404", "does not exist",
                            "unavailable", "status code 10204", "status code 10216")):
        return "deleted_or_unavailable"
    if "login" in s or "cookies" in s or "sign in" in s:
        return "login_required"
    return "other"


def would_route(item, caption, transcript, wpm):
    """What the full (Gemini) pass would do with this video. Spec steps 2–5."""
    steps = []
    if item["group"] == "tiktok_unfiled":
        steps.append("caption_triage")
    folders = {item["folder"], *item.get("collections", [])}
    usable = bool(transcript) and (wpm is None or wpm >= WPM_FLOOR)
    reasons = []
    if not transcript:
        reasons.append("no_transcript")
    elif not usable:
        reasons.append(f"low_wpm<{WPM_FLOOR}")

    if folders & NO_WATCH_FOLDERS:
        reasons.append("veo_no_watch")
        route = "caption_transcript_cover"
    elif folders & VISUAL_FOLDERS:
        reasons.append("visual_folder")
        route = "caption_transcript_cover" if usable else "full_video"
    elif TOOL_NAMES.search(caption or "") and transcript and SCREEN_PHRASES.search(transcript):
        reasons.append("tool_demo")
        route = "full_video"
    elif transcript and not usable:
        route = "full_video"  # music / aesthetic clip with a few stray words
    elif not transcript:
        route = "audio"  # step 4; may escalate to full_video if the audio turns out to be music
    else:
        route = "native_transcript"
    return steps + [route], reasons


def reroute_cached(out):
    """Recompute routes from saved per-video JSONs. No network."""
    results = []
    for p in sorted(out.glob("*.json")):
        if p.name == "summary.json":
            continue
        rec = json.load(open(p))
        old = rec.get("would_route", [])
        if rec.get("ok"):
            rec["would_route"], rec["route_reasons"] = would_route(
                rec, rec.get("caption"), rec.get("transcript"), rec.get("wpm"))
        rec["previous_route"] = old
        with open(p, "w") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        results.append(rec)
    order = {"tiktok_collection": 0, "tiktok_unfiled": 1, "instagram_reel": 2}
    return sorted(results, key=lambda r: order.get(r["group"], 9))


# ───────────────────────── Gemini steps (cost test) ─────────────────────────
# Prices: Gemini 3.8 Flash intro rate to 31 Dec 2026 (secondary sources, check
# ai.google.dev/pricing). One input rate for text/image/audio/video.
PRICE_IN_PER_M = float(os.environ.get("GEMINI_PRICE_IN_PER_M", "0.75"))
PRICE_OUT_PER_M = float(os.environ.get("GEMINI_PRICE_OUT_PER_M", "3.75"))  # incl. thinking
USD_TO_GBP = float(os.environ.get("USD_TO_GBP", "0.79"))
GEMINI_MODEL = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-3.8-flash")
INLINE_LIMIT = 18_000_000  # bytes; bigger media goes through the Files API

TRIAGE_PROMPT = """Toni saved these TikToks. Keep a video only if it matches his interests:
AI and agents, design and branding, building/engineering, business, places, food, art.
Drop memes, gossip, fitness, generic lifestyle and anything off those topics.

Return JSON: [{{"i": <number>, "keep": true|false, "why": "<5 words>"}}] for every item.

{items}"""

AUDIO_PROMPT = """Transcribe the spoken words in this audio verbatim.
If there is no speech, return exactly: [no speech]
If the only vocals are song lyrics (music, singing, a backing track), return exactly: [music]
Otherwise return only the transcript of the speech, ignoring any lyrics."""

VIDEO_PROMPT = """Toni saved this short video. Watch it and return JSON:
{{"shown": "<what is on screen, 1-2 sentences>",
  "transcript": "<speech, verbatim, or empty>",
  "key_ideas": ["<up to 4>"],
  "why_saved": "<best guess, 1 sentence>",
  "tags": ["<3-6 lowercase tags>"]}}
Caption: {caption}"""


class SpendStop(Exception):
    pass


class _SkipTriage(Exception):
    pass


def gemini_call(client, contents, cfg):
    from google.genai import errors
    try:
        reply = client.models.generate_content(model=GEMINI_MODEL, contents=contents, config=cfg)
    except errors.APIError as e:
        code = getattr(e, "code", None)
        msg = str(e)
        if code in (402, 429) or "RESOURCE_EXHAUSTED" in msg or "billing" in msg.lower() \
                or "spend" in msg.lower():
            raise SpendStop(f"{code}: {msg[:200]}")
        raise
    # reply.text can include thought parts; keep only the answer
    parts = (reply.candidates[0].content.parts or []) if reply.candidates else []
    text = "".join(p.text for p in parts if getattr(p, "text", None) and not getattr(p, "thought", False))
    u = reply.usage_metadata
    tin = u.prompt_token_count or 0
    tout = (u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
    usd = tin / 1e6 * PRICE_IN_PER_M + tout / 1e6 * PRICE_OUT_PER_M
    return text or reply.text or "", {"tokens_in": tin, "tokens_out": tout, "usd": round(usd, 6),
                        "gbp": round(usd * USD_TO_GBP, 6)}


def media_part(client, path, mime):
    from google.genai import types
    data = Path(path).read_bytes()
    if len(data) <= INLINE_LIMIT:
        return types.Part.from_bytes(data=data, mime_type=mime), None
    f = client.files.upload(file=str(path))
    while f.state and f.state.name == "PROCESSING":
        time.sleep(3)
        f = client.files.get(name=f.name)
    return f, f.name


def download(rec, workdir, audio_only, cookies_browser):
    vid = rec["video_id"]
    tmpl = str(workdir / f"{vid}.media.%(ext)s")
    cmd = ["yt-dlp", "--no-warnings", "--no-progress", "-o", tmpl, "--socket-timeout", "30"]
    if audio_only:
        cmd += ["-x", "--audio-format", "mp3", "--audio-quality", "5"]
    else:
        cmd += ["-f", "b[height<=720]/bv*[height<=720]+ba/b", "--merge-output-format", "mp4"]
    if rec["platform"] == "instagram" or rec.get("used_cookies"):
        cmd += ["--cookies-from-browser", cookies_browser]
    proc = subprocess.run(cmd + [rec["url"]], capture_output=True, text=True, timeout=300)
    files = [p for p in workdir.glob(f"{vid}.media.*") if not p.name.endswith(".part")]
    if not files and "403" in (proc.stderr or "") and "--cookies-from-browser" not in cmd:
        proc = subprocess.run(cmd + ["--cookies-from-browser", cookies_browser, rec["url"]],
                              capture_output=True, text=True, timeout=300)
        files = [p for p in workdir.glob(f"{vid}.media.*") if not p.name.endswith(".part")]
    if not files:
        raise RuntimeError((proc.stderr or "download failed").strip().splitlines()[-1][:200])
    return files[0]


def cost_test(args, out):
    """--cost-test: Gemini steps on 10 cached Phase 0 videos. Writes nothing to Supabase."""
    from dotenv import load_dotenv
    from google import genai
    from google.genai import types
    load_dotenv(ROOT / ".env")
    sys.path.insert(0, str(ROOT / "scripts"))
    import tag_images  # reuse the existing image tagger's prompt + settings

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg_json = types.GenerateContentConfig(temperature=0, response_mime_type="application/json",
                                           thinking_config=types.ThinkingConfig(thinking_level="low"))
    cfg_text = types.GenerateContentConfig(temperature=0,
                                           thinking_config=types.ThinkingConfig(thinking_level="low"))

    recs = {}
    for p in out.glob("*.json"):
        if p.name != "summary.json":
            r = json.load(open(p))
            recs[r["video_id"]] = r
    raw = out / "raw"
    work = out / "cost_test"
    work.mkdir(exist_ok=True)

    # 10 videos covering every route; one Instagram reel forced to a full watch so
    # we learn what a full watch costs (none of the 20 routes there naturally).
    plan = [
        ("7634582746777603360", "audio"), ("C8Uxp5VAV8o", "audio"),
        ("DAEC980Ja6r", "audio"), ("DC6r5EFoUmR", "audio"),
        ("7512559897481907486", "caption_transcript_cover"),
        ("7515451187001527575", "caption_transcript_cover"),
        ("7515914688425676062", "caption_transcript_cover"),
        ("Czd4PHhA_cE", "full_video (forced)"),
        ("7688848553254423829", "native_transcript"),
        ("7669910082481605910", "native_transcript"),
    ][:args.limit]
    if args.only:
        want = set(args.only.split(","))
        plan = [(v, r) for v, r in plan if v in want]
    unfiled = [r for r in recs.values() if r["group"] == "tiktok_unfiled" and r.get("ok")]

    results, total_usd = [], 0.0
    print(f"Cost test with {GEMINI_MODEL} at ${PRICE_IN_PER_M}/M in, ${PRICE_OUT_PER_M}/M out. "
          f"No Supabase writes.\n")
    try:
        # 1. caption triage: one batch call over the unfiled TikToks
        if args.only:
            raise _SkipTriage
        items = "\n".join(f"{i}. {(r.get('caption') or '').strip()[:300]}" for i, r in enumerate(unfiled, 1))
        text, usage = gemini_call(client, TRIAGE_PROMPT.format(items=items), cfg_json)
        verdicts = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip())
        if isinstance(verdicts, dict):
            verdicts = next((v for v in verdicts.values() if isinstance(v, list)), [])
        total_usd += usage["usd"]
        per_caption = usage["usd"] / max(len(unfiled), 1)
        print(f"caption triage  {len(unfiled)} captions  {usage['tokens_in']}→{usage['tokens_out']} tok  "
              f"${usage['usd']:.5f}  (${per_caption:.6f}/caption)")
        for v in verdicts:
            r = unfiled[int(v["i"]) - 1]
            print(f"    {'KEEP' if v.get('keep') else 'drop'}  {(r.get('caption') or '')[:60]!r}  ({v.get('why')})")
        results.append({"step": "caption_triage", "n": len(unfiled), **usage,
                        "usd_per_caption": round(per_caption, 7), "verdicts": verdicts})
        print()
    except _SkipTriage:
        pass
    except SpendStop as e:
        print(f"\nStopped: Gemini spend cap / quota error: {e}")
        return
    try:
        # cover-tag prompt context, read-only from Supabase, same as tag_images.py
        from supabase import create_client
        sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
        doors = sb.table("door").select("id,label").order("sort").execute().data
        domains = sb.table("domain").select("id,label").order("label").execute().data
        concepts = sb.table("concept").select("slug").execute().data
        tag_ctx = {"doors": "\n".join(f"  {d['id']} — {d['label']}" for d in doors if d["id"] != "cross_door"),
                   "domains": "\n".join(f"  {d['id']}" for d in domains),
                   "concepts": ", ".join(sorted(c["slug"] for c in concepts))}

        import httpx
        http = httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})

        for i, (vid, route) in enumerate(plan, 1):
            r = recs[vid]
            label = f"[{i:>2}/{len(plan)}] {r['platform'][:2]} {r['folder'][:14]:<14} {route:<24}"
            res = {"video_id": vid, "platform": r["platform"], "folder": r["folder"],
                   "route": route, "duration": r.get("duration"), "usd": 0.0, "gbp": 0.0,
                   "tokens_in": 0, "tokens_out": 0}
            uploaded, media = None, None
            try:
                if route == "native_transcript":
                    res["output"] = (r.get("transcript") or "")[:300]
                    res["note"] = "no Gemini call; transcript goes to the weekly tagger as text"
                elif route == "caption_transcript_cover":
                    info = json.load(open(raw / f"{vid}.info.json"))
                    img = http.get(info["thumbnail"])
                    img.raise_for_status()
                    text_ctx = " ".join(f"{r.get('caption') or ''} {r.get('transcript') or ''}".split())
                    prompt = tag_images.PROMPT.format(text=text_ctx[:tag_images.MAX_TEXT_CHARS] or "(none)",
                                                      **tag_ctx)
                    part = types.Part.from_bytes(data=img.content, mime_type="image/jpeg")
                    text, usage = gemini_call(client, [part, prompt], cfg_json)
                    res.update(usage, output=tag_images.parse_json(text))
                elif route == "audio":
                    time.sleep(random.uniform(args.min_sleep, args.max_sleep))
                    media = download(r, work, True, args.cookies_from_browser)
                    part, uploaded = media_part(client, media, "audio/mp3")
                    text, usage = gemini_call(client, [part, AUDIO_PROMPT], cfg_text)
                    text = re.sub(r"^thought\s*", "", text.strip())
                    marker = next((m for m in ("[no speech]", "[music]") if m in text), None)
                    words = 0 if marker else len(text.split())
                    res["audio_result"] = marker.strip("[]").replace(" ", "_") if marker else "speech"
                    res.update(usage, output=text.strip()[:600], transcript_words=words,
                               wpm=round(words / (r["duration"] / 60), 1) if r.get("duration") else None)
                else:  # full_video
                    time.sleep(random.uniform(args.min_sleep, args.max_sleep))
                    media = download(r, work, False, args.cookies_from_browser)
                    res["media_mb"] = round(media.stat().st_size / 1e6, 1)
                    part, uploaded = media_part(client, media, "video/mp4")
                    text, usage = gemini_call(client, [part, VIDEO_PROMPT.format(caption=r.get("caption") or "")],
                                              cfg_json)
                    res.update(usage, output=tag_images.parse_json(text))
            except SpendStop:
                raise
            except Exception as e:
                res["error"] = str(e)[:200]
            finally:
                if media and media.exists():
                    media.unlink()  # spec step 7: delete downloaded media
                if uploaded:
                    try:
                        client.files.delete(name=uploaded)
                    except Exception:
                        pass
            total_usd += res["usd"]
            per_min = res["usd"] / (r["duration"] / 60) if r.get("duration") and res["usd"] else 0
            res["usd_per_minute"] = round(per_min, 6)
            status = f"ERROR {res['error']}" if res.get("error") else \
                f"{res['tokens_in']:>6}→{res['tokens_out']:<5} tok  ${res['usd']:.5f}  (£{res['gbp']:.5f})"
            print(f"{label} {r.get('duration') or '?':>5}s  {status}")
            results.append(res)
    except SpendStop as e:
        print(f"\nStopped: Gemini spend cap / quota error: {e}")

    # projection for the full pass: per-route mean cost × expected counts
    by_route = defaultdict(list)
    for x in results:
        if x.get("route") and not x.get("error"):
            by_route[x["route"].split(" ")[0]].append(x["usd"])
    mean = {k: sum(v) / len(v) for k, v in by_route.items()}
    summary = {"model": GEMINI_MODEL, "price_in_per_m": PRICE_IN_PER_M, "price_out_per_m": PRICE_OUT_PER_M,
               "usd_to_gbp": USD_TO_GBP, "total_usd": round(total_usd, 5),
               "total_gbp": round(total_usd * USD_TO_GBP, 5),
               "mean_usd_per_video_by_route": {k: round(v, 6) for k, v in mean.items()},
               "results": results}
    fname = "cost_summary_rerun.json" if args.only else "cost_summary.json"
    with open(work / fname, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nTotal this run: ${total_usd:.4f} (≈ £{total_usd * USD_TO_GBP:.4f})")
    for k, v in mean.items():
        print(f"  mean {k:<26} ${v:.5f}/video  (£{v * USD_TO_GBP:.5f})")
    print(f"Wrote {work / fname}")


# ───────────────────────── full pass (--run) ─────────────────────────

TRIAGE_BATCH = 50
MAX_GEMINI_SECONDS = 600  # Toni 2026-11-17: never audio-transcribe or watch videos over 10 min
MAX_FULL_TEXT = 8000


def row_item(row):
    url = row["url"]
    raw = row.get("raw_data") or {}
    if "tiktok.com/" in url:
        platform, vid = "tiktok", re.search(r"/(\d{15,})", url).group(1)
    else:
        platform, vid = "instagram", url.rstrip("/").split("/")[-1]
    collections = raw.get("collections") or ([raw["collection"]] if raw.get("collection") else [])
    return {"platform": platform, "video_id": vid, "url": url, "folder": row.get("folder") or "",
            "collections": collections, "kind": raw.get("kind"),
            "group": "tiktok_unfiled" if raw.get("needs_triage") else row["source"]}


def compose_full_text(row, caption, transcript, notes):
    parts = [row.get("full_text") or caption or ""]
    if transcript:
        parts.append(f"Transcript:\n{transcript}")
    if notes:
        if notes.get("shown"):
            parts.append(f"On screen: {notes['shown']}")
        if notes.get("key_ideas"):
            parts.append("Key ideas: " + "; ".join(notes["key_ideas"]))
        if notes.get("why_saved"):
            parts.append(f"Why saved: {notes['why_saved']}")
        if notes.get("tags"):
            parts.append(" ".join(f"#{t.replace(' ', '-')}" for t in notes["tags"]))
    return "\n\n".join(p.strip() for p in parts if p and p.strip())[:MAX_FULL_TEXT] or None


def retry(fn, tries=5):
    """Retry a Supabase call through short network blips."""
    for n in range(tries):
        try:
            return fn()
        except Exception as e:
            if n == tries - 1:
                raise
            print(f"    supabase retry {n + 1}: {str(e)[:80]}")
            time.sleep(10 * (n + 1))


def write_back(sb, row, update, plan_only):
    """Update the inbox row; if it already has a node, refresh it and clear tags/embedding."""
    if plan_only:
        return
    retry(lambda: _write_back(sb, row, update))


def _write_back(sb, row, update):
    update = {**update, "video_processed_at": datetime.now(timezone.utc).isoformat()}
    sb.table("inbox").update(update).eq("id", row["id"]).execute()
    if "full_text" in update or "title" in update or "media_urls" in update:
        node = sb.table("node").select("id").eq("source_table", "inbox") \
            .eq("source_id", str(row["id"])).execute().data
        if node:
            nupd = {"tagged_at": None, "tagged_model": None, "embedding": None, "embedded_at": None}
            if "full_text" in update:
                nupd["body"] = update["full_text"]
            if update.get("title"):
                nupd["title"] = update["title"]
            if "media_urls" in update:
                nupd.update({"image_tagged_at": None, "image_tagged_model": None})
            sb.table("node").update(nupd).eq("id", node[0]["id"]).execute()


def full_pass(args):
    """--run: process inbox rows with video_route='pending'. --plan-only = no Gemini, no writes."""
    from dotenv import load_dotenv
    from google import genai
    from google.genai import types
    from supabase import create_client
    load_dotenv(ROOT / ".env")
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    client = None if args.plan_only else genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg_json = types.GenerateContentConfig(temperature=0, response_mime_type="application/json",
                                           thinking_config=types.ThinkingConfig(thinking_level="low"))
    cfg_text = types.GenerateContentConfig(temperature=0,
                                           thinking_config=types.ThinkingConfig(thinking_level="low"))
    work = Path(os.path.expanduser(args.out)) / "video_pass"
    work.mkdir(parents=True, exist_ok=True)
    rng = random.Random()

    q = sb.table("inbox").select("id,source,folder,url,title,full_text,author_handle,raw_data") \
        .eq("video_route", "pending").order("source_created_at", desc=True)
    if args.source:
        q = q.eq("source", args.source)
    if args.folder:
        folders = [f.strip() for f in args.folder.split(",") if f.strip()]
        q = q.in_("folder", folders) if len(folders) > 1 else q.eq("folder", folders[0])
    rows = q.limit(args.limit).execute().data
    # filed items first; unfiled TikToks go through triage as a batch
    rows.sort(key=lambda r: bool((r.get("raw_data") or {}).get("needs_triage")))
    mode = "PLAN ONLY (no Gemini, no writes)" if args.plan_only else \
        f"RUN (Gemini {GEMINI_MODEL}, writes to inbox, stop at ${args.max_spend_usd})"
    print(f"{mode}: {len(rows)} pending rows\n")

    spent, counts, log = 0.0, Counter(), []

    def charge(usage):
        nonlocal spent
        spent += usage["usd"]
        if spent >= args.max_spend_usd:
            raise SpendStop(f"--max-spend-usd {args.max_spend_usd} reached")

    # Work in chunks of TRIAGE_BATCH so progress is saved as we go.
    consecutive_429, stop = 0, False
    for c0 in range(0, len(rows), TRIAGE_BATCH):
        chunk = rows[c0:c0 + TRIAGE_BATCH]
        # ── A. metadata + native subtitles (free) ──
        metas = []
        try:
            for i, row in enumerate(chunk, c0 + 1):
                item = row_item(row)
                if i > 1:
                    time.sleep(rng.uniform(args.min_sleep, args.max_sleep))
                proc, info, subs, _ = run_ytdlp(item, work, args.cookies_from_browser)
                if not info and proc and item["platform"] == "tiktok" \
                        and classify_error(proc.stderr) == "login_required":
                    time.sleep(rng.uniform(args.min_sleep, args.max_sleep))
                    proc, info, subs, _ = run_ytdlp(dict(item, platform="tiktok_cookies"), work,
                                                    args.cookies_from_browser)
                    item["used_cookies"] = True
                tag = f"[{i:>3}/{len(rows)}] {item['platform'][:2]} {item['folder'][:16]:<16}"
                if not info:
                    err = classify_error(proc.stderr if proc else "")
                    if err in ("rate_limited", "network"):
                        consecutive_429 += 1
                        print(f"{tag} {err} (left pending)")
                        if consecutive_429 >= 3:
                            print(f"Three {err} errors in a row. Stopping; remaining rows stay pending.")
                            stop = True
                            break
                        time.sleep(30)
                        continue  # leave pending, retry next run
                    consecutive_429 = 0
                    if err == "other":
                        counts["left_pending"] += 1
                        print(f"{tag} unknown yt-dlp error, left pending: "
                              f"{(proc.stderr or '').strip().splitlines()[-1][:120] if proc else ''}")
                        continue
                    counts["unavailable"] += 1
                    print(f"{tag} unavailable ({err})")
                    write_back(sb, row, {"video_route": "unavailable",
                                         "video_notes": {"error": err}}, args.plan_only)
                    continue
                consecutive_429 = 0
                sub = pick_sub_file(subs)
                transcript = vtt_to_text(sub) if sub else None
                duration = round(info["duration"], 1) if info.get("duration") else None
                words = len(transcript.split()) if transcript else 0
                metas.append({"row": row, "item": item, "info": info, "transcript": transcript,
                              "duration": duration,
                              "wpm": round(words / (duration / 60), 1) if transcript and duration else None,
                              "caption": info.get("description") or info.get("title") or ""})
                for f in work.glob(f"{item['video_id']}.*"):
                    f.unlink()
        except KeyboardInterrupt:
            print("Interrupted during metadata; processing what was fetched.")
            stop = True

        try:
            # ── B. caption triage for unfiled TikToks (one Gemini call per 50) ──
            unfiled = [m for m in metas if m["item"]["group"] == "tiktok_unfiled"]
            keep_ids = {id(m) for m in metas if m["item"]["group"] != "tiktok_unfiled"}
            for b in range(0, len(unfiled), TRIAGE_BATCH):
                batch = unfiled[b:b + TRIAGE_BATCH]
                if args.plan_only:
                    keep_ids |= {id(m) for m in batch}
                    continue
                items = "\n".join(f"{j}. {m['caption'].strip()[:300] or '(no caption)'}"
                                  for j, m in enumerate(batch, 1))
                text, usage = gemini_call(client, TRIAGE_PROMPT.format(items=items), cfg_json)
                charge(usage)
                verdicts = json.loads(re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip())
                if isinstance(verdicts, dict):
                    verdicts = next((v for v in verdicts.values() if isinstance(v, list)), [])
                keep = {int(v["i"]) for v in verdicts if v.get("keep")}
                for j, m in enumerate(batch, 1):
                    if j in keep:
                        keep_ids.add(id(m))
                    else:
                        counts["triaged_out"] += 1
                        write_back(sb, m["row"], {"video_route": "triaged_out",
                                                  "video_notes": {"caption": m["caption"][:500],
                                                                  "triage_why": next((v.get("why") for v in verdicts
                                                                                      if int(v["i"]) == j), None)}},
                                   False)
                print(f"triage batch {b // TRIAGE_BATCH + 1}: kept {len(keep)}/{len(batch)}  ${usage['usd']:.4f}")

            # ── C. route, Gemini step, write back ──
            for m in [m for m in metas if id(m) in keep_ids]:
                row, item, info = m["row"], m["item"], m["info"]
                transcript, caption = m["transcript"], m["caption"]
                if item.get("kind") == "photo" or not m["duration"]:
                    route, reasons = ["caption_only"], ["no_video"]
                else:
                    route, reasons = would_route(item, caption, transcript, m["wpm"])
                final = route[-1]
                if final in ("audio", "full_video") and (m["duration"] or 0) > MAX_GEMINI_SECONDS:
                    reasons.append("over_10_min")
                    final = "native_transcript" if transcript else "caption_only"
                notes, cost, media, uploaded = None, 0.0, None, None
                try:
                    if final == "audio" and not args.plan_only:
                        time.sleep(rng.uniform(args.min_sleep, args.max_sleep))
                        media = download(item, work, True, args.cookies_from_browser)
                        part, uploaded = media_part(client, media, "audio/mp3")
                        text, usage = gemini_call(client, [part, AUDIO_PROMPT], cfg_text)
                        charge(usage); cost += usage["usd"]
                        text = re.sub(r"^thought\s*", "", text.strip())
                        if "[music]" in text or "[no speech]" in text:
                            reasons.append("audio_" + ("music" if "[music]" in text else "no_speech"))
                            final = "full_video"  # nothing to transcribe: watch it instead
                        else:
                            transcript = text
                        media.unlink(); media = None
                        if uploaded:
                            client.files.delete(name=uploaded); uploaded = None
                    if final == "full_video" and not args.plan_only:
                        time.sleep(rng.uniform(args.min_sleep, args.max_sleep))
                        media = download(item, work, False, args.cookies_from_browser)
                        part, uploaded = media_part(client, media, "video/mp4")
                        text, usage = gemini_call(client, [part, VIDEO_PROMPT.format(caption=caption[:1000])],
                                                  cfg_json)
                        charge(usage); cost += usage["usd"]
                        notes = parse_json_obj(text)
                        if notes.get("transcript") and not transcript:
                            transcript = notes["transcript"]
                except SpendStop:
                    raise
                except Exception as e:
                    reasons.append(f"error: {str(e)[:120]}")
                    print(f"    error on {item['video_id']}: {str(e)[:120]}")
                    if final in ("audio", "full_video") and not transcript and not notes:
                        continue  # leave pending; retry next run
                finally:
                    if media and media.exists():
                        media.unlink()
                    if uploaded:
                        try:
                            client.files.delete(name=uploaded)
                        except Exception:
                            pass

                update = {"video_route": final,
                          "video_notes": {"caption": caption[:2000], "creator": info.get("uploader"),
                                          "creator_id": info.get("uploader_id") or info.get("channel_id"),
                                          "duration": m["duration"], "view_count": info.get("view_count"),
                                          "upload_date": info.get("upload_date"),
                                          "transcript": transcript, "wpm": m["wpm"], "notes": notes,
                                          "reasons": reasons, "cost_usd": round(cost, 6),
                                          "model": GEMINI_MODEL if cost else None}}
                ft = compose_full_text(row, caption, transcript, notes)
                if ft and ft != row.get("full_text"):
                    update["full_text"] = ft
                if not row.get("title"):
                    t = next((ln.strip() for ln in caption.splitlines() if ln.strip()), None) \
                        or (notes or {}).get("shown")
                    if t:
                        update["title"] = t[:200]
                # TikTok: uploader = @handle, uploader_id = numeric. Instagram: channel = username.
                handle = info.get("uploader") if item["platform"] == "tiktok" else \
                    (info.get("channel") or info.get("uploader_id"))
                if not row.get("author_handle") and handle:
                    update["author_handle"] = handle
                if final in ("caption_transcript_cover", "caption_only") and info.get("thumbnail"):
                    update["media_urls"] = [info["thumbnail"]]  # tag_images.py tags it
                write_back(sb, row, update, args.plan_only)
                counts[final] += 1
                log.append({"id": row["id"], "folder": item["folder"], "route": final, "cost_usd": cost})
                print(f"  {item['platform'][:2]} {item['folder'][:16]:<16} {m['duration'] or '?':>5}s  "
                      f"{' → '.join(route[:-1] + [final]):<40} ${cost:.4f}")
        except SpendStop as e:
            print(f"\nStopped: {e}. Remaining rows stay pending.")
            stop = True
        if stop:
            break

    print(f"\nRoutes: {dict(counts)}")
    print(f"Spent ${spent:.4f} (≈ £{spent * USD_TO_GBP:.4f})")
    if counts.get("caption_transcript_cover") or counts.get("caption_only"):
        print("Thumbnails expire within days: run `python scripts/tag_images.py --all` soon "
              "so the cover tags get done while the image URLs still load.")
    with open(work / f"run_{datetime.now():%Y%m%d_%H%M%S}.json", "w") as f:
        json.dump({"spent_usd": spent, "counts": counts, "plan_only": args.plan_only, "rows": log},
                  f, indent=2)


def parse_json_obj(text):
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    a, b = t.find("{"), t.rfind("}")
    return json.loads(t[a:b + 1]) if a >= 0 and b > a else {}


# ───────────────────────── main ─────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ytdlp-only", action="store_true", help="Phase 0: no Gemini, no Supabase")
    ap.add_argument("--reroute-cached", action="store_true",
                    help="recompute routes from JSONs already in --out (no network)")
    ap.add_argument("--run", action="store_true",
                    help="full pass over inbox rows with video_route='pending' (Gemini + writes)")
    ap.add_argument("--plan-only", action="store_true", help="--run without Gemini or writes")
    ap.add_argument("--max-spend-usd", type=float, default=1.50)
    ap.add_argument("--source", help="--run: only this inbox.source")
    ap.add_argument("--folder", help="--run: only these inbox.folder values (comma-separated)")
    ap.add_argument("--only", help="cost test: comma-separated video ids to re-run (skips triage)")
    ap.add_argument("--cost-test", action="store_true",
                    help="Gemini steps on up to 10 cached Phase 0 videos; prints cost per video. "
                         "No Supabase writes.")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", default=str(DEFAULT_EXPORTS))
    ap.add_argument("--ig-saves", default=str(DEFAULT_EXPORTS / "instagram_saves"))
    ap.add_argument("--tiktok", default=str(DEFAULT_EXPORTS / "tiktok" / "user_data_tiktok.json"))
    ap.add_argument("--tiktok-collections", default=str(ROOT / "social_ingest" / "tiktok_collections_2026-11-15.json"))
    ap.add_argument("--tiktok-ai", default=str(ROOT / "social_ingest" / "tiktok_ai_learning_collection_2026-11-15.json"))
    ap.add_argument("--cookies-from-browser", default="chrome")
    ap.add_argument("--seed", type=int, default=20261115)
    ap.add_argument("--min-sleep", type=float, default=3.0)
    ap.add_argument("--max-sleep", type=float, default=8.0)
    args = ap.parse_args()

    out = Path(os.path.expanduser(args.out))

    if args.cost_test:
        cost_test(args, out)
        return

    if args.run:
        full_pass(args)
        return

    if args.reroute_cached:
        results = reroute_cached(out)
        print("Re-routing cached Phase 0 results. No yt-dlp, no Gemini, no Supabase.\n")
        for r in results:
            print(f"{r['platform'][:2]} {r['folder'][:16]:<16} {str(r.get('wpm')):>6} wpm  "
                  f"{' → '.join(r.get('previous_route', []))[:34]:<34} ⇒ {' → '.join(r['would_route']):<40} "
                  f"{','.join(r.get('route_reasons') or [])}")
        summarise(results, out, rerouted=True)
        return

    if not args.ytdlp_only:
        sys.exit("Only Phase 0 is built. Run with --ytdlp-only. Gemini steps wait for Toni's go-ahead.")

    raw = out / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)

    # 50% TikTok collections, 25% unfiled TikTok, 25% IG reels (10/5/5 at limit 20)
    n_coll = args.limit // 2
    n_unf = (args.limit - n_coll) // 2
    n_ig = args.limit - n_coll - n_unf

    coll_picks, coll_ids = pick_tiktok_collections(args.tiktok_collections, args.tiktok_ai, n_coll, rng)
    unf_picks, unf_pool = pick_tiktok_unfiled(args.tiktok, coll_ids, n_unf, rng)
    ig_picks, ig_pool = pick_instagram_reels(args.ig_saves, n_ig, rng)
    items = coll_picks + unf_picks + ig_picks
    print(f"Sample: {len(coll_picks)} TikTok collection, {len(unf_picks)} unfiled TikTok "
          f"(pool {unf_pool}), {len(ig_picks)} IG reels (pool {ig_pool})")
    print("Phase 0: yt-dlp only. No Gemini. No Supabase.\n")

    results, consecutive_429 = [], 0
    for i, item in enumerate(items, 1):
        if i > 1:
            time.sleep(rng.uniform(args.min_sleep, args.max_sleep))
        label = f"[{i:>2}/{len(items)}] {item['platform']:<9} {item['folder'][:16]:<16} {item['video_id']}"
        try:
            proc, info, subs, elapsed = run_ytdlp(item, raw, args.cookies_from_browser)
        except subprocess.TimeoutExpired:
            proc, info, subs, elapsed = None, None, [], 180.0
        if (not info and proc and item["platform"] == "tiktok" and args.cookies_from_browser
                and classify_error(proc.stderr) == "login_required"):
            print(f"{label}  login wall, retrying with {args.cookies_from_browser} cookies")
            time.sleep(rng.uniform(args.min_sleep, args.max_sleep))
            proc, info, subs, elapsed = run_ytdlp(dict(item, platform="tiktok_cookies"), raw,
                                                  args.cookies_from_browser)
            rec_cookies = True
        else:
            rec_cookies = item["platform"] == "instagram"

        rec = dict(item)
        rec["fetched_at"] = datetime.now(timezone.utc).isoformat()
        rec["ytdlp_seconds"] = elapsed
        rec["used_cookies"] = rec_cookies
        if info:
            consecutive_429 = 0
            caption = info.get("description") or info.get("title")
            sub_file = pick_sub_file(subs)
            transcript = vtt_to_text(sub_file) if sub_file else None
            duration = round(info["duration"], 1) if info.get("duration") else None
            words = len(transcript.split()) if transcript else 0
            wpm = round(words / (duration / 60), 1) if transcript and duration else None
            route, reasons = would_route(item, caption, transcript, wpm)
            rec.update({
                "ok": True, "error": None,
                "caption": caption,
                "creator": info.get("uploader") or info.get("channel") or info.get("creator"),
                "creator_id": info.get("uploader_id") or info.get("channel_id"),
                "duration": duration,
                "view_count": info.get("view_count"),
                "like_count": info.get("like_count"),
                "upload_date": info.get("upload_date"),
                "webpage_url": info.get("webpage_url"),
                "subtitle_langs_available": sorted(set((info.get("subtitles") or {}).keys())
                                                   | set((info.get("automatic_captions") or {}).keys())),
                "subtitle_file": os.path.basename(sub_file) if sub_file else None,
                "transcript": transcript,
                "transcript_words": words,
                "wpm": wpm,
                "would_route": route,
                "route_reasons": reasons,
            })
            print(f"{label}  ok  {duration or '?'}s  "
                  f"{'transcript ' + str(words) + 'w' if transcript else 'no transcript'}  → {route[-1]}")
        else:
            stderr = (proc.stderr if proc else "timeout").strip()
            kind = classify_error(stderr)
            rec.update({"ok": False, "error": kind,
                        "error_detail": stderr.splitlines()[-1][:300] if stderr else None,
                        "would_route": ["skip"]})
            print(f"{label}  FAIL {kind}: {rec['error_detail']}")
            consecutive_429 = consecutive_429 + 1 if kind == "rate_limited" else 0
            if consecutive_429 >= 3:
                print("\nThree 429s in a row. Stopping.")
                results.append(rec)
                break

        with open(out / f"{item['platform']}_{item['video_id']}.json", "w") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        results.append(rec)

    summarise(results, out)


def summarise(results, out, rerouted=False):
    def stats(rs):
        ok = [r for r in rs if r["ok"]]
        tr = [r for r in ok if r.get("transcript")]
        return {"attempted": len(rs), "metadata": len(ok), "native_transcript": len(tr),
                "failed": len(rs) - len(ok)}

    by_group = {}
    for r in results:
        by_group.setdefault(r["group"], []).append(r)
    routes = {}
    for r in results:
        routes[r["would_route"][-1]] = routes.get(r["would_route"][-1], 0) + 1
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "phase": "0 (yt-dlp only, no Gemini, no Supabase)" + (", re-routed from cache" if rerouted else ""),
        "yt_dlp_version": subprocess.run(["yt-dlp", "--version"], capture_output=True, text=True).stdout.strip(),
        "totals": stats(results),
        "by_platform": {p: stats([r for r in results if r["platform"] == p]) for p in ("tiktok", "instagram")},
        "by_group": {g: stats(rs) for g, rs in by_group.items()},
        "failures": {k: sum(1 for r in results if r.get("error") == k)
                     for k in {r.get("error") for r in results if r.get("error")}},
        "would_route_counts": routes,
        "gemini_calls_in_full_pass": {
            "caption_triage_batches": 1 if any("caption_triage" in r["would_route"] for r in results) else 0,
            "audio_transcribe": routes.get("audio", 0),
            "full_video_watch": routes.get("full_video", 0),
            "cover_image_tag": routes.get("caption_transcript_cover", 0),
        },
        "videos": [{
            "platform": r["platform"], "folder": r["folder"], "id": r["video_id"], "ok": r["ok"],
            "duration": r.get("duration"), "transcript_words": r.get("transcript_words"),
            "wpm": r.get("wpm"), "route": " → ".join(r["would_route"]),
            "reasons": r.get("route_reasons"), "error": r.get("error"),
            "caption": (r.get("caption") or r.get("scraped_caption") or "")[:90],
        } for r in results],
    }
    with open(out / "summary.json", "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print("\n──────── Summary ────────")
    for p, s in summary["by_platform"].items():
        print(f"{p:<10} attempted {s['attempted']:>2}  metadata {s['metadata']:>2}  "
              f"native transcript {s['native_transcript']:>2}  failed {s['failed']:>2}")
    print(f"Failures: {summary['failures'] or 'none'}")
    print(f"Would route: {routes}")
    print(f"\nWrote {len(results)} video JSONs + summary.json to {out}")


if __name__ == "__main__":
    main()
