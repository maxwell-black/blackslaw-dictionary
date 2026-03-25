#!/usr/bin/env python3
"""
fill_source_pages.py — Fill in missing source_pages for entries.

Matches headwords against OCR text in source_pages.jsonl to find the
printed page where each entry appears. Only assigns pages where the
headword appears as a clear match in the OCR text of that page.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_PAGES = REPO / "rebuild" / "out" / "source_pages.jsonl"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LIVE_CORPUS = REPO / "blacks_entries.json"


def load_page_index():
    """Load source_pages.jsonl and build a text index by page."""
    pages = []
    with open(SOURCE_PAGES, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            pp = rec.get("printed_page")
            if pp is None:
                continue
            text = "\n".join(rec.get("lines", []))
            pages.append({
                "leaf": rec["leaf"],
                "printed_page": str(pp),
                "text": text.upper(),
            })
    return pages


def find_page_for_term(term, pages, expected_range=None):
    """Find the printed page where a headword appears.

    Args:
        term: The headword to find
        pages: The page index from load_page_index()
        expected_range: Optional (min_page, max_page) tuple to narrow search

    Returns:
        List of page numbers (strings) where term was found, or []
    """
    term_upper = term.upper().strip()
    if not term_upper or len(term_upper) < 2:
        return []

    # Build search pattern — headword at start of line or after whitespace
    # Escape special regex characters
    escaped = re.escape(term_upper)
    pat = re.compile(r'(?:^|\n)\s*' + escaped + r'\s*[.,\n]', re.MULTILINE)

    found_pages = []
    for pg in pages:
        pp = int(pg["printed_page"])
        # Skip pages outside expected range (optimization)
        if expected_range:
            if pp < expected_range[0] - 2 or pp > expected_range[1] + 2:
                continue
        if pat.search(pg["text"]):
            found_pages.append(pg["printed_page"])

    return found_pages


def estimate_page_range(term, entries_with_pages):
    """Estimate expected page range for a term based on neighboring entries."""
    term_upper = term.upper()

    # Find entries just before and after this term alphabetically
    before_page = None
    after_page = None
    for t, pages in entries_with_pages:
        t_upper = t.upper()
        if t_upper < term_upper:
            before_page = max(int(p) for p in pages)
        elif t_upper > term_upper:
            after_page = min(int(p) for p in pages)
            break

    if before_page and after_page:
        return (before_page - 1, after_page + 1)
    elif before_page:
        return (before_page - 1, before_page + 10)
    elif after_page:
        return (after_page - 10, after_page + 1)
    return None


def main():
    print("Loading source pages index...")
    pages = load_page_index()
    print("  %d pages with printed numbers" % len(pages))

    print("Loading live corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    print("  %d entries" % len(entries))

    # Build list of entries sorted by term, with/without pages
    entries.sort(key=lambda e: e["term"].upper())

    missing = []
    entries_with_pages = []
    for e in entries:
        sp = e.get("source_pages", [])
        if sp:
            entries_with_pages.append((e["term"], sp))
        else:
            missing.append(e["term"])

    print("  %d entries missing source_pages" % len(missing))

    # Fill in missing source_pages
    print("\nSearching for headwords in OCR text...")
    found = {}
    not_found = []
    for i, term in enumerate(missing):
        if i % 200 == 0 and i > 0:
            print("  ...processed %d/%d" % (i, len(missing)))

        # Estimate page range
        expected = estimate_page_range(term, entries_with_pages)
        result = find_page_for_term(term, pages, expected)

        if result:
            # Take only pages in a reasonable range (max 3 pages)
            if len(result) <= 3:
                found[term] = result
            else:
                # Too many matches — headword appears too frequently, skip
                not_found.append(term)
        else:
            not_found.append(term)

    print("\n  Found pages for: %d entries" % len(found))
    print("  Not found: %d entries" % len(not_found))

    if not found:
        print("\nNothing to update.")
        return

    # Update overlay entries with found pages
    print("\nUpdating overlay...")
    with open(OVERLAY_PATH, encoding="utf-8") as f:
        overlay = json.load(f)

    overlay_by_term = {}
    for o in overlay:
        overlay_by_term[o["term"].upper()] = o

    updated = 0
    for term, page_list in found.items():
        key = term.upper()
        if key in overlay_by_term:
            o = overlay_by_term[key]
            if not o.get("source_pages"):
                o["source_pages"] = page_list
                updated += 1

    print("  Updated %d overlay entries" % updated)

    with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print("  Saved: %s" % OVERLAY_PATH)

    # Report
    print("\nSample of filled entries:")
    for term, pg in list(found.items())[:20]:
        print("  %s: %s" % (term, pg))


if __name__ == "__main__":
    main()
