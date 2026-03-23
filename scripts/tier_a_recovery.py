#!/usr/bin/env python3
"""
tier_a_recovery.py — Extract full entry bodies for Tier A (exact_prefix) recoverable entries.

For each exact_prefix hit from the missing entries scan:
1. Find the headword line on the source page
2. Extract body text from that line until the next headword or end of page
3. Check for duplicates against existing live build entries
4. Produce a report for review
"""
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
SOURCE_PAGES_PATH = REPO / "rebuild" / "out" / "source_pages.jsonl"
LEGACY_PATH = REPO / "rebuild" / "out" / "blacks_entries.legacy_original.json"
LIVE_PATH = REPO / "blacks_entries.json"
RECOVERY_REPORT_PATH = REPO / "rebuild" / "reports" / "missing_entries_recovery.txt"

# Headword pattern: ALL CAPS line that starts a new entry
# Must start with a letter, be mostly uppercase, and be substantial
HEADWORD_RE = re.compile(
    r"^([A-Z][A-Z\s,;.\-\'()/]+)$"
)

# More conservative: line is all caps and at least 3 chars
HEADWORD_SIMPLE_RE = re.compile(r"^[A-Z][A-Z\s\-,;.\'()]{2,}$")


def get_page_text(page):
    """Extract full text from a source page."""
    text = page.get("text", "")
    if not text:
        lines = page.get("lines", [])
        if isinstance(lines, list):
            text = "\n".join(
                l if isinstance(l, str) else l.get("text", "")
                for l in lines
            )
    return text


def is_headword_line(line, min_len=3):
    """Check if a line looks like a dictionary headword (all caps, standalone)."""
    stripped = line.strip()
    if len(stripped) < min_len:
        return False
    # Must be mostly uppercase letters
    alpha_chars = [c for c in stripped if c.isalpha()]
    if not alpha_chars:
        return False
    upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
    if upper_ratio < 0.85:
        return False
    # Must start with a capital letter
    if not stripped[0].isupper():
        return False
    # Should not be too long (headwords are typically < 60 chars)
    if len(stripped) > 70:
        return False
    return True


def extract_entry_body(page_text, term, start_line_idx, lines):
    """Extract the entry body starting from the headword line.

    Continues until the next headword-like line or end of page.
    Returns the extracted body text.
    """
    body_lines = []
    term_upper = term.upper()

    # Start from the headword line itself
    first_line = lines[start_line_idx].strip()

    # Remove the headword from the start of the first line
    if first_line.upper().startswith(term_upper):
        remainder = first_line[len(term_upper):].lstrip(" .,;:")
        if remainder:
            body_lines.append(remainder)

    # Continue with subsequent lines
    for i in range(start_line_idx + 1, len(lines)):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            # Blank line — could be paragraph break or entry separator
            # Keep it for now, we'll clean up later
            body_lines.append("")
            continue

        # Check if this line starts a new headword entry
        if is_headword_line(stripped) and stripped.upper() != term_upper:
            # This looks like a new entry — stop here
            break

        body_lines.append(stripped)

    # Clean up: remove trailing blank lines
    while body_lines and not body_lines[-1].strip():
        body_lines.pop()

    return "\n".join(body_lines)


def main():
    # Load overlay for duplicate checking
    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)

    overlay_terms = {e["term"]: e for e in overlay}
    overlay_terms_upper = {e["term"].upper(): e for e in overlay}

    # Load live build for duplicate checking
    with LIVE_PATH.open("r", encoding="utf-8") as f:
        live = json.load(f)
    live_terms = {e["term"].upper() for e in live}

    # Load legacy for body comparison
    with LEGACY_PATH.open("r", encoding="utf-8") as f:
        legacy = json.load(f)
    legacy_by_term = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)

    # Load source pages
    source_pages = {}
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

    # Parse recovery report for exact_prefix entries
    with RECOVERY_REPORT_PATH.open("r", encoding="utf-8", errors="replace") as f:
        report_text = f.read()

    section1 = report_text.split("SECTION 1: RECOVERABLE ENTRIES")[1].split("SECTION 2:")[0]

    tier_a_entries = []
    lines = section1.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if (line and not line.startswith("(") and not line.startswith("=")
                and not line.startswith("Found") and not line.startswith("Method")
                and not line.startswith("Matching")):
            term = line
            leaf = None
            method = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                dl = lines[j].strip()
                if dl.startswith("Found on leaf:"):
                    m = re.match(r"Found on leaf: (\d+)", dl)
                    if m:
                        leaf = int(m.group(1))
                elif dl.startswith("Method:"):
                    method = dl.split("Method:")[1].strip()
            if leaf is not None and method == "exact_prefix":
                tier_a_entries.append((term, leaf))
        i += 1

    print(f"Tier A (exact_prefix) entries to process: {len(tier_a_entries)}")
    print()

    # Process each Tier A entry
    results = []
    duplicates = []

    for term, leaf in tier_a_entries:
        page = source_pages.get(leaf)
        if not page:
            results.append({
                "term": term,
                "leaf": leaf,
                "status": "ERROR",
                "reason": f"Source page leaf {leaf} not found",
            })
            continue

        page_text = get_page_text(page)
        if not page_text:
            results.append({
                "term": term,
                "leaf": leaf,
                "status": "ERROR",
                "reason": "Empty page text",
            })
            continue

        page_lines = page_text.split("\n")
        term_upper = term.upper()

        # Find the headword line
        start_idx = None
        for idx, pl in enumerate(page_lines):
            if pl.strip().upper().startswith(term_upper):
                after = pl.strip().upper()[len(term_upper):]
                if not after or after[0] in " .,;:()'-":
                    start_idx = idx
                    break

        if start_idx is None:
            results.append({
                "term": term,
                "leaf": leaf,
                "status": "ERROR",
                "reason": "Headword line not found on page",
            })
            continue

        # Extract body
        body = extract_entry_body(page_text, term, start_idx, page_lines)

        # Check for duplicates
        in_live = term.upper() in live_terms
        in_overlay = term in overlay_terms

        # Check if it exists under a garbled name
        garbled_match = None
        if not in_overlay:
            # Check legacy entries for similar terms
            for lt in legacy_by_term:
                if lt == term:
                    continue
                # Simple check: same length, differ by 1-2 chars
                if abs(len(lt) - len(term)) <= 1:
                    diffs = sum(1 for a, b in zip(lt, term) if a != b)
                    diffs += abs(len(lt) - len(term))
                    if diffs <= 2 and lt in overlay_terms:
                        oe = overlay_terms[lt]
                        if oe["entry_type"] in ("legacy_unresolved", "legacy_retained"):
                            garbled_match = lt

        status = "RECOVER"
        notes = []

        if in_live:
            status = "DUPLICATE"
            notes.append(f"Already in live build as '{term}'")
        if in_overlay:
            oe = overlay_terms[term]
            if oe["entry_type"] not in ("legacy_unresolved", "fragment_artifact",
                                         "junk_headword", "appendix_abbrev"):
                status = "DUPLICATE"
                notes.append(f"Already in overlay as {oe['entry_type']}")
            else:
                notes.append(f"In overlay as {oe['entry_type']} (will upgrade)")
        if garbled_match:
            notes.append(f"Possible garbled duplicate: {garbled_match}")

        legacy_body = (legacy_by_term.get(term, {}).get("body") or "").strip()
        printed_page = page.get("printed_page", "?")

        results.append({
            "term": term,
            "leaf": leaf,
            "printed_page": printed_page,
            "status": status,
            "body_preview": body[:150] if body else "(empty)",
            "body_length": len(body),
            "legacy_body_length": len(legacy_body),
            "notes": "; ".join(notes) if notes else "",
        })

    # Print report
    recover_count = sum(1 for r in results if r["status"] == "RECOVER")
    dup_count = sum(1 for r in results if r["status"] == "DUPLICATE")
    err_count = sum(1 for r in results if r["status"] == "ERROR")

    print(f"=" * 80)
    print(f"TIER A RECOVERY REPORT")
    print(f"=" * 80)
    print(f"Total exact_prefix entries: {len(results)}")
    print(f"  RECOVER:   {recover_count}")
    print(f"  DUPLICATE: {dup_count}")
    print(f"  ERROR:     {err_count}")
    print()

    print(f"--- RECOVERABLE ENTRIES ({recover_count}) ---")
    print()
    for idx, r in enumerate(results, 1):
        if r["status"] != "RECOVER":
            continue
        print(f"{idx:>3}. {r['term']}")
        print(f"     Leaf: {r['leaf']} (printed page: {r['printed_page']})")
        print(f"     DjVu body ({r['body_length']} chars): \"{r['body_preview']}\"")
        if r["legacy_body_length"]:
            print(f"     Legacy body: {r['legacy_body_length']} chars")
        if r["notes"]:
            print(f"     Notes: {r['notes']}")
        print()

    if dup_count:
        print(f"--- DUPLICATES ({dup_count}) ---")
        print()
        for r in results:
            if r["status"] == "DUPLICATE":
                print(f"  {r['term']}: {r['notes']}")
        print()

    if err_count:
        print(f"--- ERRORS ({err_count}) ---")
        print()
        for r in results:
            if r["status"] == "ERROR":
                print(f"  {r['term']}: {r['reason']}")
        print()


if __name__ == "__main__":
    main()
