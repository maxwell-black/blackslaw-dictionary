#!/usr/bin/env python3
"""
validate_rebuild.py — Validate a rebuilt or live corpus JSON file.

Checks:
  - Entry count and structure
  - Short header artifacts (mid-body only, skips first line)
  - Page number artifacts
  - Empty bodies
  - Garbled body starts (v.\\nfrom. pattern)
  - Duplicate headwords

Usage:
    python scripts/validate_rebuild.py [path]

Default path: rebuild/out/blacks_entries.live_candidate.json
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SHORT_HEADER_RE = re.compile(r"(?m)^[A-Z]{1,4}$")
PAGE_NUMBER_RE = re.compile(r"(?m)^\d{1,4}$")
GARBLED_START_RE = re.compile(r"^[a-z]{1,3}\.\s*(?:from\.|[.,;])")


def validate(path: Path) -> int:
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)

    print(f"Validating {path.name}: {len(entries)} entries")

    issues: dict[str, list] = {
        "empty_body": [],
        "short_header_artifact": [],
        "page_number_artifact": [],
        "garbled_body_start": [],
        "duplicate_headword": [],
    }

    seen_terms: dict[str, int] = {}

    for i, e in enumerate(entries):
        term = e.get("term", "")
        body = e.get("body", "")

        # Duplicate headwords
        if term in seen_terms:
            issues["duplicate_headword"].append(
                f"  [{i}] {term} (first at [{seen_terms[term]}])"
            )
        seen_terms[term] = i

        # Empty body
        if not body.strip():
            issues["empty_body"].append(f"  [{i}] {term}")
            continue

        # Short header artifact — only flag mid-body (skip first line)
        first_newline = body.index("\n") if "\n" in body else len(body)
        body_after_first = body[first_newline:]
        if body_after_first and SHORT_HEADER_RE.search(body_after_first):
            issues["short_header_artifact"].append(
                f"  [{i}] {term}: ...{body_after_first[body_after_first.find(chr(10)):body_after_first.find(chr(10))+20].strip()!r}..."
            )

        # Page number artifact (mid-body only)
        if body_after_first and PAGE_NUMBER_RE.search(body_after_first):
            issues["page_number_artifact"].append(f"  [{i}] {term}")

        # Garbled body start
        flat = re.sub(r"\s+", " ", body[:60]).strip()
        if GARBLED_START_RE.match(flat):
            issues["garbled_body_start"].append(
                f"  [{i}] {term}: {flat[:50]!r}"
            )

    # Report
    total_issues = 0
    for category, items in issues.items():
        if items:
            print(f"\n{category}: {len(items)}")
            for line in items[:10]:
                print(line)
            if len(items) > 10:
                print(f"  ... and {len(items) - 10} more")
            total_issues += len(items)

    if total_issues == 0:
        print("\nAll checks passed.")
    else:
        print(f"\nTotal issues: {total_issues}")

    return 1 if total_issues > 0 else 0


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = ROOT / "rebuild" / "out" / "blacks_entries.live_candidate.json"

    if not path.exists():
        print(f"File not found: {path}")
        return 1

    return validate(path)


if __name__ == "__main__":
    sys.exit(main())
