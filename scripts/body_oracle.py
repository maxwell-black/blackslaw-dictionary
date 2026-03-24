#!/usr/bin/env python3
"""
body_oracle.py — Headword correction pass for legacy_retained entries.

For each legacy_retained entry, inspects the body opening to extract a
candidate "true" headword, then applies a decision tree:
  - suppress as legacy_duplicate if body matches an existing canonical entry
  - correct headword if body-oracle form is a strong OCR correction
  - skip if ambiguous

Outputs: rebuild/reports/body_oracle_results.json

Usage:
    python scripts/body_oracle.py --report          # report only, no mutations
    python scripts/body_oracle.py --apply           # apply changes to overlay
"""

import json
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

# Force UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LEGACY_PATH = REPO / "rebuild" / "out" / "blacks_entries.legacy_original.json"
REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
REPORT_PATH = REPO / "rebuild" / "reports" / "body_oracle_results.json"

# OCR confusion pairs (source char -> likely intended char)
OCR_CONFUSIONS = {
    "O": "C", "C": "O",
    "I": "L", "L": "I",
    "U": "V", "V": "U",
    "M": "N", "N": "M",
    "H": "N", "Z": "S", "S": "Z",
}

# Known legitimate terms that should NOT be "corrected"
KNOWN_LEGIT = {
    "ABIATICUS", "ABISHERING", "ABSENTEES", "ABSQUE", "ACCEPTEUR",
    "ACCOUNT-BOOK", "ACCT", "ACCUMULATED", "ACRE", "AB ANTE",
    "AB INITIO", "AC", "AA", "A&E",
    # Add more as discovered
}

MIN_LEGACY_BODY = 40


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_body_oracle(term: str, body: str) -> str | None:
    """Extract candidate headword from body opening."""
    if not body or len(body) < 5:
        return None

    # Strip leading whitespace
    text = body.strip()

    # Pattern 1: Body starts with ALL-CAPS term before first period or comma
    # e.g. "ACCESSION. In property law, ..."
    m = re.match(r"^([A-Z][A-Z\s,'\-]{0,60}?)\s*[.,;:]", text)
    if m:
        candidate = m.group(1).strip().rstrip(",")
        # Don't return if it's just the original headword
        if candidate.upper() != term.upper():
            return candidate

    # Pattern 2: "See TERM" or "Same as TERM" at start
    m = re.match(r"^(?:See|Same as|Vide)\s+([A-Z][A-Z\s\-]{2,40}[A-Z])", text)
    if m:
        return m.group(1).strip()

    # Pattern 3: Body echoes headword then continues (headword appears at start)
    # The body literally starts with the garbled headword followed by definition
    m = re.match(r"^([A-Z][A-Z\s]{1,40}?)\s+(?:In |Lat\.|Fr\.|Sp\.|An? |The |One )", text)
    if m:
        candidate = m.group(1).strip()
        if candidate.upper() != term.upper():
            return candidate

    return None


def is_ocr_confusion(term_a: str, term_b: str) -> bool:
    """Check if two terms differ only by known OCR confusion characters."""
    if len(term_a) != len(term_b):
        # Allow length-1 differences (inserted/deleted char)
        if abs(len(term_a) - len(term_b)) > 1:
            return False

    # Check character-level differences
    diffs = 0
    a, b = term_a.upper(), term_b.upper()

    # Align with simple comparison for same-length
    if len(a) == len(b):
        for ca, cb in zip(a, b):
            if ca != cb:
                diffs += 1
                # Check if this is a known confusion
                if OCR_CONFUSIONS.get(ca) != cb and OCR_CONFUSIONS.get(cb) != ca:
                    return False
        return 0 < diffs <= 3
    else:
        # Use SequenceMatcher for length differences
        ratio = SequenceMatcher(None, a, b).ratio()
        return ratio >= 0.85


def body_similarity(body_a: str, body_b: str) -> float:
    """Compare first 300 chars of two bodies."""
    a = body_a[:300].strip()
    b = body_b[:300].strip()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def main():
    mode = "--report"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    print("Loading data...")
    overlay = load_json(OVERLAY_PATH)
    legacy = load_json(LEGACY_PATH)
    rebuilt = load_json(REBUILT_PATH)

    legacy_by_term = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)

    rebuilt_by_term = {}
    for e in rebuilt:
        rebuilt_by_term.setdefault(e["term"], e)

    # Build lookup of canonical entries (verified_main, provisional_main)
    canonical_types = {"verified_main", "provisional_main", "recovered_main"}
    canonical_by_term = {}
    for oe in overlay:
        if oe["entry_type"] in canonical_types:
            canonical_by_term[oe["term"].upper()] = oe

    # Also build a set of ALL live headwords for duplicate checking
    live_types = {
        "verified_main", "provisional_main", "recovered_main",
        "low_confidence_main", "alias_variant", "reversed_polarity",
        "unmatched_keep", "subentry", "headword_corrected",
    }
    all_live_terms = set()
    for oe in overlay:
        if oe["entry_type"] in live_types:
            all_live_terms.add(oe["term"].upper())
    # Also add legacy_unresolved that would be promoted
    for oe in overlay:
        if oe["entry_type"] == "legacy_unresolved":
            lb = legacy_by_term.get(oe["term"], {}).get("body", "")
            if len((lb or "").strip()) >= MIN_LEGACY_BODY:
                all_live_terms.add(oe["term"].upper())

    # Find all legacy_retained entries (legacy_unresolved with body >= 40)
    legacy_retained = []
    for oe in overlay:
        if oe["entry_type"] != "legacy_unresolved":
            continue
        term = oe["term"]
        lb = legacy_by_term.get(term, {}).get("body", "")
        if len((lb or "").strip()) >= MIN_LEGACY_BODY:
            legacy_retained.append(oe)

    print(f"Found {len(legacy_retained)} legacy_retained entries to analyze")

    # Results
    results = []
    corrections = []
    suppressions = []
    skipped = []

    for oe in legacy_retained:
        term = oe["term"]
        oe_id = oe["id"]

        # Get body from both sources
        legacy_body = (legacy_by_term.get(term, {}).get("body") or "").strip()
        rebuilt_body = (rebuilt_by_term.get(term, {}).get("body") or "").strip()

        # Prefer rebuilt, fall back to legacy
        body = rebuilt_body if rebuilt_body and len(rebuilt_body) > 20 else legacy_body

        # Extract candidate from body
        candidate = extract_body_oracle(term, body)

        result = {
            "id": oe_id,
            "term": term,
            "candidate": candidate,
            "decision": "skipped",
            "evidence": "",
            "confidence": "low",
            "body_preview": body[:100] if body else "",
        }

        if not candidate:
            result["evidence"] = "no candidate extracted from body"
            skipped.append(result)
            results.append(result)
            continue

        if term in KNOWN_LEGIT:
            result["evidence"] = "term in KNOWN_LEGIT set"
            skipped.append(result)
            results.append(result)
            continue

        # Check: does candidate match an existing canonical entry?
        candidate_upper = candidate.upper()

        if candidate_upper in canonical_by_term:
            # Potential duplicate — check body similarity
            canon_oe = canonical_by_term[candidate_upper]
            canon_term = canon_oe["term"]
            canon_body = (legacy_by_term.get(canon_term, {}).get("body") or "").strip()
            if not canon_body:
                canon_body = (rebuilt_by_term.get(canon_term, {}).get("body") or "").strip()

            sim = body_similarity(body, canon_body)

            if sim >= 0.8:
                result["decision"] = "suppress_duplicate"
                result["evidence"] = f"body matches canonical '{canon_term}' (similarity={sim:.3f})"
                result["confidence"] = "high"
                result["canonical_match"] = canon_term
                result["body_similarity"] = round(sim, 3)
                suppressions.append(result)
            else:
                result["decision"] = "skipped"
                result["evidence"] = f"candidate '{candidate}' matches canonical '{canon_term}' but bodies differ (similarity={sim:.3f})"
                result["confidence"] = "medium"
                result["canonical_match"] = canon_term
                result["body_similarity"] = round(sim, 3)
                skipped.append(result)

        elif candidate_upper != term.upper() and is_ocr_confusion(term, candidate):
            # Novel correction via OCR confusion
            if candidate_upper not in all_live_terms:
                result["decision"] = "correct_headword"
                result["evidence"] = f"body-oracle '{candidate}' is OCR-confusion variant of '{term}', novel headword"
                result["confidence"] = "high"
                corrections.append(result)
            else:
                result["decision"] = "skipped"
                result["evidence"] = f"body-oracle '{candidate}' already exists as live headword but not canonical; potential complex duplicate"
                result["confidence"] = "medium"
                skipped.append(result)

        elif candidate_upper == term.upper():
            # Body echoes headword — no correction needed
            result["decision"] = "skipped"
            result["evidence"] = "body echoes same headword"
            skipped.append(result)

        else:
            # Candidate extracted but doesn't match OCR pattern
            result["decision"] = "skipped"
            result["evidence"] = f"candidate '{candidate}' doesn't match OCR confusion patterns for '{term}'"
            result["confidence"] = "low"
            skipped.append(result)

        results.append(result)

    # Summary
    print(f"\nBody-oracle results:")
    print(f"  Corrections:   {len(corrections)}")
    print(f"  Suppressions:  {len(suppressions)}")
    print(f"  Skipped:       {len(skipped)}")

    if corrections:
        print(f"\nProposed corrections:")
        for c in corrections:
            print(f"  {c['term']} -> {c['candidate']}  ({c['evidence']})")

    if suppressions:
        print(f"\nProposed suppressions:")
        for s in suppressions:
            print(f"  {s['term']} -> duplicate of {s.get('canonical_match', '?')}  (sim={s.get('body_similarity', 0):.3f})")

    # Write report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "summary": {
            "total_analyzed": len(legacy_retained),
            "corrections": len(corrections),
            "suppressions": len(suppressions),
            "skipped": len(skipped),
        },
        "corrections": corrections,
        "suppressions": suppressions,
        "skipped_with_candidates": [s for s in skipped if s.get("candidate")],
        "results": results,
    }
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nReport: {REPORT_PATH}")

    # Apply if requested
    if mode == "--apply" and (corrections or suppressions):
        apply_changes(overlay, corrections, suppressions)


def apply_changes(overlay: list, corrections: list, suppressions: list):
    """Apply corrections and suppressions to the overlay."""
    correction_map = {c["id"]: c for c in corrections}
    suppression_ids = {s["id"] for s in suppressions}

    changed = 0
    for entry in overlay:
        eid = entry["id"]

        if eid in correction_map:
            c = correction_map[eid]
            entry["entry_type"] = "headword_corrected"
            entry["original_term"] = entry["term"]
            entry["term"] = c["candidate"]
            entry["body_oracle_evidence"] = c["evidence"]
            changed += 1

        elif eid in suppression_ids:
            s = next(x for x in suppressions if x["id"] == eid)
            entry["entry_type"] = "legacy_duplicate"
            entry["duplicate_of"] = s.get("canonical_match", "")
            entry["body_oracle_evidence"] = s["evidence"]
            changed += 1

    with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nApplied {changed} changes to overlay")


if __name__ == "__main__":
    main()
