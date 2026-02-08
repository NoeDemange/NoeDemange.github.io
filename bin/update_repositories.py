#!/usr/bin/env python3
"""Sync repository metadata from the GitHub API into _data/repositories.yml."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import requests
import yaml

DATA_FILE = Path("_data/repositories.yml")
API_BASE_URL = "https://api.github.com"
TOKEN_ENV_VAR = "GITHUB_TOKEN"
USER_AGENT = "al-folio-repo-sync"
REPOS_PER_PAGE = 100


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


def write_data(
    raw_data: Dict[str, Any], metadata: List[Dict[str, Any]], repos: List[str]
) -> None:
    ordered_data: Dict[str, Any] = {}
    ordered_data["github_users"] = raw_data.get("github_users", [])
    ordered_data["repo_description_lines_max"] = raw_data.get(
        "repo_description_lines_max", 2
    )
    ordered_data["github_repos"] = repos
    ordered_data["github_repos_metadata"] = metadata

    for key, value in raw_data.items():
        if key not in ordered_data:
            ordered_data[key] = value

    with DATA_FILE.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(ordered_data, handle, sort_keys=False, allow_unicode=True)


def fetch_user_repositories(user: str, session: requests.Session) -> List[str]:
    username = user.strip()
    if not username:
        return []

    page = 1
    slugs: List[str] = []
    while True:
        params = {
            "type": "owner",
            "per_page": REPOS_PER_PAGE,
            "page": page,
            "sort": "updated",
            "direction": "desc",
        }
        url = f"{API_BASE_URL}/users/{username}/repos"
        response = session.get(url, params=params, timeout=30)
        if response.status_code == 404:
            raise RuntimeError(f"GitHub user '{username}' does not exist or is private.")
        response.raise_for_status()

        payload = response.json()
        if not payload:
            break

        for repo in payload:
            full_name = repo.get("full_name")
            if full_name:
                slugs.append(full_name)
        if len(payload) < REPOS_PER_PAGE:
            break
        page += 1

    print(f"Discovered {len(slugs)} repos for user '{username}'.")
    return slugs


def resolve_repositories(
    data: Dict[str, Any], session: requests.Session
) -> List[str]:
    manual_repos = [slug for slug in data.get("github_repos", []) if slug]
    seen: Set[str] = set(manual_repos)
    resolved: List[str] = list(manual_repos)

    users: Iterable[str] = data.get("github_users", []) or []
    for user in users:
        try:
            for slug in fetch_user_repositories(user, session):
                if slug not in seen:
                    seen.add(slug)
                    resolved.append(slug)
        except Exception as exc:  # noqa: BLE001
            print(exc)
            sys.exit(1)

    return resolved


def main() -> None:
    data = load_data()
    token = require_token()
    session = build_session(token)

    repos = resolve_repositories(data, session)
    if not repos:
        print(
            "No repositories found. Populate 'github_users' or 'github_repos' in _data/repositories.yml."
        )
        return

    metadata: List[Dict[str, Any]] = []
    for slug in repos:
        try:
            repo_data = fetch_repo(slug, session)
            print(f"Fetched metadata for {repo_data['slug']}")
            metadata.append(repo_data)
        except Exception as exc:  # noqa: BLE001
            print(exc)
            sys.exit(1)

    if (
        data.get("github_repos_metadata") == metadata
        and data.get("github_repos") == repos
    ):
        print("Repository metadata already up-to-date. Skipping write.")
        return

    write_data(data, metadata, repos)
    print(f"Saved metadata for {len(metadata)} repositories to {DATA_FILE}.")


if __name__ == "__main__":
    main()
