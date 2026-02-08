#!/usr/bin/env python3
"""Fetch Google Scholar publications and update _bibliography/papers.bib."""

from __future__ import annotations

import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from scholarly import scholarly

from scholar_utils import configure_scholarly_session, load_scholar_user_id

BIBLIO_FILE = Path("_bibliography/papers.bib")
MANUAL_FILE = Path("_bibliography/manual_overrides.bib")


def fetch_publications(scholar_id: str) -> List[Dict[str, object]]:
    """Return the list of publication dicts for the given Scholar ID."""
    print(f"Fetching publications for Google Scholar ID: {scholar_id}")
    scholarly.set_timeout(15)
    scholarly.set_retries(3)

    try:
        author = scholarly.search_author_id(scholar_id)
        author = scholarly.fill(author, sections=["publications"])
    except Exception as exc:  # noqa: BLE001
        print(f"Error fetching author data: {exc}")
        sys.exit(1)

    publications = []
    for pub in author.get("publications", []):
        try:
            publications.append(scholarly.fill(pub))
        except Exception as exc:  # noqa: BLE001
            title = pub.get("bib", {}).get("title", "Unknown title")
            print(f"Warning: Could not fetch full data for '{title}': {exc}")

    if not publications:
        print("No publications retrieved from Google Scholar.")
        sys.exit(1)

    return publications


def slugify(text: str) -> str:
    """Normalize text for safe BibTeX keys."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_text = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text.lower() or "publication"


def unique_key(base: str, existing: Iterable[str]) -> str:
    """Ensure the BibTeX key is unique within the bibliography."""
    key = base
    index = 2
    existing_set = set(existing)
    while key in existing_set:
        key = f"{base}-{index}"
        index += 1
    return key


def determine_entry_type(bib: Dict[str, str]) -> str:
    if bib.get("journal"):
        return "article"
    if bib.get("booktitle"):
        return "inproceedings"
    citation = (bib.get("citation") or "").lower()
    if "thesis" in citation:
        return "phdthesis"
    return "misc"


def sanitize(value: object) -> str:
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def parse_year(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_bibtex_entry(
    pub: Dict[str, object], existing_keys: List[str]
) -> Tuple[str, str]:
    bib = pub.get("bib", {})
    title = bib.get("title") or "Untitled"
    year = bib.get("pub_year") or "n.d."
    authors = bib.get("author") or "Unknown"

    first_author_block = authors.split(" and ")[0].strip()
    parts = first_author_block.split()
    first_author_last = parts[-1] if parts else "publication"
    base_key = slugify(f"{first_author_last}-{year}")
    key = unique_key(base_key, existing_keys)
    existing_keys.append(key)

    entry_type = determine_entry_type(bib)

    fields = [
        ("author", authors),
        ("title", title),
        ("journal", bib.get("journal")),
        ("booktitle", bib.get("booktitle")),
        ("publisher", bib.get("publisher")),
        ("volume", bib.get("volume")),
        ("number", bib.get("number")),
        ("pages", bib.get("pages")),
        ("year", year),
        ("abstract", bib.get("abstract")),
        ("url", pub.get("pub_url") or bib.get("url")),
        ("bibtex_show", "true"),
    ]

    if entry_type == "article":
        fields = [field for field in fields if field[0] != "booktitle"]
    elif entry_type == "inproceedings":
        fields = [field for field in fields if field[0] != "journal"]

    formatted_fields = [
        f"  {field} = {{{sanitize(value)}}}"
        for field, value in fields
        if value
    ]

    entry_text = f"@{entry_type}{{{key},\n" + ",\n".join(formatted_fields) + "\n}\n"
    return key, entry_text


def load_manual_overrides() -> Tuple[Set[str], str]:
    if not MANUAL_FILE.exists():
        return set(), ""

    manual_text = MANUAL_FILE.read_text(encoding="utf-8").strip()
    if not manual_text:
        return set(), ""

    manual_keys = {
        match.group(1).strip()
        for match in re.finditer(r"@\w+\{([^,]+),", manual_text)
    }

    return manual_keys, manual_text + "\n"


def write_bibtex(entries: List[str], scholar_id: str, manual_text: str) -> None:
    BIBLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"%% Auto-generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        f"%% Source: Google Scholar ID {scholar_id}\n\n"
    )

    with BIBLIO_FILE.open("w", encoding="utf-8") as handle:
        handle.write(header)
        for entry in entries:
            handle.write(entry)
            handle.write("\n")

        if manual_text:
            handle.write(
                "\n%% Manual overrides appended from _bibliography/manual_overrides.bib\n\n"
            )
            handle.write(manual_text.rstrip())
            handle.write("\n")

    total_entries = len(entries)
    if manual_text:
        print(
            f"Saved {total_entries} auto-generated entries plus manual overrides to {BIBLIO_FILE}."
        )
    else:
        print(f"Saved {total_entries} entries to {BIBLIO_FILE}.")


def main() -> None:
    configure_scholarly_session()
    scholar_id = load_scholar_user_id()
    publications = fetch_publications(scholar_id)

    manual_keys, manual_text = load_manual_overrides()
    if manual_keys:
        print(
            f"Found {len(manual_keys)} manual override key(s) that will replace auto-generated entries."
        )
    elif manual_text:
        print("Manual overrides file has content but no BibTeX entries were detected.")

    publications.sort(
        key=lambda item: (
            parse_year(item.get("bib", {}).get("pub_year")),
            item.get("bib", {}).get("title", ""),
        ),
        reverse=True,
    )

    existing_keys: List[str] = []
    auto_entries = [build_bibtex_entry(pub, existing_keys) for pub in publications]

    filtered_entries = [
        entry for key, entry in auto_entries if key not in manual_keys
    ]

    skipped = len(auto_entries) - len(filtered_entries)
    if skipped:
        print(f"Skipped {skipped} auto-generated entr(y/ies) due to manual overrides.")

    write_bibtex(filtered_entries, scholar_id, manual_text)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Aborted by user.")
        sys.exit(1)
