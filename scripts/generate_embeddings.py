"""
generate_embeddings.py
──────────────────────
Finds commentary rows without embeddings and generates them.

Uses gemini-embedding-2 at 768 dimensions, matching the commentary.embedding
column. text-embedding-004 was retired and now returns a 404.

Safe to re-run — only processes rows where embedding IS NULL.

Run after writing new commentary:
  python scripts/generate_embeddings.py

Needs the current SDK, not the retired one:
  pip install google-genai
"""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL              = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY            = os.environ["GEMINI_API_KEY"]

# Same defaults as embed_nodes.py so the two stay in step.
EMBEDDING_MODEL = os.environ.get("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
DIMS  = 768     # must match the vector(768) column
BATCH = 25


def main() -> None:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    client = genai.Client(api_key=GEMINI_API_KEY)
    cfg = types.EmbedContentConfig(
        output_dimensionality=DIMS,
        task_type="SEMANTIC_SIMILARITY",
    )

    rows = (
        supabase.table("commentary")
        .select("id, body")
        .is_("embedding", "null")
        .execute()
    ).data

    rows = [r for r in rows if (r.get("body") or "").strip()]
    if not rows:
        print("No commentary rows missing embeddings. All up to date.")
        return

    print(f"Generating embeddings for {len(rows)} commentary rows "
          f"using {EMBEDDING_MODEL} at {DIMS} dimensions...")

    done, failed = 0, 0
    for start in range(0, len(rows), BATCH):
        batch = rows[start:start + BATCH]
        try:
            resp = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=[r["body"] for r in batch],
                config=cfg,
            )
            vectors = [e.values for e in resp.embeddings]
        except Exception as e:
            failed += len(batch)
            print(f"  ✗ batch failed: {e}")
            time.sleep(3)
            continue

        for row, vector in zip(batch, vectors):
            if len(vector) != DIMS:
                failed += 1
                print(f"  ✗ {row['id'][:8]} came back with {len(vector)} dims, expected {DIMS}")
                continue
            supabase.table("commentary").update({"embedding": vector}).eq("id", row["id"]).execute()
            done += 1
            print(f"  ✓ {row['id'][:8]}")
        time.sleep(0.2)

    print(f"\nDone. {done} embedded, {failed} failed.")


if __name__ == "__main__":
    main()
