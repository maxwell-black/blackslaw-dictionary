#!/usr/bin/env python3
"""
source_page_validator.py — Validate source_pages monotonicity and range
consistency across the live corpus.

Principle: Black's Law Dictionary is alphabetically ordered. Within each
letter section, source page numbers must be monotonically non-decreasing
and must fall within the expected page range for that letter. An entry
under "I" with source page 186 is a misplaced entry — either the headword
is wrong or the source_pages mapping is wrong.

Usage:
    python3 scripts/source_page_validator.py

    # Report only, no mutations:
    python3 scripts/source_page_validator.py --report-only

    # Include entries with no source_pages in the gap analysis:
    python3 scripts/source_page_validator.py --include-empty

Outputs:
    rebuild/reports/source_page_validation.json  — machine-readable
    rebuild/reports/source_page_validation.md    — human-readable

Requires:
    - blacks_entries.json in repo root (current live corpus)
"""

import json
import sys
import argparse
import statistics
from pathlib import Path
from collections import defaultdict


REPO_ROOT = Path(".")
LIVE_CORPUS = REPO_ROOT / "blacks_entries.json"
REPORT_DIR = REPO_ROOT / "rebuild" / "reports"
REPORT_JSON = REPORT_DIR / "source_page_validation.json"
REPORT_MD = REPORT_DIR / "source_page_validation.md"


def load_corpus() -> list[dict]:
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        data = json.load(f)
    # Normalize: our corpus uses 'term', script expects 'headword'
    for entry in data:
        if "headword" not in entry and "term" in entry:
            entry["headword"] = entry["term"]
        if "id" not in entry:
            entry["id"] = entry.get("headword", entry.get("term", ""))
    return data


def get_letter(headword: str) -> str:
    """Extract the filing letter from a headword."""
    hw = headword.strip().upper()
    if not hw:
        return "?"
    # Skip leading non-alpha (quotes, parens, etc.)
    for ch in hw:
        if ch.isalpha():
            return ch
    return "?"


def extract_pages(entry: dict) -> list[int]:
    """Extract integer page/leaf numbers from source_pages field."""
    sp = entry.get("source_pages", [])
    if not sp:
        return []
    if isinstance(sp, (int, float)):
        return [int(sp)]
    if isinstance(sp, str):
        # Could be comma-separated or single number
        pages = []
        for part in sp.replace(",", " ").split():
            try:
                pages.append(int(part))
            except ValueError:
                pass
        return pages
    if isinstance(sp, list):
        pages = []
        for item in sp:
            if isinstance(item, (int, float)):
                pages.append(int(item))
            elif isinstance(item, str):
                try:
                    pages.append(int(item))
                except ValueError:
                    pass
            elif isinstance(item, dict):
                # Handle {leaf: N} or {page: N} structures
                for key in ("leaf", "page", "leaf_number", "page_number"):
                    if key in item:
                        try:
                            pages.append(int(item[key]))
                        except (ValueError, TypeError):
                            pass
        return pages
    return []


def compute_letter_ranges(entries: list[dict]) -> dict:
    """
    Compute expected page ranges for each letter using only entries
    with source_pages data. Uses the 10th-90th percentile to establish
    the "expected" range, then extends to min/max for the "hard" range.
    """
    letter_pages = defaultdict(list)

    for entry in entries:
        letter = get_letter(entry.get("headword", ""))
        pages = extract_pages(entry)
        if pages:
            letter_pages[letter].extend(pages)

    ranges = {}
    for letter in sorted(letter_pages.keys()):
        pages = sorted(letter_pages[letter])
        if len(pages) < 3:
            # Too few entries to establish a range
            ranges[letter] = {
                "min": min(pages),
                "max": max(pages),
                "p10": min(pages),
                "p90": max(pages),
                "median": pages[len(pages) // 2],
                "count": len(pages),
                "entry_count": 0,  # filled below
            }
        else:
            p10_idx = max(0, int(len(pages) * 0.10))
            p90_idx = min(len(pages) - 1, int(len(pages) * 0.90))
            ranges[letter] = {
                "min": pages[0],
                "max": pages[-1],
                "p10": pages[p10_idx],
                "p90": pages[p90_idx],
                "median": pages[len(pages) // 2],
                "count": len(pages),
                "entry_count": 0,
            }

    return ranges


def infer_expected_letter(page: int, letter_ranges: dict) -> str:
    """Given a page number, infer which letter section it belongs to."""
    best_letter = "?"
    best_dist = float("inf")

    for letter, r in letter_ranges.items():
        if letter == "?":
            continue
        if r["min"] <= page <= r["max"]:
            # Within hard range — check how central it is
            mid = r["median"]
            dist = abs(page - mid)
            if dist < best_dist:
                best_dist = dist
                best_letter = letter
        else:
            # Outside range — compute distance to nearest edge
            dist = min(abs(page - r["min"]), abs(page - r["max"]))
            if dist < best_dist:
                best_dist = dist
                best_letter = letter

    return best_letter


def find_monotonicity_breaks(entries_by_letter: dict) -> dict:
    """
    Within each letter, check that source pages are monotonically
    non-decreasing when entries are sorted by headword. Returns
    breaks where page numbers go backwards significantly.
    """
    breaks = defaultdict(list)

    for letter, entries in sorted(entries_by_letter.items()):
        # Sort by headword (alphabetical order within letter)
        sorted_entries = sorted(entries, key=lambda e: e["headword"].upper())

        prev_max_page = 0
        prev_entry = None

        for entry in sorted_entries:
            pages = extract_pages(entry)
            if not pages:
                continue

            entry_min = min(pages)
            entry_max = max(pages)

            # A significant backwards jump (more than 12 pages) is suspicious.
            # Threshold raised from 5 to 12 because the corpus has a systematic
            # ~11 page offset (leaf-number vs printed-page mixing) that causes
            # 3,190 false-positive breaks at 6-10 pages across all letters.
            if prev_max_page > 0 and entry_min < prev_max_page - 12:
                breaks[letter].append({
                    "entry_id": entry.get("id", ""),
                    "headword": entry.get("headword", ""),
                    "source_pages": pages,
                    "prev_headword": prev_entry.get("headword", "") if prev_entry else "",
                    "prev_pages": extract_pages(prev_entry) if prev_entry else [],
                    "backward_jump": prev_max_page - entry_min,
                })

            if entry_max > prev_max_page:
                prev_max_page = entry_max
                prev_entry = entry

    return dict(breaks)


def validate(entries: list[dict], include_empty: bool = False) -> dict:
    """Main validation logic."""

    # Group entries by letter
    entries_by_letter = defaultdict(list)
    for entry in entries:
        letter = get_letter(entry.get("headword", ""))
        entries_by_letter[letter].append(entry)

    # Compute letter ranges
    letter_ranges = compute_letter_ranges(entries)
    for letter, ents in entries_by_letter.items():
        if letter in letter_ranges:
            letter_ranges[letter]["entry_count"] = len(ents)

    # Find out-of-range entries using IQR-based outlier detection.
    # This is robust to contaminated data — a few misplaced entries
    # won't distort the expected range for the letter.
    out_of_range = []
    no_source_pages = []

    # Compute IQR bounds per letter
    letter_all_pages = defaultdict(list)
    for entry in entries:
        letter = get_letter(entry.get("headword", ""))
        pages = extract_pages(entry)
        if pages:
            letter_all_pages[letter].extend(pages)

    letter_iqr_bounds = {}
    for letter, pages in letter_all_pages.items():
        if len(pages) < 4:
            # Too few — use raw min/max with no outlier detection
            letter_iqr_bounds[letter] = (min(pages), max(pages))
            continue
        pages_sorted = sorted(pages)
        q1_idx = len(pages_sorted) // 4
        q3_idx = (3 * len(pages_sorted)) // 4
        q1 = pages_sorted[q1_idx]
        q3 = pages_sorted[q3_idx]
        iqr = q3 - q1
        # Use 2.0x IQR fence (slightly generous to avoid false positives
        # at letter boundaries where page ranges legitimately overlap)
        fence = max(iqr * 2.0, 30)  # minimum fence of 30 pages
        lower = q1 - fence
        upper = q3 + fence
        letter_iqr_bounds[letter] = (lower, upper)

    for entry in entries:
        letter = get_letter(entry.get("headword", ""))
        pages = extract_pages(entry)

        if not pages:
            no_source_pages.append({
                "id": entry.get("id", ""),
                "headword": entry.get("headword", ""),
                "letter": letter,
                "body_preview": entry.get("body", "")[:100],
            })
            continue

        if letter not in letter_iqr_bounds:
            continue

        lower, upper = letter_iqr_bounds[letter]
        r = letter_ranges.get(letter, {})
        entry_min = min(pages)
        entry_max = max(pages)

        if entry_min < lower or entry_max > upper:
            expected = infer_expected_letter(entry_min, letter_ranges)
            median = r.get("median", 0)
            out_of_range.append({
                "id": entry.get("id", ""),
                "headword": entry.get("headword", ""),
                "letter": letter,
                "source_pages": pages,
                "expected_range": [int(lower), int(upper)],
                "iqr_bounds": [int(lower), int(upper)],
                "inferred_letter": expected,
                "body_preview": entry.get("body", "")[:150],
                "body_length": len(entry.get("body", "")),
                "severity": "high" if abs(entry_min - median) > 200 else "medium",
            })

    # Find monotonicity breaks
    mono_breaks = find_monotonicity_breaks(entries_by_letter)

    # Build summary
    total_with_pages = len(entries) - len(no_source_pages)

    report = {
        "metadata": {
            "total_entries": len(entries),
            "entries_with_source_pages": total_with_pages,
            "entries_without_source_pages": len(no_source_pages),
        },
        "letter_ranges": {k: v for k, v in sorted(letter_ranges.items()) if k != "?"},
        "out_of_range_entries": sorted(out_of_range, key=lambda x: x["severity"], reverse=True),
        "out_of_range_count": len(out_of_range),
        "monotonicity_breaks": mono_breaks,
        "monotonicity_break_count": sum(len(v) for v in mono_breaks.values()),
    }

    if include_empty:
        report["entries_without_source_pages_sample"] = no_source_pages[:100]

    return report


def write_markdown(report: dict):
    lines = [
        "# Source Page Validation Report",
        "",
        "## Overview",
        "",
        f"- Total entries: {report['metadata']['total_entries']}",
        f"- With source_pages: {report['metadata']['entries_with_source_pages']}",
        f"- Without source_pages: {report['metadata']['entries_without_source_pages']}",
        f"- Out of range: **{report['out_of_range_count']}**",
        f"- Monotonicity breaks: **{report['monotonicity_break_count']}**",
        "",
        "## Letter Page Ranges",
        "",
        "Expected page ranges derived from entries with source_pages data.",
        "",
        "| Letter | Entries | Pages | Min | P10 | Median | P90 | Max |",
        "|--------|---------|-------|-----|-----|--------|-----|-----|",
    ]

    for letter, r in sorted(report["letter_ranges"].items()):
        lines.append(
            f"| {letter} | {r['entry_count']} | {r['count']} | "
            f"{r['min']} | {r['p10']} | {r['median']} | {r['p90']} | {r['max']} |"
        )

    lines.extend([
        "",
        "## Out-of-Range Entries",
        "",
        "These entries have source_pages that fall outside the expected range for their letter.",
        "They are likely misplaced entries with garbled headwords, or entries whose source_pages",
        "mapping is incorrect.",
        "",
        "| Severity | Headword | Letter | Source Pages | Expected Range | Inferred Letter | Body Preview |",
        "|----------|----------|--------|-------------|----------------|-----------------|--------------|",
    ])

    for e in report["out_of_range_entries"]:
        preview = e["body_preview"].replace("|", "/").replace("\n", " ")[:80]
        pages = ", ".join(str(p) for p in e["source_pages"])
        erange = f"{e['expected_range'][0]}-{e['expected_range'][1]}"
        lines.append(
            f"| {e['severity']} | {e['headword']} | {e['letter']} | "
            f"{pages} | {erange} | {e['inferred_letter']} | {preview} |"
        )

    if report["monotonicity_break_count"] > 0:
        lines.extend([
            "",
            "## Monotonicity Breaks",
            "",
            "Within a letter, entries should have non-decreasing source pages when sorted",
            "alphabetically. These entries show significant backward jumps (>5 pages).",
            "",
        ])

        for letter, breaks in sorted(report["monotonicity_breaks"].items()):
            if not breaks:
                continue
            lines.append(f"### Letter {letter} ({len(breaks)} breaks)")
            lines.append("")
            lines.append("| Headword | Pages | After | After Pages | Jump |")
            lines.append("|----------|-------|-------|-------------|------|")
            for b in breaks[:20]:  # cap at 20 per letter
                pages = ", ".join(str(p) for p in b["source_pages"])
                prev_pages = ", ".join(str(p) for p in b["prev_pages"])
                lines.append(
                    f"| {b['headword']} | {pages} | "
                    f"{b['prev_headword']} | {prev_pages} | -{b['backward_jump']} |"
                )
            if len(breaks) > 20:
                lines.append(f"| ... | ... | ... | ... | ({len(breaks) - 20} more) |")
            lines.append("")

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- **Out-of-range (high severity)**: source page is 200+ pages from the letter's median.",
        "  Almost certainly a misplaced entry. The body text likely defines a term from a",
        "  completely different part of the alphabet. Check the body and inferred letter.",
        "- **Out-of-range (medium severity)**: source page is outside the letter's range but",
        "  not drastically. Could be a letter-boundary edge case or a genuine misplacement.",
        "- **Monotonicity breaks**: within a correctly-placed letter, entries whose pages go",
        "  backwards suggest either headword ordering issues or source_pages mapping errors.",
        "",
        "## Recommended Actions",
        "",
        "For each out-of-range entry:",
        "1. Read the body text — what term is actually being defined?",
        "2. Check the inferred letter — does the body content match terms from that section?",
        "3. If the headword is garbled (e.g., 'I' but body says 'Fr. To drive, compel'),",
        "   the entry likely has an OCR-destroyed headword. The real headword can often be",
        "   recovered from the body's first sentence or from cross-references.",
        "4. Use the source_pages leaf number to look up the original scan on Internet Archive",
        "   and visually identify the correct headword.",
        "",
    ])

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote: {REPORT_MD}")


def main():
    parser = argparse.ArgumentParser(description="Validate source_pages consistency")
    parser.add_argument("--report-only", action="store_true",
                        help="Generate reports without suggesting mutations")
    parser.add_argument("--include-empty", action="store_true",
                        help="Include sample of entries with no source_pages")
    args = parser.parse_args()

    if not LIVE_CORPUS.exists():
        print(f"ERROR: {LIVE_CORPUS} not found. Run from repo root.")
        sys.exit(1)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading corpus...")
    entries = load_corpus()
    print(f"  {len(entries)} entries loaded")

    print("Validating source pages...")
    report = validate(entries, include_empty=args.include_empty)

    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {REPORT_JSON}")

    write_markdown(report)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"Entries with source_pages:    {report['metadata']['entries_with_source_pages']}")
    print(f"Entries without source_pages: {report['metadata']['entries_without_source_pages']}")
    print(f"Out-of-range entries:         {report['out_of_range_count']}")
    print(f"  High severity:              {sum(1 for e in report['out_of_range_entries'] if e['severity'] == 'high')}")
    print(f"  Medium severity:            {sum(1 for e in report['out_of_range_entries'] if e['severity'] == 'medium')}")
    print(f"Monotonicity breaks:          {report['monotonicity_break_count']}")
    print(f"{'=' * 60}")

    if report["out_of_range_count"] > 0:
        print(f"\nTop out-of-range entries:")
        for e in report["out_of_range_entries"][:10]:
            pages = ", ".join(str(p) for p in e["source_pages"])
            print(f"  [{e['severity']}] {e['headword']} (letter {e['letter']}, "
                  f"pages {pages}, expected {e['expected_range'][0]}-{e['expected_range'][1]}, "
                  f"inferred {e['inferred_letter']})")


if __name__ == "__main__":
    main()
