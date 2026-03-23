#!/usr/bin/env python3
"""
missing_entries_scan.py — Page-window recovery scan for genuinely missing entries.

Searches source_pages.jsonl for headwords within estimated page windows
based on alphabetical neighbors in the overlay.
"""
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
CLASSIFICATION_PATH = REPO / "rebuild" / "reports" / "unmatched_classification.json"
SOURCE_PAGES_PATH = REPO / "rebuild" / "out" / "source_pages.jsonl"


def normalize_ocr(text):
    """Apply common OCR normalization for matching."""
    text = text.replace("!", "I").replace("1", "I").replace("|", "I")
    text = text.replace("0", "O")
    text = text.replace("Z", "E")  # less common, but happens
    return text


def main():
    # Load overlay
    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)

    # Build sorted list of entries with source_pages for neighbor lookup
    entries_with_pages = []
    for e in overlay:
        pages = e.get("source_pages", [])
        if pages:
            int_pages = [int(p) for p in pages if str(p).isdigit()]
            if int_pages:
                entries_with_pages.append((e["term"], int_pages))
    entries_with_pages.sort(key=lambda x: x[0].upper())
    neighbor_terms = [t for t, _ in entries_with_pages]

    # Load classification report
    with CLASSIFICATION_PATH.open("r", encoding="utf-8") as f:
        classification = json.load(f)

    genuinely_missing = classification.get("genuinely_missing", [])
    if isinstance(genuinely_missing, dict):
        genuinely_missing = genuinely_missing.get("entries", [])

    # If it's a list of strings, use as-is. If list of dicts, extract term.
    if genuinely_missing and isinstance(genuinely_missing[0], dict):
        missing_terms = [e.get("term", e.get("headword", "")) for e in genuinely_missing]
    else:
        missing_terms = genuinely_missing

    print(f"Total genuinely_missing entries: {len(missing_terms)}")

    # Load source pages indexed by leaf AND build printed_page -> leaf mapping
    source_pages = {}
    printed_to_leaves = {}
    with SOURCE_PAGES_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            page = json.loads(line)
            leaf = page.get("leaf")
            if leaf is not None:
                leaf_int = int(leaf) if isinstance(leaf, str) else leaf
                source_pages[leaf_int] = page
                pp = page.get("printed_page")
                if pp is not None:
                    pp_int = int(pp) if isinstance(pp, str) else pp
                    printed_to_leaves.setdefault(pp_int, []).append(leaf_int)

    all_leaves = sorted(source_pages.keys())
    print(f"Loaded {len(source_pages)} source pages")

    import bisect

    def find_leaf_window(term):
        """Find expected leaf window based on alphabetical neighbors.

        Overlay source_pages uses printed page numbers.
        We convert to leaf numbers for searching.
        """
        term_upper = term.upper()
        idx = bisect.bisect_left(neighbor_terms, term_upper,
                                  key=lambda x: x.upper())

        # Get nearest neighbors with pages (these are printed page numbers)
        before_pages = []
        after_pages = []

        # Look back
        for i in range(max(0, idx - 1), max(0, idx - 5), -1):
            if i < len(entries_with_pages):
                before_pages.extend(entries_with_pages[i][1])
                if before_pages:
                    break

        # Look forward
        for i in range(min(idx, len(entries_with_pages) - 1),
                       min(idx + 5, len(entries_with_pages))):
            after_pages.extend(entries_with_pages[i][1])
            if after_pages:
                break

        all_printed = before_pages + after_pages
        if not all_printed:
            return None, None

        # Expand window in printed page space
        min_printed = min(all_printed) - 3
        max_printed = max(all_printed) + 3

        # Convert to leaf numbers
        leaf_nums = set()
        for pp in range(min_printed, max_printed + 1):
            for leaf in printed_to_leaves.get(pp, []):
                leaf_nums.add(leaf)

        if not leaf_nums:
            # Fallback: estimate leaf from printed page (offset ~11)
            for pp in range(min_printed, max_printed + 1):
                est_leaf = pp + 11  # typical offset
                if est_leaf in source_pages:
                    leaf_nums.add(est_leaf)
                # Try nearby
                for delta in range(-2, 3):
                    if (pp + 11 + delta) in source_pages:
                        leaf_nums.add(pp + 11 + delta)

        if not leaf_nums:
            return None, None

        return min(leaf_nums), max(leaf_nums)

    # Search for each missing term
    found = []
    not_found = []

    for term in missing_terms:
        if not term or len(term) < 2:
            not_found.append((term, None, None, "too_short"))
            continue

        min_leaf, max_leaf = find_leaf_window(term)
        if min_leaf is None:
            not_found.append((term, None, None, "no_neighbor_pages"))
            continue

        term_upper = term.upper()
        term_norm = normalize_ocr(term_upper)
        best_match = None

        for leaf_num in range(min_leaf, max_leaf + 1):
            page = source_pages.get(leaf_num)
            if not page:
                continue

            # Get page text - try different field names
            text = page.get("text", "")
            if not text:
                lines = page.get("lines", [])
                if isinstance(lines, list):
                    text = "\n".join(
                        l if isinstance(l, str) else l.get("text", "")
                        for l in lines
                    )

            if not text:
                continue

            text_upper = text.upper()
            text_lines = text_upper.split("\n")

            # Method 1: exact prefix match (line starts with term)
            for line in text_lines:
                line_stripped = line.strip()
                if line_stripped.startswith(term_upper):
                    after = line_stripped[len(term_upper):]
                    if not after or after[0] in " .,;:()":
                        snippet = line_stripped[:100]
                        printed = page.get("printed_page", "?")
                        best_match = (term, leaf_num, printed, "exact_prefix", snippet)
                        break
            if best_match:
                break

            # Method 2: OCR-normalized prefix match
            text_norm = normalize_ocr(text_upper)
            norm_lines = text_norm.split("\n")
            for line in norm_lines:
                line_stripped = line.strip()
                if line_stripped.startswith(term_norm):
                    after = line_stripped[len(term_norm):]
                    if not after or after[0] in " .,;:()":
                        snippet = line_stripped[:100]
                        printed = page.get("printed_page", "?")
                        best_match = (term, leaf_num, printed, "ocr_normalized", snippet)
                        break
            if best_match:
                break

            # Method 3: fuzzy substring (term appears anywhere in page)
            if len(term_upper) >= 4:  # skip very short terms
                for line in text_lines:
                    line_stripped = line.strip()
                    pos = line_stripped.find(term_upper)
                    if pos >= 0:
                        # Check it's at a word boundary
                        before_ok = pos == 0 or not line_stripped[pos - 1].isalpha()
                        after_pos = pos + len(term_upper)
                        after_ok = (after_pos >= len(line_stripped) or
                                    not line_stripped[after_pos].isalpha())
                        if before_ok and after_ok:
                            start = max(0, pos - 10)
                            snippet = line_stripped[start:start + 100]
                            printed = page.get("printed_page", "?")
                            best_match = (term, leaf_num, printed,
                                          "fuzzy_substring", snippet)
                            break
            if best_match:
                break

        if best_match:
            found.append(best_match)
        else:
            not_found.append((term, min_leaf, max_leaf, "not_found"))

    # Print report
    print(f"\n{'=' * 70}")
    print("SECTION 1: RECOVERABLE ENTRIES")
    print(f"{'=' * 70}")
    print(f"({len(found)} entries)\n")

    for term, leaf, printed, method, snippet in sorted(found, key=lambda x: x[1]):
        print(f"{term}")
        print(f"  Found on leaf: {leaf} (printed page: {printed})")
        print(f"  Method: {method}")
        print(f"  Matching line: \"{snippet}\"")
        print()

    print(f"\n{'=' * 70}")
    print("SECTION 2: NOT FOUND")
    print(f"{'=' * 70}")
    print(f"({len(not_found)} entries)\n")

    for term, min_l, max_l, reason in sorted(not_found, key=lambda x: x[0].upper()):
        if min_l is not None:
            print(f"{term}")
            print(f"  Search window: leaves {min_l}-{max_l}")
            print(f"  Reason: {reason}")
        else:
            print(f"{term}")
            print(f"  Reason: {reason}")
        print()

    print(f"\n{'=' * 70}")
    print("SECTION 3: SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total genuinely_missing: {len(missing_terms)}")
    print(f"Recoverable:            {len(found)} ({100*len(found)/max(len(missing_terms),1):.1f}%)")
    print(f"Not found:              {len(not_found)} ({100*len(not_found)/max(len(missing_terms),1):.1f}%)")

    by_method = {}
    for _, _, _, method, _ in found:
        by_method[method] = by_method.get(method, 0) + 1
    print(f"\nRecovery by method:")
    for method, count in sorted(by_method.items(), key=lambda x: -x[1]):
        print(f"  {method:20s} {count:>4}")


if __name__ == "__main__":
    main()
