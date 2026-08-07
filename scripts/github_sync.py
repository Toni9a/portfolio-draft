"""
github_sync.py
──────────────
Syncs ALL your GitHub repos (excluding forks by default) into
github_sync_cache. No need to tag repos — you toggle inclusion
in the admin UI instead.

Usage:
  python github_sync.py                  # sync all non-fork repos
  python github_sync.py --include-forks  # include forked repos too
  python github_sync.py --repo tonzownz/TrakRush  # sync one specific repo
  python github_sync.py --dry-run        # print what would be synced
"""

import os
import base64
import argparse
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL               = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY  = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
GITHUB_TOKEN               = os.environ.get("GITHUB_TOKEN")
GITHUB_USERNAME            = os.environ.get("GITHUB_USERNAME", "tonzownz")

GH_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    **({"Authorization": f"Bearer {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
}


def gh_get(url: str):
    r = requests.get(url, headers=GH_HEADERS, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def fetch_readme(repo_full_name: str) -> str | None:
    data = gh_get(f"https://api.github.com/repos/{repo_full_name}/readme")
    if not data or "content" not in data:
        return None
    try:
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_all_repos(username: str, include_forks: bool) -> list[dict]:
    repos, page = [], 1
    while True:
        url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner"
        batch = gh_get(url)
        if not batch:
            break
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    if not include_forks:
        repos = [r for r in repos if not r.get("fork")]
    return repos


def repo_to_row(repo: dict, readme: str | None) -> dict:
    pushed_at = repo.get("pushed_at")
    last_commit = None
    if pushed_at:
        try:
            last_commit = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            pass
    return {
        "repo_full_name": repo["full_name"],
        "display_name": repo["name"],
        "readme_md": readme,
        "description": repo.get("description"),
        "topics": repo.get("topics") or [],
        "homepage_url": repo.get("homepage"),
        "stars": repo.get("stargazers_count", 0),
        "last_commit_at": last_commit,
        "raw_data": {
            "id": repo["id"],
            "name": repo["name"],
            "private": repo.get("private", False),
            "language": repo.get("language"),
            "fork": repo.get("fork", False),
            "created_at": repo.get("created_at"),
            "html_url": repo.get("html_url"),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default=GITHUB_USERNAME)
    parser.add_argument("--include-forks", action="store_true")
    parser.add_argument("--repo", help="Sync a single repo e.g. tonzownz/TrakRush")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    if args.repo:
        raw = gh_get(f"https://api.github.com/repos/{args.repo}")
        repos = [raw] if raw else []
    else:
        print(f"Fetching repos for @{args.username}...")
        repos = fetch_all_repos(args.username, args.include_forks)

    if not repos:
        print("No repos found.")
        return

    print(f"Found {len(repos)} repos\n")
    for r in repos:
        print(f"  {'[fork] ' if r.get('fork') else ''}{r['full_name']} — {r.get('description') or '(no description)'}")

    if args.dry_run:
        print("\n[dry-run] Nothing written.")
        return

    rows = []
    for i, repo in enumerate(repos):
        name = repo["full_name"]
        print(f"\n[{i+1}/{len(repos)}] {name}")
        readme = fetch_readme(name)
        print(f"  README: {len(readme)} chars" if readme else "  README: none")
        rows.append(repo_to_row(repo, readme))

    # Upsert — preserve existing 'included' value so toggling in the UI isn't overwritten
    supabase.table("github_sync_cache").upsert(
        rows,
        on_conflict="repo_full_name",
        ignore_duplicates=False,
    ).execute()

    print(f"\n✓ Synced {len(rows)} repos. Open the admin UI to toggle which ones are active.")


if __name__ == "__main__":
    main()
