#!/usr/bin/env python3
"""
ocr_headword_scan.py — Find O-for-C OCR garbled headwords among legacy entries.

Only tries O→C substitutions (the dominant garble: OCR reads C as O).
Filters: corrected form must appear MORE often in corpus bodies than garbled form.
"""
import json
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LEGACY_PATH = REPO / "rebuild" / "out" / "blacks_entries.legacy_original.json"


def main():
    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)
    with LEGACY_PATH.open("r", encoding="utf-8") as f:
        legacy = json.load(f)

    legacy_by_term = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)

    all_overlay_terms = {e["term"] for e in overlay}

    # Build corpus text for word search
    corpus_text = ""
    for e in legacy:
        corpus_text += " " + (e.get("body") or "").upper()

    def count_word(term):
        pattern = re.escape(term.upper())
        rx = re.compile(r"(?<![A-Z])" + pattern + r"(?![A-Z])")
        return len(rx.findall(corpus_text))

    def corrected_in_own_body(garbled_term, corrected_term):
        """Check if the corrected form appears in the garbled entry's body."""
        le = legacy_by_term.get(garbled_term)
        if not le:
            return False
        body = (le.get("body") or "").upper()
        pattern = re.escape(corrected_term.upper())
        return bool(re.search(r"(?<![A-Z])" + pattern + r"(?![A-Z])", body))

    candidates = [
        e for e in overlay
        if e["entry_type"] in ("legacy_unresolved", "legacy_retained")
    ]

    results = []

    for entry in candidates:
        term = entry["term"]
        le = legacy_by_term.get(term)
        if not le:
            continue
        body = (le.get("body") or "").strip()
        if not body.upper().startswith(term.upper()):
            continue

        garbled_count = count_word(term)
        seen = set()

        def accept(garbled_t, corrected_t, g_count, c_count):
            """Decide if this correction is plausible."""
            # Skip very short terms (too many false positives)
            if len(corrected_t) < 4:
                return False
            # Strong signal: corrected form appears more than garbled
            if c_count > g_count:
                return True
            # Medium signal for longer terms: corrected form found in corpus
            # AND in the entry's own body
            if len(corrected_t) >= 6 and c_count >= 1:
                if corrected_in_own_body(garbled_t, corrected_t):
                    return True
            # Medium signal: corrected form found and garbled only once
            if len(corrected_t) >= 6 and c_count >= 1 and g_count <= 1:
                return True
            return False

        # Single O->C swaps
        for i, ch in enumerate(term):
            if ch == "O":
                corrected = term[:i] + "C" + term[i + 1:]
                if corrected in all_overlay_terms or corrected in seen:
                    continue
                seen.add(corrected)
                n = count_word(corrected)
                in_body = corrected_in_own_body(term, corrected)
                if accept(term, corrected, garbled_count, n):
                    results.append((
                        term, corrected, body[:80],
                        garbled_count, n, f"pos {i}: O->C",
                        in_body,
                    ))

        # Double O->C swaps
        o_positions = [i for i, ch in enumerate(term) if ch == "O"]
        if len(o_positions) >= 2:
            for a in range(len(o_positions)):
                for b in range(a + 1, len(o_positions)):
                    chars = list(term)
                    chars[o_positions[a]] = "C"
                    chars[o_positions[b]] = "C"
                    corrected = "".join(chars)
                    if corrected in all_overlay_terms or corrected in seen:
                        continue
                    seen.add(corrected)
                    n = count_word(corrected)
                    in_body = corrected_in_own_body(term, corrected)
                    if accept(term, corrected, garbled_count, n):
                        results.append((
                            term, corrected, body[:80],
                            garbled_count, n,
                            f"pos {o_positions[a]},{o_positions[b]}: O->C",
                            in_body,
                        ))

    # Deduplicate: best correction per garbled term (highest corpus count)
    best = {}
    for garbled, corrected, body_start, g_count, c_count, detail, in_body in results:
        if garbled not in best or c_count > best[garbled][4]:
            best[garbled] = (garbled, corrected, body_start, g_count, c_count, detail, in_body)

    # Also check for garbled entries whose corrected form IS in overlay
    # (these are duplicates, not headword corrections)
    duplicates = []
    for entry in candidates:
        term = entry["term"]
        le = legacy_by_term.get(term)
        if not le:
            continue
        for i, ch in enumerate(term):
            if ch == "O":
                corrected = term[:i] + "C" + term[i + 1:]
                if corrected in all_overlay_terms and corrected != term:
                    for oe in overlay:
                        if oe["term"] == corrected:
                            duplicates.append((term, corrected, oe["entry_type"]))
                            break
                    break

    for garbled, corrected, body_start, g_count, c_count, detail, in_body in sorted(best.values()):
        print(f"{garbled} -> {corrected}")
        print(f'  Body starts with: "{body_start}"')
        print(f'  Garbled "{garbled}" in corpus: {g_count} | Corrected "{corrected}": {c_count}')
        print(f"  Corrected in own body: {'Yes' if in_body else 'No'}")
        print(f"  Swap: {detail}")
        print(f"  Recommendation: CORRECT")
        print()

    if duplicates:
        print(f"\n=== DUPLICATE ENTRIES (corrected form already in overlay) ===")
        for garbled, corrected, target_type in sorted(set(duplicates)):
            print(f"  {garbled} -> {corrected} (exists as {target_type})")

    print(f"\n=== SUMMARY ===")
    print(f"Total candidates scanned: {len(candidates)}")
    print(f"Unique headword corrections: {len(best)}")
    if duplicates:
        print(f"Duplicate entries (target exists): {len(set(duplicates))}")


if __name__ == "__main__":
    main()
