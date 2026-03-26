#!/usr/bin/env python3
"""
repair_source_pages.py — Fix source_pages for all entries using source_candidates.jsonl.

For each overlay entry:
  1. Match against source_candidates.jsonl by source_headword or norm_headword
  2. Convert leaves[] to printed page numbers (leaf - 11)
  3. Fall back to legacy corpus for unmatched entries
  4. Update the overlay with correct source_pages
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_CANDIDATES = REPO / "rebuild" / "out" / "source_candidates.jsonl"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LEGACY_CORPUS = REPO / "rebuild" / "out" / "blacks_entries.legacy_original.json"
LEAF_OFFSET = 11  # printed_page = leaf - 11


def normalize(term):
    """Normalize a term for matching."""
    return re.sub(r'[^A-Z0-9 ]', '', term.upper()).strip()


def load_source_candidates():
    """Load source_candidates.jsonl and build lookup by normalized headword."""
    by_norm = {}  # norm_headword -> list of (leaves, source_pages)
    by_source = {}  # source_headword upper -> list of (leaves, source_pages)

    with open(SOURCE_CANDIDATES, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            leaves = rec.get("leaves", [])
            sp = rec.get("source_pages", [])
            shw = rec.get("source_headword", "")
            nhw = rec.get("norm_headword", "")

            if leaves:
                entry = {"leaves": leaves, "source_pages": sp}
                if nhw:
                    key = normalize(nhw)
                    if key not in by_norm:
                        by_norm[key] = []
                    by_norm[key].append(entry)
                if shw:
                    key = normalize(shw)
                    if key not in by_source:
                        by_source[key] = []
                    by_source[key].append(entry)

    return by_norm, by_source


def leaves_to_pages(leaves):
    """Convert leaf numbers to printed page numbers as strings."""
    pages = []
    for leaf in leaves:
        pp = leaf - LEAF_OFFSET
        if pp > 0:
            pages.append(str(pp))
    return pages


def pick_best_match(matches, current_sp):
    """Pick the best match when multiple candidates exist.

    Prefer the one whose leaves produce pages closest to the current source_pages
    (if any), or take the first entry with a reasonable leaf range.
    """
    if len(matches) == 1:
        return matches[0]

    # Filter out entries with very low leaf numbers (front matter)
    valid = [m for m in matches if any(l >= 12 for l in m["leaves"])]
    if not valid:
        valid = matches

    if len(valid) == 1:
        return valid[0]

    # If we have existing source_pages, pick closest
    if current_sp:
        try:
            current_page = int(current_sp[0])
            best = None
            best_dist = float("inf")
            for m in valid:
                pages = leaves_to_pages(m["leaves"])
                if pages:
                    dist = abs(int(pages[0]) - current_page)
                    if dist < best_dist:
                        best_dist = dist
                        best = m
            if best:
                return best
        except (ValueError, IndexError):
            pass

    # Default: take the match with the most common leaf range for this letter
    return valid[0]


def main():
    print("Loading source candidates...")
    by_norm, by_source = load_source_candidates()
    print(f"  {len(by_norm)} unique normalized headwords")
    print(f"  {len(by_source)} unique source headwords")

    print("Loading overlay...")
    with open(OVERLAY_PATH, encoding="utf-8") as f:
        overlay = json.load(f)
    print(f"  {len(overlay)} entries")

    # Load legacy corpus for fallback
    print("Loading legacy corpus...")
    legacy_sp = {}
    if LEGACY_CORPUS.exists():
        with open(LEGACY_CORPUS, encoding="utf-8") as f:
            legacy = json.load(f)
        for e in legacy:
            sp = e.get("source_pages", [])
            if sp:
                legacy_sp[normalize(e["term"])] = sp
        print(f"  {len(legacy_sp)} entries with source_pages")
    else:
        print("  Legacy corpus not found, skipping fallback")

    # Process overlay entries
    updated = 0
    filled = 0
    already_correct = 0
    no_match = 0
    legacy_used = 0

    for entry in overlay:
        term = entry.get("term", "")
        current_sp = entry.get("source_pages", [])
        norm_term = normalize(term)

        # Try matching in source_candidates
        matches = by_norm.get(norm_term, []) or by_source.get(norm_term, [])

        if matches:
            best = pick_best_match(matches, current_sp)
            new_pages = leaves_to_pages(best["leaves"])

            if not new_pages:
                if not current_sp:
                    no_match += 1
                continue

            # Ensure pages are strings
            new_pages = [str(p) for p in new_pages]

            if current_sp == new_pages:
                already_correct += 1
                continue

            if not current_sp:
                # Fill missing
                entry["source_pages"] = new_pages
                filled += 1
            else:
                # Update existing (potentially wrong) value
                entry["source_pages"] = new_pages
                updated += 1
        else:
            # Fallback to legacy corpus
            if norm_term in legacy_sp:
                legacy_pages = legacy_sp[norm_term]
                # Ensure strings
                legacy_pages = [str(p) for p in legacy_pages]
                if current_sp != legacy_pages:
                    entry["source_pages"] = legacy_pages
                    legacy_used += 1
                    if not current_sp:
                        filled += 1
                    else:
                        updated += 1
            else:
                if not current_sp:
                    no_match += 1

    print(f"\n=== Results ===")
    print(f"  Already correct: {already_correct}")
    print(f"  Filled (was empty): {filled}")
    print(f"  Updated (was wrong): {updated}")
    print(f"  From legacy corpus: {legacy_used}")
    print(f"  No match found: {no_match}")

    # Check remaining missing
    still_missing = sum(1 for e in overlay if not e.get("source_pages"))
    print(f"  Still missing: {still_missing}")

    # Save
    with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\n  Saved: {OVERLAY_PATH}")


if __name__ == "__main__":
    main()
