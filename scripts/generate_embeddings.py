"""
generate_embeddings.py
──────────────────────
Finds commentary rows without embeddings and generates them using
Gemini's text-embedding-004 model (768 dims). Safe to re-run — only
processes rows where embedding IS NULL.

Run after writing new commentary:
  python generate_embeddings.py
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client
import google.generativeai as genai

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL              = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GEMINI_API_KEY            = os.environ["GEMINI_API_KEY"]

EMBEDDING_MODEL = "models/text-embedding-004"  # 768 dims, matches schema


def embed_text(text: str) -> list[float]:
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="SEMANTIC_SIMILARITY",
    )
    return result["embedding"]


def main():
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)

    # Fetch commentary rows missing embeddings
    result = (
        supabase.table("commentary")
        .select("id, body")
        .is_("embedding", "null")
        .execute()
    )
    rows = result.data

    if not rows:
        print("No commentary rows missing embeddings. All up to date.")
        return

    print(f"Generating embeddings for {len(rows)} commentary rows...")

    for i, row in enumerate(rows):
        try:
            embedding = embed_text(row["body"])
            supabase.table("commentary").update({"embedding": embedding}).eq("id", row["id"]).execute()
            print(f"  [{i+1}/{len(rows)}] ✓ {row['id'][:8]}...")
            time.sleep(0.1)  # gentle rate limiting
        except Exception as e:
            print(f"  [{i+1}/{len(rows)}] ✗ Failed for {row['id'][:8]}: {e}")

    print(f"\n✓ Done. {len(rows)} embeddings generated.")


if __name__ == "__main__":
    main()
