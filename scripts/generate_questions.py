"""
generate_questions.py
─────────────────────
For each repo in github_sync_cache, generates a short set of targeted
questions using Gemini (based on the README + any existing portfolio data),
then stores them in project_qna_sessions ready for you to answer.

Run after github_sync.py:
  python generate_questions.py

To answer the questions interactively in your terminal:
  python generate_questions.py --answer

Options:
  --repo tonzownz/TrakRush   Only process one specific repo
  --answer                   Interactive mode: step through unanswered questions
  --force                    Re-generate questions even if they already exist
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

REPO_TO_PROJECT_ID: dict[str, str] = {
    # "tonzownz/trakrush": "trakrush",
    # "tonzownz/leveret-dental": "leveret_ai",
}

QUESTION_SYSTEM_PROMPT = """You are helping Toni Esan, an applied AI engineer and creative
technologist, document and explain his projects for his personal portfolio.

Given a GitHub repo name, description, topics, and README, generate exactly 5 targeted questions
that will help Toni articulate:
- Why he built this (the actual motivation, not the generic answer)
- What was technically interesting or challenging
- What he would do differently now
- What hat(s) this falls under: computer_vision | web_software | ml_ai | design_engineering | creative_tech | entrepreneurship | other
- Whether it's worth showcasing for TikTok / LinkedIn content

The questions should be specific to THIS project — reference actual things from the README.
Do not ask generic questions like "What did you learn?"

Respond ONLY with valid JSON, no markdown:
{
  "project_id_suggestion": "snake_case_id",
  "hat_suggestions": ["computer_vision", "ml_ai"],
  "questions": [
    "Question 1 here",
    "Question 2 here",
    "Question 3 here",
    "Question 4 here",
    "Question 5 here"
  ]
}
"""


def generate_questions_for_repo(model, repo: dict) -> dict | None:
    readme = repo.get("readme_md") or ""
    readme_excerpt = readme[:3000]

    prompt = f"""Repo: {repo['repo_full_name']}
Description: {repo.get('description') or '(none)'}
Topics: {', '.join(repo.get('topics') or [])}

README (first 3000 chars):
{readme_excerpt}
"""

    try:
        response = model.generate_content(
            f"{QUESTION_SYSTEM_PROMPT}\n\n{prompt}",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.4,
            ),
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"  Gemini error: {e}")
        return None


def answer_mode(supabase: Client):
    result = (
        supabase.table("project_qna_sessions")
        .select("id, project_id, question, answer")
        .is_("answer", "null")
        .order("project_id")
        .execute()
    )
    unanswered = result.data

    if not unanswered:
        print("No unanswered questions. Run without --answer to generate more.")
        return

    print(f"\n{len(unanswered)} unanswered questions. Type your answer and press Enter.")
    print("Press Enter with no input to skip. Type 'q' to quit.\n")

    for i, row in enumerate(unanswered):
        print(f"── {row['project_id']} [{i+1}/{len(unanswered)}] ──")
        print(f"Q: {row['question']}\n")
        answer = input("A: ").strip()

        if answer.lower() == "q":
            print("Quitting.")
            break
        if not answer:
            print("Skipped.\n")
            continue

        supabase.table("project_qna_sessions").update({
            "answer": answer,
            "answered_at": "now()",
        }).eq("id", row["id"]).execute()
        print("✓ Saved\n")

    print("Done answering.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="Specific repo full name e.g. Toni9a/halfmara")
    parser.add_argument("--answer", action="store_true", help="Interactive answer mode")
    parser.add_argument("--force", action="store_true", help="Re-generate questions even if they exist")
    args = parser.parse_args()

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    if args.answer:
        answer_mode(supabase)
        return

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    query = supabase.table("github_sync_cache").select("*")
    if args.repo:
        query = query.eq("repo_full_name", args.repo)
    repos = query.execute().data

    if not repos:
        print("No repos in github_sync_cache. Run github_sync.py first.")
        return

    print(f"Generating questions for {len(repos)} repo(s)...\n")

    for repo in repos:
        repo_name = repo["repo_full_name"]
        project_id = REPO_TO_PROJECT_ID.get(repo_name.lower()) or repo_name.split("/")[-1].lower()

        print(f"── {repo_name} ──")

        if not args.force:
            existing = (
                supabase.table("project_qna_sessions")
                .select("id")
                .eq("project_id", project_id)
                .execute()
            )
            if existing.data:
                print(f"  Already has {len(existing.data)} questions. Use --force to regenerate.\n")
                continue

        result = generate_questions_for_repo(model, repo)
        if not result:
            print("  Failed to generate. Skipping.\n")
            continue

        questions = result.get("questions", [])
        hat_suggestions = result.get("hat_suggestions", [])

        print(f"  Hat suggestions: {hat_suggestions}")
        print(f"  Generated {len(questions)} questions")

        rows = [{"project_id": project_id, "question": q} for q in questions]
        rows.append({
            "project_id": project_id,
            "question": f"[meta] Hat suggestions from README: {', '.join(hat_suggestions)}. Confirm or override?",
        })

        supabase.table("project_qna_sessions").insert(rows).execute()
        print(f"  ✓ Stored {len(rows)} questions\n")

    print("Done. Refresh the admin page Q&A tab to start answering.")


if __name__ == "__main__":
    main()
