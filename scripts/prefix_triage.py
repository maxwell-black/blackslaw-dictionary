#!/usr/bin/env python3
"""
prefix_triage.py — Classify prefix_of_matched entries into standalone/subentry/duplicate.

Uses body containment as the primary signal.
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LEGACY_PATH = REPO / "rebuild" / "out" / "blacks_entries.legacy_original.json"
CLASSIFICATION_PATH = REPO / "rebuild" / "reports" / "unmatched_classification.json"


def normalize_body(body):
    """Normalize body text for comparison."""
    return re.sub(r"\s+", " ", body.upper()).strip()


def body_contained_in(short_body, long_body, threshold=0.7):
    """Check if the shorter body is substantially contained in the longer body."""
    if not short_body or not long_body:
        return False, 0.0

    s = normalize_body(short_body)
    l = normalize_body(long_body)

    if not s or not l:
        return False, 0.0

    # Direct substring check
    if s in l:
        return True, 1.0

    # Check if most words of short body appear in long body
    s_words = set(s.split())
    l_words = set(l.split())
    if not s_words:
        return False, 0.0

    overlap = len(s_words & l_words) / len(s_words)
    if overlap > threshold:
        return True, overlap

    # Sequence similarity
    ratio = SequenceMatcher(None, s[:500], l[:500]).ratio()
    return ratio > threshold, ratio


def main():
    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)
    with LEGACY_PATH.open("r", encoding="utf-8") as f:
        legacy = json.load(f)
    with CLASSIFICATION_PATH.open("r", encoding="utf-8") as f:
        classification = json.load(f)

    legacy_by_term = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)

    overlay_by_term = {}
    for e in overlay:
        overlay_by_term.setdefault(e["term"], []).append(e)

    prefix_entries = classification.get("prefix_of_matched", [])
    print(f"Prefix entries to triage: {len(prefix_entries)}")

    standalone = []
    subentries = []
    duplicates = []
    no_body = []

    for pe in prefix_entries:
        term = pe["term"]
        matched_term = pe["matched_norm"]

        # Get legacy bodies
        le = legacy_by_term.get(term)
        short_body = (le.get("body") or "").strip() if le else ""

        # Find the matched (longer) entry's body
        matched_le = legacy_by_term.get(matched_term)
        long_body = (matched_le.get("body") or "").strip() if matched_le else ""

        # Get overlay info
        oe_list = overlay_by_term.get(term, [])
        oe = oe_list[0] if oe_list else None
        current_type = oe["entry_type"] if oe else "unknown"

        if not short_body or len(short_body) < 10:
            no_body.append({
                "term": term,
                "matched_term": matched_term,
                "body_length": len(short_body),
                "current_type": current_type,
            })
            continue

        is_contained, similarity = body_contained_in(short_body, long_body)

        result = {
            "term": term,
            "matched_term": matched_term,
            "body_length": len(short_body),
            "matched_body_length": len(long_body),
            "similarity": round(similarity, 2),
            "current_type": current_type,
            "body_preview": short_body[:80],
        }

        if is_contained and similarity > 0.85:
            # Body is nearly identical or a subset -> duplicate or subentry
            if similarity > 0.95:
                result["classification"] = "duplicate"
                duplicates.append(result)
            else:
                result["classification"] = "subentry"
                subentries.append(result)
        else:
            # Body is distinct -> standalone
            result["classification"] = "standalone"
            standalone.append(result)

    print(f"\nResults:")
    print(f"  Standalone:  {len(standalone)}")
    print(f"  Subentry:    {len(subentries)}")
    print(f"  Duplicate:   {len(duplicates)}")
    print(f"  No body:     {len(no_body)}")

    # Write report
    report = {
        "summary": {
            "total": len(prefix_entries),
            "standalone": len(standalone),
            "subentry": len(subentries),
            "duplicate": len(duplicates),
            "no_body": len(no_body),
        },
        "standalone": sorted(standalone, key=lambda x: x["term"]),
        "subentries": sorted(subentries, key=lambda x: x["term"]),
        "duplicates": sorted(duplicates, key=lambda x: x["term"]),
        "no_body": sorted(no_body, key=lambda x: x["term"]),
    }

    report_path = REPO / "rebuild" / "reports" / "prefix_triage_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\n--- SUBENTRIES ({len(subentries)}) ---")
    for s in subentries:
        print(f"  {s['term']} -> parent: {s['matched_term']} (sim={s['similarity']})")

    print(f"\n--- DUPLICATES ({len(duplicates)}) ---")
    for d in duplicates:
        print(f"  {d['term']} -> {d['matched_term']} (sim={d['similarity']})")

    print(f"\n--- NO BODY ({len(no_body)}) ---")
    for n in no_body[:10]:
        print(f"  {n['term']} (body={n['body_length']} chars)")
    if len(no_body) > 10:
        print(f"  ... and {len(no_body) - 10} more")

    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
