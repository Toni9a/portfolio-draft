#!/usr/bin/env python3
"""
ingest_social.py — load Instagram + TikTok saves into `inbox`, and algorithm
snapshots into `algo_snapshot`.
Spec: social_ingest/social_ingest_spec_2026-11-15.md

    python3 scripts/ingest_social.py \
        --ig-saves ~/Downloads/social_exports/instagram_saves \
        --ig-algo  ~/Downloads/social_exports/instagram_algo \
        --tiktok   ~/Downloads/social_exports/tiktok/user_data_tiktok.json \
        --tiktok-collections social_ingest/tiktok_collections_2026-11-15.json \
        --dry-run

--dry-run parses everything, prints counts per source/folder plus 5 sample
rows, and writes nothing. --apply writes (insert-only, never updates or deletes);
--apply --limit N writes only the first N inbox rows as a test. Reels and TikToks
land with video_route='pending' so sync_captures.py holds them until
watch_videos.py --run has added their transcript.

inbox facts (checked via Supabase MCP 2026-11-17): unique key is `url` alone
(inbox_url_unique), so rows dedupe on normalised URL across every source.
Self-chat notes have no URL; they carry source_item_id instead, made unique for
the social sources by migration 20261117000100_inbox_social_source_item_unique.sql
(partial index, so the write path must skip source_item_ids that already exist
rather than rely on ON CONFLICT).
"""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

IG_DROP_COLLECTIONS = {"Fitness stretch", "Safto", "MK", "Temi Teeeth", "Tennis", "Food ldn"}
IG_ALWAYS_KEEP = {"Aesth", "Patrick bs"}
CUTOFF_2022 = datetime(2022, 1, 1, tzinfo=timezone.utc)
TT_UNFILED_CUTOFF = "2025-01-01"
SELFCHAT_THREAD = "toni_560975108639336"
IGNORE_THREADS = {"oluwatoni_1193254748744699"}  # a different person; never opened
IG_PLACEHOLDER = "You sent an attachment."
# Demographic ad labels are personal, not interest signal (spec: "don't load anything personal")
PERSONAL_CATEGORY = re.compile(r"^(relationship status|education level|age|gender|household|income|"
                               r"parents|life events|job title|employer)\b", re.I)
EXPECT = {"instagram_save": 167, "instagram_selfchat": 214}


# ───────────────────────── helpers ─────────────────────────

def fix(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def ts(sec):
    return datetime.fromtimestamp(sec, timezone.utc)


def tt_id(url):
    m = re.search(r"/(?:video|photo|v)/(\d{15,})", url or "")
    return m.group(1) if m else None


def tt_handle(url):
    m = re.search(r"tiktok\.com/@([^/]+)/", url or "")
    return m.group(1) if m and m.group(1) != "_" else None


def norm_url(url):
    """Normalise any IG/TikTok link so dupes collapse. Others: strip query."""
    if not url:
        return None
    vid = tt_id(url) if "tiktok" in url else None
    if vid:
        return f"https://www.tiktok.com/@_/video/{vid}"
    if "instagram.com" in url:
        m = re.search(r"instagram\.com/(?:[^/]+/)?(p|reel|reels|tv)/([^/?#]+)", url)
        if m:
            kind = "reel" if m.group(1) in ("reel", "reels") else m.group(1)
            return f"https://www.instagram.com/{kind}/{m.group(2)}/"
    return url.split("?")[0]


def walk(label_values):
    """Recursive walker for Instagram {label_values:[...]} records."""
    out = {"hashtags": [], "owner": None, "owner_name": None}
    for lv in label_values or []:
        title = lv.get("title")
        if "dict" in lv and title == "Hashtags":
            for d in lv["dict"]:
                for x in d.get("dict", []):
                    if x.get("label") == "Name":
                        out["hashtags"].append(fix(x.get("value")))
        elif "dict" in lv and title == "Owner":
            for d in lv["dict"]:
                for x in d.get("dict", []):
                    if x.get("label") == "Username":
                        out["owner"] = fix(x.get("value"))
                    elif x.get("label") == "Name":
                        out["owner_name"] = fix(x.get("value"))
        elif "dict" in lv and title in (None, "", "Media"):
            # nested post (see-more / not-interested files wrap the post one level down)
            for d in lv["dict"]:
                inner = walk(d.get("dict", []))
                for k, v in inner.items():
                    if v and not out.get(k):
                        out[k] = v
        elif "label" in lv:
            out[lv["label"].lower()] = fix(lv.get("value"))
    return out


def first_line(s, n=200):
    for line in (s or "").splitlines():
        line = line.strip()
        if line:
            return line[:n]
    return None


def compose_text(text, handle=None, hashtags=None):
    parts = [text.strip()] if text and text.strip() else []
    if handle:
        parts.append(f"by @{handle}")
    tags = [h for h in (hashtags or []) if h and f"#{h}" not in (text or "")]
    if tags:
        parts.append(" ".join(f"#{h}" for h in tags))
    return "\n\n".join(parts) or None


def load_list(path):
    d = json.load(open(path))
    if isinstance(d, dict):
        vals = [v for v in d.values() if isinstance(v, list)]
        return vals[0] if vals else []
    return d


# ───────────────────────── A. Instagram saves ─────────────────────────

def instagram_saves(ig_dir):
    saved = json.load(open(ig_dir / "saved" / "saved_posts.json"))
    colls = json.load(open(ig_dir / "saved" / "saved_collections.json"))
    url_colls = defaultdict(set)
    for c in colls:
        name = next((fix(lv.get("value")) for lv in c["label_values"] if lv.get("label") == "Name"), None)
        for lv in c["label_values"]:
            for d in lv.get("dict", []) or []:
                f = walk(d.get("dict", []))
                if f.get("url"):
                    url_colls[norm_url(f["url"])].add(name)
    rows, dropped = [], Counter()
    for p in saved:
        f = walk(p["label_values"])
        url = norm_url(f.get("url"))
        cs = url_colls.get(url, set())
        saved_at = ts(p["timestamp"])
        if cs & IG_ALWAYS_KEEP:
            pass
        elif saved_at < CUTOFF_2022:
            dropped["before_2022"] += 1
            continue
        elif cs & IG_DROP_COLLECTIONS:
            dropped["dropped_collection"] += 1
            continue
        keep_first = sorted(cs & IG_ALWAYS_KEEP) + sorted(cs - IG_ALWAYS_KEEP)
        caption = f.get("caption")
        rows.append({
            "source": "instagram_save",
            "folder": keep_first[0] if keep_first else "Instagram saves",
            "url": url,
            "source_item_id": url.rstrip("/").split("/")[-1],
            "title": first_line(caption) or (f"@{f['owner']} reel" if f.get("owner") else None),
            "full_text": compose_text(caption, f.get("owner"), f.get("hashtags")),
            "author_name": f.get("owner_name"),
            "author_handle": f.get("owner"),
            "source_created_at": saved_at.isoformat(),
            "raw_data": {"kind": "reel" if "/reel/" in url else "post",
                         "collections": sorted(cs), "hashtags": f.get("hashtags"),
                         "origins": ["instagram_save"]},
        })
    return rows, dropped


# ───────────────────────── B. Instagram self-chat ─────────────────────────

def instagram_selfchat(ig_dir):
    thread = ig_dir / "messages" / "inbox" / SELFCHAT_THREAD / "message_1.json"
    assert SELFCHAT_THREAD not in IGNORE_THREADS
    m = json.load(open(thread))
    participants = [fix(p["name"]) for p in m["participants"]]
    if participants != ["Toni"]:
        sys.exit(f"Self-chat thread has unexpected participants {participants}; stopping.")
    rows, kinds, skipped = [], Counter(), Counter()
    for msg in m["messages"]:
        sent = datetime.fromtimestamp(msg["timestamp_ms"] / 1000, timezone.utc)
        if sent < CUTOFF_2022:
            skipped["before_2022"] += 1
            continue
        content = fix(msg.get("content"))
        if content == IG_PLACEHOLDER:
            content = None
        share = msg.get("share") or {}
        photos = msg.get("photos") or []
        sid = f"ig_selfchat_{msg['timestamp_ms']}"
        base = {"source": "instagram_selfchat", "folder": "Instagram self-chat",
                "source_item_id": sid, "source_created_at": sent.isoformat()}
        if share.get("link") or share.get("share_text"):
            kinds["share"] += 1
            text = fix(share.get("share_text"))
            owner = fix(share.get("original_content_owner"))
            rows.append({**base,
                         "url": norm_url(share.get("link")),
                         "title": first_line(content) or first_line(text),
                         "full_text": compose_text("\n\n".join(x for x in (content, text) if x), owner),
                         "author_handle": owner,
                         "my_note": content,
                         "raw_data": {"kind": "share", "share_link": share.get("link"),
                                      "origins": ["instagram_selfchat"]}})
        elif photos:
            kinds["photo"] += 1
            rows.append({**base, "url": None, "title": first_line(content) or "Self-chat photo",
                         "full_text": content, "media_urls": [p.get("uri") for p in photos],
                         "raw_data": {"kind": "photo", "origins": ["instagram_selfchat"]}})
        elif content:
            kinds["note"] += 1
            rows.append({**base, "url": None, "title": first_line(content), "full_text": content,
                         "my_note": content,
                         "raw_data": {"kind": "note", "origins": ["instagram_selfchat"]}})
        else:
            kinds["empty (media not in export)"] += 1
    return rows, kinds, skipped


# ───────────────────────── C. TikTok favourites ─────────────────────────

def tiktok(tiktok_file, coll_file):
    data = json.load(open(tiktok_file))
    favs = data["Likes and Favorites"]["Favorite Videos"]["FavoriteVideoList"]
    fav_date = {}
    for f in favs:
        vid = tt_id(f.get("Link"))
        if vid and vid not in fav_date:
            fav_date[vid] = f["Date"]

    coll = json.load(open(coll_file))["collections"]
    coll_items = []  # (folder, url, caption)
    for name, c in coll.items():
        if c.get("items_file"):
            for url, cap in json.load(open(ROOT / c["items_file"]))["items"]:
                coll_items.append((name, url, cap))
        for url in c.get("items", []):
            coll_items.append((name, url, None))

    rows, seen, matched = [], set(), 0
    for folder, url, cap in coll_items:
        vid = tt_id(url)
        if vid in seen:
            continue
        seen.add(vid)
        saved = fav_date.get(vid)
        matched += bool(saved)
        rows.append({
            "source": "tiktok_save", "folder": folder, "url": norm_url(url), "source_item_id": vid,
            "title": first_line(cap) if cap else None,
            "full_text": compose_text(cap, tt_handle(url)) if cap else None,
            "author_handle": tt_handle(url),
            "source_created_at": f"{saved}+00:00".replace(" ", "T") if saved else None,
            "raw_data": {"kind": "photo" if "/photo/" in url else "video", "collection": folder,
                         "scraped_url": url, "in_favourites_export": bool(saved),
                         "needs_triage": False, "origins": ["tiktok_collection"]},
        })
    n_coll = len(rows)

    unfiled_old = 0
    for vid, saved in fav_date.items():
        if vid in seen:
            continue
        if saved < TT_UNFILED_CUTOFF:
            unfiled_old += 1
            continue
        seen.add(vid)
        rows.append({
            "source": "tiktok_save", "folder": "TikTok saves", "url": f"https://www.tiktok.com/@_/video/{vid}",
            "source_item_id": vid, "title": None, "full_text": None,
            "source_created_at": f"{saved}+00:00".replace(" ", "T"),
            "raw_data": {"kind": "video", "needs_triage": True, "origins": ["tiktok_favourite"]},
        })
    stats = {"favourites_in_export": len(favs), "unique_favourites": len(fav_date),
             "collection_items": n_coll, "collection_items_matched_in_export": matched,
             "unfiled_2025_plus": len(rows) - n_coll, "unfiled_pre_2025_skipped": unfiled_old}
    return rows, stats


# ───────────────────────── D. algorithm snapshots ─────────────────────────

def algo_snapshots(ig_algo, tiktok_file, snapshot_date):
    snaps, seemore = [], []

    def add(platform, kind, url, caption=None, owner=None, hashtags=None, raw=None):
        snaps.append({"platform": platform, "snapshot_date": snapshot_date, "kind": kind,
                      "url": url, "caption": caption, "owner": owner,
                      "hashtags": hashtags or [], "raw": raw})

    if ig_algo:
        at = ig_algo / "ads_information" / "ads_and_topics"
        ab = ig_algo / "ads_information" / "instagram_ads_and_businesses"
        for fname, kind in (("videos_watched.json", "video_watched"),
                            ("posts_viewed.json", "post_viewed"),
                            ("posts_you're_not_interested_in.json", "not_interested")):
            p = at / fname
            if not p.exists():
                continue
            for rec in load_list(p):
                f = walk(rec.get("label_values"))
                add("instagram", kind, norm_url(f.get("url")), f.get("caption"), f.get("owner"),
                    f.get("hashtags"), {"timestamp": rec.get("timestamp")})
        for p in (at / "other_categories_used_to_reach_you.json", ab / "other_categories_used_to_reach_you.json"):
            if p.exists():
                d = json.load(open(p))
                for rec in (d if isinstance(d, list) else [d]):
                    for lv in rec.get("label_values", []):
                        for v in lv.get("vec", []) or []:
                            cat = fix(v.get("value"))
                            if cat and not PERSONAL_CATEGORY.match(cat):
                                add("instagram", "ad_category", None, cat)
        p = at / "posts_you're_interested_or_not_interested_in.json"
        if p.exists():
            for rec in load_list(p):
                f = walk(rec.get("label_values"))
                fb = (f.get("feedback") or "").lower()
                url = norm_url(f.get("url"))
                if fb == "see more" and url:
                    seemore.append({
                        "source": "instagram_seemore", "folder": "Instagram see more", "url": url,
                        "source_item_id": url.rstrip("/").split("/")[-1],
                        "title": first_line(f.get("caption")),
                        "full_text": compose_text(f.get("caption"), f.get("owner"), f.get("hashtags")),
                        "author_handle": f.get("owner"),
                        "source_created_at": ts(rec["timestamp"]).isoformat(),
                        "raw_data": {"kind": "reel" if "/reel/" in url else "post",
                                     "surface": f.get("surface"), "origins": ["instagram_seemore"]}})
                elif url:
                    add("instagram", "see_less", url, f.get("caption"), f.get("owner"), f.get("hashtags"))

    if tiktok_file:
        t = json.load(open(tiktok_file))
        ya = t["Your Activity"]
        for rec in ya.get("Watch History", {}).get("VideoList", []):
            add("tiktok", "watched", norm_url(rec.get("Link")), raw={"date": rec.get("Date")})
        for rec in ya.get("Searches", {}).get("SearchList", []):
            add("tiktok", "search", None, rec.get("SearchTerm"), raw={"date": rec.get("Date")})
        for rec in ya.get("Share History", {}).get("ShareHistoryList", []):
            add("tiktok", "shared", norm_url(rec.get("Link")), raw={"date": rec.get("Date"),
                                                                      "method": rec.get("Method")})
        for rec in ya.get("Reposts", {}).get("RepostList", []):
            add("tiktok", "reposted", norm_url(rec.get("Link")), raw={"date": rec.get("Date")})
        for rec in t["Likes and Favorites"].get("Like List", {}).get("ItemFavoriteList", []):
            add("tiktok", "liked", norm_url(rec.get("link")), raw={"date": rec.get("date")})

    # unique (platform, kind, url, snapshot_date); url-less rows dedupe on owner, then caption.
    # The table's unique key needs the same: store "owner:<handle>" / "search:<term>" in url
    # or use a generated identity column. Decided in the migration.
    uniq = {}
    for s in snaps:
        ident = s["url"] or (f"owner:{s['owner']}" if s["owner"] else f"text:{s['caption']}")
        key = (s["platform"], s["kind"], ident, s["snapshot_date"])
        uniq.setdefault(key, s)
    return list(uniq.values()), len(snaps), seemore


# ───────────────────────── main ─────────────────────────

def dedupe(rows):
    """Collapse rows sharing a URL; first wins, origins merged."""
    by_url, out, merged = {}, [], 0
    for r in rows:
        u = r.get("url")
        if u and u in by_url:
            keep = by_url[u]
            keep["raw_data"]["origins"] = sorted(set(keep["raw_data"]["origins"]) | set(r["raw_data"]["origins"]))
            if r.get("my_note") and not keep.get("my_note"):
                keep["my_note"] = r["my_note"]
            merged += 1
            continue
        if u:
            by_url[u] = r
        out.append(r)
    return out, merged


# ───────────────────────── writing ─────────────────────────

SOCIAL_SOURCES = ["instagram_save", "instagram_selfchat", "instagram_seemore", "tiktok_save"]
INBOX_COLS = {"source", "folder", "url", "source_item_id", "title", "full_text", "author_name",
              "author_handle", "media_urls", "my_note", "source_created_at", "raw_data", "video_route"}


def needs_video_pass(r):
    """Reels and TikToks wait for watch_videos.py; posts and notes sync straight away."""
    u = r.get("url") or ""
    return "tiktok.com/" in u or "/reel/" in u


def supabase_client():
    import os
    from dotenv import load_dotenv
    from supabase import create_client
    load_dotenv(ROOT / ".env")
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def fetch_col(sb, table, cols, **flt):
    out, off = [], 0
    while True:
        q = sb.table(table).select(cols)
        for k, v in flt.items():
            q = q.in_(k, v) if isinstance(v, list) else q.eq(k, v)
        page = q.order("id").range(off, off + 999).execute().data
        out += page
        if len(page) < 1000:
            return out
        off += 1000


def write_inbox(sb, rows):
    """Insert-only. URL rows: upsert ignore-duplicates on inbox_url_unique.
    URL-less rows: skip source_item_ids already present (index inbox_social_source_item_unique
    is partial, so ON CONFLICT can't target it). Never updates or deletes existing rows."""
    rows = [{k: v for k, v in r.items() if k in INBOX_COLS and v is not None} for r in rows]
    have_urls = {r["url"] for r in fetch_col(sb, "inbox", "url") if r.get("url")}
    have_ids = {(r["source"], r["source_item_id"])
                for r in fetch_col(sb, "inbox", "source,source_item_id", source=SOCIAL_SOURCES)}
    with_url = [r for r in rows if r.get("url") and r["url"] not in have_urls]
    no_url = [r for r in rows if not r.get("url")
              and (r["source"], r["source_item_id"]) not in have_ids]
    skipped = len(rows) - len(with_url) - len(no_url)
    written = 0
    for i in range(0, len(with_url), 200):
        chunk = with_url[i:i + 200]
        sb.table("inbox").upsert(chunk, on_conflict="url", ignore_duplicates=True).execute()
        written += len(chunk)
    for i in range(0, len(no_url), 200):
        chunk = no_url[i:i + 200]
        sb.table("inbox").insert(chunk).execute()
        written += len(chunk)
    print(f"\ninbox: wrote {written} new rows ({len(with_url)} with url, {len(no_url)} notes), "
          f"skipped {skipped} already present")


def write_algo(sb, snaps):
    """Upsert ignore-duplicates on (platform, kind, ident, snapshot_date)."""
    n = 0
    for i in range(0, len(snaps), 1000):
        sb.table("algo_snapshot").upsert(snaps[i:i + 1000], ignore_duplicates=True,
                                         on_conflict="platform,kind,ident,snapshot_date").execute()
        n += len(snaps[i:i + 1000])
        print(f"\ralgo_snapshot: {n}/{len(snaps)}", end="", flush=True)
    print(f"\nalgo_snapshot: sent {n} rows (existing ones ignored)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ig-saves", type=Path)
    ap.add_argument("--ig-algo", type=Path)
    ap.add_argument("--tiktok", type=Path)
    ap.add_argument("--tiktok-collections", type=Path,
                    default=ROOT / "social_ingest" / "tiktok_collections_2026-11-15.json")
    ap.add_argument("--snapshot-date", default=date.today().isoformat())
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="counts + samples, write nothing")
    mode.add_argument("--apply", action="store_true", help="write to inbox and algo_snapshot")
    ap.add_argument("--limit", type=int, help="--apply: write at most N inbox rows (first test)")
    ap.add_argument("--skip-algo", action="store_true", help="--apply: don't write algo_snapshot")
    ap.add_argument("--samples", type=int, default=5)
    args = ap.parse_args()

    rows, notes = [], []
    if args.ig_saves:
        r, dropped = instagram_saves(args.ig_saves.expanduser())
        notes.append(f"instagram_save: kept {len(r)}, dropped {dict(dropped)}")
        rows += r
    if args.tiktok:
        r, st = tiktok(args.tiktok.expanduser(), args.tiktok_collections)
        notes.append(f"tiktok: {st}")
        rows += r
    if args.ig_saves:
        r, kinds, skipped = instagram_selfchat(args.ig_saves.expanduser())
        notes.append(f"instagram_selfchat: {len(r)} rows {dict(kinds)}, skipped {dict(skipped)}")
        rows += r
    snaps, snaps_raw, seemore = algo_snapshots(
        args.ig_algo.expanduser() if args.ig_algo else None,
        args.tiktok.expanduser() if args.tiktok else None, args.snapshot_date)
    rows += seemore

    pre = Counter(r["source"] for r in rows)
    rows, merged = dedupe(rows)
    for r in rows:
        r["video_route"] = "pending" if needs_video_pass(r) else None

    print("DRY RUN: nothing written.\n" if args.dry_run else "APPLY: writing to Supabase.\n")
    for n in notes:
        print(n)
    print(f"cross-source URL dupes merged: {merged}\n")

    print("── inbox rows by source / folder ──")
    by = defaultdict(Counter)
    for r in rows:
        by[r["source"]][r["folder"]] += 1
    for src in sorted(by):
        tot = sum(by[src].values())
        exp = EXPECT.get(src)
        flag = ""
        if exp and abs(pre[src] - exp) > exp * 0.1:
            flag = f"  ⚠ expected ~{exp}"
        print(f"{src:<20} {tot:>4}  (before dedupe {pre[src]}){flag}")
        for folder, n in by[src].most_common():
            print(f"    {folder:<28} {n:>4}")
    print(f"{'TOTAL':<20} {len(rows):>4}")
    print(f"held for the video pass (video_route=pending): "
          f"{sum(1 for r in rows if r['video_route'] == 'pending')}")
    no_url = sum(1 for r in rows if not r.get("url"))
    print(f"rows with no url (notes): {no_url}  ← deduped on (source, source_item_id), "
          f"needs migration 20261117000100\n")

    for src, exp in EXPECT.items():
        if pre[src] and abs(pre[src] - exp) > exp * 0.25:
            sys.exit(f"{src} count {pre[src]} is far off the expected {exp}; stopping.")

    print("── algo_snapshot rows (separate table, not synced to node) ──")
    sc = Counter((s["platform"], s["kind"]) for s in snaps)
    for (p, k), n in sorted(sc.items()):
        print(f"    {p:<10} {k:<16} {n:>7}")
    print(f"    unique {len(snaps)} of {snaps_raw} raw records\n")

    print(f"── {args.samples} sample rows ──")
    picks, seen_src = [], set()
    for r in rows:  # one per source/kind first, for variety
        key = (r["source"], r["raw_data"].get("kind"), r["raw_data"].get("needs_triage"))
        if key not in seen_src:
            seen_src.add(key)
            picks.append(r)
    for r in picks[:args.samples]:
        show = {k: (v[:160] + "…" if isinstance(v, str) and len(v) > 160 else v) for k, v in r.items()}
        print(json.dumps(show, ensure_ascii=False, indent=2))

    if args.apply:
        sb = supabase_client()
        write_inbox(sb, rows[:args.limit] if args.limit else rows)
        if not args.skip_algo and not args.limit:
            write_algo(sb, snaps)
        elif args.limit:
            print("algo_snapshot skipped (--limit run)")


if __name__ == "__main__":
    main()
