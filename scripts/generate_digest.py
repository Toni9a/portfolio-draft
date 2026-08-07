"""
generate_digest.py
──────────────────
Reads new 'cool news' inbox items, sends them to Gemini to cluster and
summarise into 5-8 digest items, writes to digest_items table, and marks
source inbox items as 'in_digest'.

Run weekly (or manually whenever you want a fresh digest):
  python generate_digest.py

Options:
  --folder "cool news"   Override source folder (default: cool news)
  --max 8                Max digest items to generate (default: 8, min: 3)
  --dry-run              Print the digest without writing to Supabase
"""

import os
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL              = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY            = os.environ["GEMINI_API_KEY"]

INTEREST_AREAS = [
    "computer vision", "applied AI", "machine learning", "spatial computing",
    "augmented reality", "robotics", "medical imaging", "generative AI",
    "web development", "3D graphics", "wearables", "creative technology",
    "design engineering", "electric vehicles", "fitness tech", "UK tech",
]

DIGEST_SYSTEM_PROMPT = """You are a research assistant helping a London-based applied AI engineer
called Toni stay on top of technology news without being overwhelmed.

His core interests: {interests}

You will be given a list of bookmarked tweets/posts in REVERSE CHRONOLOGICAL ORDER (newest first).
Each item is labelled with its original post date.

Your job is to:
1. Group similar items into clusters (items about the same topic, product, paper, or event)
2. Select the {max_items} most relevant and interesting clusters based on Toni's interests
3. PRIORITISE more recent items — prefer clusters where the post dates are newer
4. Write a concise, specific one-line summary for each cluster (not vague — name the actual thing)
5. Include the date range of the cluster (e.g. "Jul 2026") in the summary where useful
6. Suggest 1-3 topic tags per cluster from this list: ai, computer_vision, spatial, robotics,
   web, 3d, design, medical, wearables, creative_tech, uk_tech, business, science, other
7. Include the post date of the most recent item in the cluster as "latest_date" (ISO format)

Respond ONLY with valid JSON, no markdown, no explanation:
{{
  "digest": [
    {{
      "summary": "...",
      "topic_tags": ["tag1", "tag2"],
      "item_indices": [0, 3, 7],
      "latest_date": "2026-07-15"
    }}
  ]
}}
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", default="cool news")
    parser.add_argument("--max", type=int, default=8, dest="max_items")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    # Fetch newest first so Gemini sees recency in order
    result = (
        supabase.table("inbox")
        .select("id, url, full_text, author_handle, source_created_at")
        .eq("folder", args.folder)
        .eq("status", "new")
        .order("source_created_at", desc=True)
        .limit(150)
        .execute()
    )
    items = result.data

    if len(items) < 3:
        print(f"Only {len(items)} new items in '{args.folder}' — need at least 3 for a digest.")
        return

    print(f"Found {len(items)} new items in '{args.folder}' (newest first)")

    items_text = "\n\n".join(
        f"[{i}] {(item.get('source_created_at') or '')[:10]} @{item.get('author_handle') or 'unknown'}\n{item.get('full_text') or ''}\nURL: {item.get('url') or ''}"
        for i, item in enumerate(items)
    )

    system = DIGEST_SYSTEM_PROMPT.format(
        interests=", ".join(INTEREST_AREAS),
        max_items=args.max_items,
    )

    print("Sending to Gemini for clustering...")
    response = model.generate_content(
        f"{system}\n\n---ITEMS (newest first)---\n{items_text}",
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )

    try:
        digest_data = json.loads(response.text)
        clusters = digest_data.get("digest", [])
    except json.JSONDecodeError as e:
        print(f"Gemini returned invalid JSON: {e}")
        print(response.text[:500])
        return

    if not clusters:
        print("No clusters returned. Exiting.")
        return

    print(f"\n── Generated {len(clusters)} digest items ──")
    for i, cluster in enumerate(clusters):
        print(f"\n{i+1}. [{cluster.get('latest_date', '?')}] {cluster['summary']}")
        print(f"   Tags: {cluster.get('topic_tags', [])}")
        print(f"   Sources: {len(cluster.get('item_indices', []))} items")

    if args.dry_run:
        print("\n[dry-run] Nothing written to Supabase.")
        return

    inbox_ids_used = set()
    digest_rows = []

    for cluster in clusters:
        indices = cluster.get("item_indices", [])
        valid_indices = [i for i in indices if 0 <= i < len(items)]
        cluster_inbox_ids = [items[i]["id"] for i in valid_indices]
        inbox_ids_used.update(cluster_inbox_ids)

        # Use the cluster's latest_date as surfaced_at so the admin UI sorts by post recency
        latest_date = cluster.get("latest_date")
        surfaced_at = latest_date if latest_date else None

        digest_rows.append({
            "inbox_ids": cluster_inbox_ids,
            "summary": cluster["summary"],
            "topic_tags": cluster.get("topic_tags", []),
            "status": "pending",
            **({"surfaced_at": surfaced_at} if surfaced_at else {}),
        })

    supabase.table("digest_items").insert(digest_rows).execute()
    print(f"\n✓ Inserted {len(digest_rows)} digest items")

    ids_to_update = list(inbox_ids_used)
    if ids_to_update:
        supabase.table("inbox").update({"status": "in_digest"}).in_("id", ids_to_update).execute()
        print(f"✓ Marked {len(ids_to_update)} inbox items as 'in_digest'")

    print("\nDone. Open the admin UI Digest tab to write your commentary.")


if __name__ == "__main__":
    main()
