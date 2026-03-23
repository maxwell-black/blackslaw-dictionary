#!/usr/bin/env python3
"""
unverified_triage.py — Classify legacy_unresolved entries for quality.

Categories:
- fragment: body < 50 chars, likely a scan fragment
- stub: body 50-100 chars, may be valid but suspicious
- normal: body >= 100 chars, probably legitimate entry
- no_hw_start: body doesn't start with headword (might be sub-entry filed wrong)

Usage:
  python scripts/unverified_triage.py --report
  python scripts/unverified_triage.py --suppress-fragments  # Mark fragments as fragment_artifact
"""
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LIVE_PATH = REPO / "blacks_entries.json"


def main():
    mode = "--report"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)
    with LIVE_PATH.open("r", encoding="utf-8") as f:
        live_entries = json.load(f)

    live_by_term = {e["term"]: e for e in live_entries}

    lu_live = [
        e for e in overlay
        if e["entry_type"] == "legacy_unresolved" and e["term"] in live_by_term
    ]

    fragments = []
    stubs = []
    normal = []

    for oe in lu_live:
        term = oe["term"]
        body = (live_by_term[term].get("body") or "").strip()
        body_len = len(body)

        # Check if body starts with headword
        starts_with_hw = body.upper().startswith(term.upper())

        # Check if body looks like a fragment (partial sentence, no period at end)
        is_fragment = (
            body_len < 50
            or (body_len < 80 and not body.rstrip().endswith("."))
            or (body_len < 60 and not starts_with_hw)
        )

        entry_info = {
            "term": term,
            "body_len": body_len,
            "starts_with_hw": starts_with_hw,
            "body_preview": body[:100],
            "id": oe["id"],
        }

        if body_len < 50:
            fragments.append(entry_info)
        elif body_len < 100:
            stubs.append(entry_info)
        else:
            normal.append(entry_info)

    print(f"Total legacy_unresolved in live: {len(lu_live)}")
    print(f"  Fragments (< 50 chars): {len(fragments)}")
    print(f"  Stubs (50-100 chars): {len(stubs)}")
    print(f"  Normal (>= 100 chars): {len(normal)}")

    print(f"\n=== FRAGMENTS ({len(fragments)}) ===")
    for f_entry in sorted(fragments, key=lambda x: x["body_len"]):
        print(f"  [{f_entry['body_len']:3d}] {f_entry['term']}: {f_entry['body_preview']}")

    print(f"\n=== STUBS (first 30 of {len(stubs)}) ===")
    for s in sorted(stubs, key=lambda x: x["body_len"])[:30]:
        print(f"  [{s['body_len']:3d}] {s['term']}: {s['body_preview']}")

    # Write report
    report = {
        "summary": {
            "total": len(lu_live),
            "fragments": len(fragments),
            "stubs": len(stubs),
            "normal": len(normal),
        },
        "fragments": sorted(fragments, key=lambda x: x["term"]),
        "stubs": sorted(stubs, key=lambda x: x["term"]),
    }
    report_path = REPO / "rebuild" / "reports" / "unverified_triage_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nReport: {report_path}")

    if mode == "--suppress-fragments":
        suppress_fragments(overlay, fragments)


def suppress_fragments(overlay, fragments):
    """Mark fragment entries as fragment_artifact in the overlay."""
    fragment_terms = {f["term"] for f in fragments}

    changed = 0
    for entry in overlay:
        if entry["term"] in fragment_terms and entry["entry_type"] == "legacy_unresolved":
            entry["entry_type"] = "fragment_artifact"
            entry["fragment_reason"] = "body < 50 chars, likely scan fragment"
            changed += 1

    with OVERLAY_PATH.open("w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nSuppressed {changed} fragments in overlay")


if __name__ == "__main__":
    main()
