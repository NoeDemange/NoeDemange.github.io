#!/usr/bin/env python3
"""Sync repository metadata from the GitHub API into _data/repositories.yml."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests
import yaml

DATA_FILE = Path("_data/repositories.yml")
API_BASE_URL = "https://api.github.com"
TOKEN_ENV_VAR = "GITHUB_TOKEN"
USER_AGENT = "al-folio-repo-sync"


def load_data() -> Dict[str, Any]:
    if not DATA_FILE.exists():
        print(f"Data file {DATA_FILE} not found.")
        sys.exit(1)

    if DATA_FILE.stat().st_size == 0:
        print(
            f"Data file {DATA_FILE} is empty. Please restore the file before running the sync."
        )
        sys.exit(1)

    with DATA_FILE.open("r", encoding="utf-8") as handle:
        try:
            return yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            print(f"Unable to parse {DATA_FILE}: {exc}")
            sys.exit(1)


def require_token() -> str:
    token = os.environ.get(TOKEN_ENV_VAR)
    if not token:
        print(
            "Missing GitHub token. Please export GITHUB_TOKEN with a fine-grained "
            "token that can read your repositories."
        )
        sys.exit(1)
    return token


def build_session(token: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
    )
    return session


def fetch_repo(slug: str, session: requests.Session) -> Dict[str, Any]:
    slug = slug.strip()
    if not slug:
        raise ValueError("Repository slug cannot be empty.")

    url = f"{API_BASE_URL}/repos/{slug}"
    response = session.get(url, timeout=30)
    if response.status_code == 404:
        raise RuntimeError(f"Repository '{slug}' does not exist or is private.")

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(f"GitHub API error for '{slug}': {exc}") from exc

    payload = response.json()
    topics = payload.get("topics") or []
    return {
        "slug": slug,
        "name": payload.get("name") or slug.split("/")[-1],
        "description": payload.get("description") or "",
        "keywords": topics,
        "homepage": payload.get("homepage") or "",
        "language": payload.get("language") or "",
        "stars": payload.get("stargazers_count") or 0,
        "updated": payload.get("updated_at"),
    }


def write_data(raw_data: Dict[str, Any], metadata: List[Dict[str, Any]]) -> None:
    ordered_keys = ["github_users", "repo_description_lines_max", "github_repos"]
    ordered_data: Dict[str, Any] = {}

    for key in ordered_keys:
        if key in raw_data:
            ordered_data[key] = raw_data[key]
        elif key == "repo_description_lines_max":
            ordered_data[key] = 2
        elif key == "github_repos":
            ordered_data[key] = []

    ordered_data["github_repos_metadata"] = metadata

    for key, value in raw_data.items():
        if key not in ordered_data:
            ordered_data[key] = value

    with DATA_FILE.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(ordered_data, handle, sort_keys=False, allow_unicode=True)


def main() -> None:
    data = load_data()
    repos = data.get("github_repos", [])
    if not repos:
        print("No entries found under 'github_repos'. Nothing to update.")
        return

    token = require_token()
    session = build_session(token)

    metadata: List[Dict[str, Any]] = []
    for slug in repos:
        try:
            repo_data = fetch_repo(slug, session)
            print(f"Fetched metadata for {repo_data['slug']}")
            metadata.append(repo_data)
        except Exception as exc:  # noqa: BLE001
            print(exc)
            sys.exit(1)

    if data.get("github_repos_metadata") == metadata:
        print("Repository metadata already up-to-date. Skipping write.")
        return

    write_data(data, metadata)
    print(f"Saved metadata for {len(metadata)} repositories to {DATA_FILE}.")


if __name__ == "__main__":
    main()
