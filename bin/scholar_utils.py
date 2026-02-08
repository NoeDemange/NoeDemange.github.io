#!/usr/bin/env python3
"""Shared helpers for scripts that interact with Google Scholar."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

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
