#!/usr/bin/env python3
"""Shared helpers for scripts that interact with Google Scholar."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml
from scholarly import ProxyGenerator, scholarly

CONFIG_PATH = Path("_data/socials.yml")


def load_scholar_user_id(config_path: str | Path = CONFIG_PATH) -> str:
    """Return the Google Scholar user ID defined in _data/socials.yml."""
    path = Path(config_path)
    if not path.exists():
        print(
            f"Configuration file {path} not found. Please ensure the file exists and contains your Google Scholar user ID."
        )
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as handle:
            config: Any = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        print(f"Error parsing YAML file {path}: {exc}. Please verify the YAML syntax.")
        sys.exit(1)

    scholar_user_id = config.get("scholar_userid")
    if not scholar_user_id:
        print(
            "No 'scholar_userid' key found in _data/socials.yml. Please add it before running this script."
        )
        sys.exit(1)

    return scholar_user_id


def configure_scholarly_session() -> None:
    """Configure scholarly to use the most reliable proxy available."""
    pg = ProxyGenerator()

    serpapi_key = os.environ.get("SERPAPI_API_KEY") or os.environ.get("SERPAPI_KEY")
    ci_env = os.environ.get("CI") == "true"
    if serpapi_key:
        try:
            if pg.SerpAPI(serpapi_key):
                scholarly.use_proxy(pg)
                print("Using SerpAPI for Google Scholar requests.")
                return
            print("Warning: Unable to initialize SerpAPI proxy. Falling back to free proxies.")
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: SerpAPI proxy configuration failed: {exc}. Falling back to free proxies.")

    if not ci_env:
        print("CI environment not detected; using direct Google Scholar connection.")
        return

    try:
        if pg.FreeProxies():
            scholarly.use_proxy(pg)
            print("Using rotating free proxies for Google Scholar requests.")
            return
        print("Warning: Unable to obtain a free proxy. Proceeding without proxy support.")
    except Exception as exc:  # noqa: BLE001
        print(f"Warning: Free proxy configuration failed: {exc}. Proceeding without proxy support.")

    print(
        "Continuing without any Google Scholar proxy. Set SERPAPI_API_KEY as a repository secret if remote runs keep failing."
    )
