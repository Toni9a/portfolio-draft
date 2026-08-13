"""
embed_nodes.py
──────────────
Generates embeddings for rows in the `node` table that do not have one yet.

Uses gemini-embedding-2 at 768 dimensions, which is what the `embedding` column
expects. The model returns 3072 by default and normalises properly when you ask
for fewer, so 768 is a real setting rather than a truncation.

Text only. It does not look at the images attached to a bookmark. The model can
do images, but that is a separate pass and costs per image.

Safe to re-run. It only touches rows where embedding IS NULL, so if it stops part
way through you can just run it again.

  python scripts/embed_nodes.py --limit 20     # try a small batch first
  python scripts/embed_nodes.py                # everything left

Needs the current SDK, not the retired one:
    pip install google-genai
"""

import argparse
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

MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
DIMS = 768              # must match the vector(768) column
PAGE = 200              # rows fetched from Supabase at a time
BATCH = 25              # items per embedding call
MAX_CHARS = 8000

DIM, RESET, RED = "\033[2m", "\033[0m", "\033[31m"


def text_for(row: dict) -> str:
    """What gets embedded. Kind and title first, then the body, capped."""
    parts = [row.get("kind") or "", row.get("title") or "", row.get("body") or ""]
    return "\n".join(p for p in parts if p).strip()[:MAX_CHARS]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="stop after this many rows")
    args = ap.parse_args()

    sb: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = types.EmbedContentConfig(
        output_dimensionality=DIMS,
        task_type="SEMANTIC_SIMILARITY",
    )

    total = sb.table("node").select("id", count="exact", head=True) \
        .is_("embedding", "null").execute().count or 0
    print(f"{total} rows need an embedding. Using {MODEL} at {DIMS} dimensions.\n")

    done, failed = 0, 0
    batch_size = BATCH
    while True:
        rows = (sb.table("node").select("id, kind, title, body")
                .is_("embedding", "null").limit(PAGE).execute().data)
        if not rows:
            break

        # Anything with no text at all gets stamped so it stops coming back.
        blank = [r["id"] for r in rows if not text_for(r)]
        if blank:
            for nid in blank:
                sb.table("node").update({"embedded_at": "now()"}).eq("id", nid).execute()
            rows = [r for r in rows if text_for(r)]

        i = 0
        while i < len(rows):
            if args.limit is not None and done >= args.limit:
                print(f"\nStopped at the limit of {args.limit}.")
                return

            batch = rows[i:i + batch_size]
            try:
                resp = client.models.embed_content(
                    model=MODEL,
                    contents=[text_for(r) for r in batch],
                    config=cfg,
                )
                vectors = [e.values for e in resp.embeddings]
            except Exception as e:
                failed += len(batch)
                print(f"{RED}batch failed: {e}{RESET}")
                if failed > 100:
                    print("Too many failures. Stopping so you can look at it.")
                    return
                i += len(batch)
                time.sleep(3)
                continue

            # A list of strings can come back as ONE blended vector covering all of
            # them rather than one vector each. Assigning that to the first row
            # would be silently wrong, so drop to one per call and retry the same
            # items rather than guessing.
            if len(vectors) != len(batch):
                if batch_size > 1:
                    print(f"{RED}Sent {len(batch)} items, got {len(vectors)} vectors. "
                          f"Switching to one per call.{RESET}")
                    batch_size = 1
                    continue
                print(f"{RED}Expected 1 vector, got {len(vectors)}. Stopping.{RESET}")
                return

            i += len(batch)
            for row, vector in zip(batch, vectors):
                if len(vector) != DIMS:
                    failed += 1
                    print(f"{RED}node {row['id']} came back with {len(vector)} dims, "
                          f"expected {DIMS}. Skipped.{RESET}")
                    continue
                sb.table("node").update(
                    {"embedding": vector, "embedded_at": "now()"}
                ).eq("id", row["id"]).execute()
                done += 1

            print(f"{DIM}  {done}/{total} embedded{RESET}")
            time.sleep(0.2)

    print(f"\nDone. {done} embedded, {failed} failed.")


if __name__ == "__main__":
    main()
