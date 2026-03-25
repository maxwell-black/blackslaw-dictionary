#!/usr/bin/env python3
"""
apply_sonnet_corrections.py — Apply quality-gated Sonnet corrections to body_corrections.json.

Reads a sonnet_review_X.json report, filters corrections through quality gates,
and applies accepted OCR fixes and trims to body_corrections.json.

Usage: python apply_sonnet_corrections.py <letter>
"""

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BODY_CORRECTIONS = REPO / "rebuild" / "overlay" / "body_corrections.json"

# Known archaic/correct spellings that should NOT be "fixed"
ARCHAIC_TERMS = {
    "connexion", "shew", "shewn", "shewing", "colour", "honour", "favour",
    "judgement", "gaol", "waggon", "despatch", "enrol", "enrolment", "wilful",
    "amongst", "whilst", "towards", "afterwards", "honour", "favour", "labour",
    "colour", "behaviour", "defence", "offence", "licence", "practice",
    "counsellor", "traveller", "jewellery", "catalogue", "programme",
    "cheque", "grey", "plough", "draught", "mediaeval", "foetus",
    "oestrogen", "manoeuvre", "pederast", "encyclopaedia", "anaesthetic",
    "haemorrhage", "diarrhoea", "oesophagus", "paediatric", "gynaecology",
    "skilful", "fulfil", "instalment", "acknowledgement", "abridgement",
}

# Known Latin/French terms that should not be changed
LATIN_FRENCH_PATTERNS = re.compile(
    r'\b(habeas|certiorari|mandamus|res\s+judicata|cestui|chose|feme|'
    r'covert|quare|assumpsit|supersedeas|nisi\s+prius|scire\s+facias|'
    r'quo\s+warranto|fieri\s+facias|capias|mittimus|praecipe|'
    r'venire|voir\s+dire|amicus\s+curiae)\b', re.I
)


def is_archaic_false_positive(correction):
    """Check if an OCR fix is actually trying to 'fix' correct archaic spelling."""
    if correction.get("type") != "ocr_fix":
        return False

    old = correction.get("old", "").lower()
    new = correction.get("new", "").lower()

    # Check if the "old" text contains known archaic words being "corrected"
    for word in ARCHAIC_TERMS:
        if word in old and word not in new:
            return True

    # Check if it's trying to change Latin/French
    if LATIN_FRENCH_PATTERNS.search(old):
        return True

    return False


def apply_ocr_fix(body, old_text, new_text):
    """Apply an OCR fix to a body, return (new_body, success)."""
    if old_text in body:
        return body.replace(old_text, new_text, 1), True
    return body, False


def apply_trim(body, trim_at):
    """Trim body at the given marker, return (new_body, success)."""
    idx = body.find(trim_at)
    if idx > 0:
        # Trim at the marker, remove trailing whitespace
        trimmed = body[:idx].rstrip()
        if len(trimmed) > 20:  # Sanity check: don't trim to nothing
            return trimmed, True
    return body, False


def main():
    if len(sys.argv) < 2:
        print("Usage: python apply_sonnet_corrections.py <letter>")
        sys.exit(1)

    letter = sys.argv[1].upper()
    report_file = REPO / "rebuild" / "reports" / f"sonnet_review_{letter.lower()}.json"

    if not report_file.exists():
        print(f"ERROR: {report_file} not found")
        sys.exit(1)

    # Load report
    with open(report_file, encoding="utf-8") as f:
        report = json.load(f)

    corrections = report.get("corrections", [])
    print(f"Letter {letter}: {len(corrections)} raw corrections")

    # Load current entries to get bodies
    entries_file = REPO / "data" / f"entries_{letter.lower()}.json"
    with open(entries_file, encoding="utf-8") as f:
        entries = json.load(f)
    entry_bodies = {e["term"]: e.get("body", "") for e in entries}

    # Load body_corrections
    with open(BODY_CORRECTIONS, encoding="utf-8") as f:
        body_corrections = json.load(f)

    # Process corrections
    accepted_ocr = 0
    accepted_trim = 0
    rejected_archaic = 0
    rejected_headword = 0
    flagged = 0
    failed = 0
    flags_out = []

    for c in corrections:
        ctype = c.get("type", "")
        term = c.get("term", "")

        if ctype == "ocr_fix":
            # Quality gate: check for archaic false positives
            if is_archaic_false_positive(c):
                rejected_archaic += 1
                print(f"  REJECT archaic: {term} - {c.get('old','')} -> {c.get('new','')}")
                continue

            # Use entry body (what Sonnet reviewed) first, then body_corrections
            body = entry_bodies.get(term, "") or body_corrections.get(term, {}).get("body", "")
            if not body:
                failed += 1
                continue

            new_body, ok = apply_ocr_fix(body, c.get("old", ""), c.get("new", ""))
            if ok:
                body_corrections[term] = {"body": new_body, "_source": "sonnet_review"}
                accepted_ocr += 1
            else:
                failed += 1

        elif ctype == "trim":
            body = entry_bodies.get(term, "") or body_corrections.get(term, {}).get("body", "")
            if not body:
                failed += 1
                continue

            new_body, ok = apply_trim(body, c.get("trim_at", ""))
            if ok:
                body_corrections[term] = {"body": new_body, "_source": "sonnet_review"}
                accepted_trim += 1
            else:
                failed += 1

        elif ctype == "headword":
            # Headword fixes are complex — save as flags for manual review
            rejected_headword += 1
            flags_out.append({
                "type": "headword_review",
                "term": term,
                "suggested": c.get("correct", ""),
                "reason": c.get("reason", ""),
            })

        elif ctype == "flag":
            flagged += 1
            flags_out.append(c)

        else:
            print(f"  Unknown correction type: {ctype}")

    # Save body_corrections
    with open(BODY_CORRECTIONS, "w", encoding="utf-8") as f:
        json.dump(body_corrections, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # Save flags if any
    if flags_out:
        flags_file = REPO / "rebuild" / "reports" / f"sonnet_flags_{letter.lower()}.json"
        with open(flags_file, "w", encoding="utf-8") as f:
            json.dump(flags_out, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Flags saved: {flags_file}")

    print(f"\n  Accepted OCR fixes: {accepted_ocr}")
    print(f"  Accepted trims: {accepted_trim}")
    print(f"  Rejected (archaic): {rejected_archaic}")
    print(f"  Headword -> flagged: {rejected_headword}")
    print(f"  Flagged: {flagged}")
    print(f"  Failed to apply: {failed}")
    print(f"  Total corrections in body_corrections.json: {len(body_corrections)}")

    return accepted_ocr + accepted_trim


if __name__ == "__main__":
    count = main()
    sys.exit(0 if count >= 0 else 1)
