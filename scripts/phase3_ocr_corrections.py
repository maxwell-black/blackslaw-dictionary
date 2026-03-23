#!/usr/bin/env python3
"""
phase3_ocr_corrections.py — Conservative OCR headword correction for Phase 3.

Scans legacy_retained and legacy_unresolved entries for O-for-C garbles.
Only proposes corrections where ALL safety checks pass.

Outputs a JSON report of proposed actions. Does NOT modify the overlay.
"""
import json
import re
from pathlib import Path
from collections import Counter

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
    overlay_by_term = {}
    for e in overlay:
        overlay_by_term.setdefault(e["term"], []).append(e)

    # Build corpus word frequency from ALL legacy bodies
    corpus_text_upper = ""
    for e in legacy:
        corpus_text_upper += " " + (e.get("body") or "").upper()

    def count_in_corpus(term):
        pattern = re.escape(term.upper())
        rx = re.compile(r"(?<![A-Z])" + pattern + r"(?![A-Z])")
        return len(rx.findall(corpus_text_upper))

    def in_own_body(garbled_term, corrected_term):
        le = legacy_by_term.get(garbled_term)
        if not le:
            return False
        body = (le.get("body") or "").upper()
        pattern = re.escape(corrected_term.upper())
        return bool(re.search(r"(?<![A-Z])" + pattern + r"(?![A-Z])", body))

    def body_starts_with(term):
        le = legacy_by_term.get(term)
        if not le:
            return False
        body = (le.get("body") or "").strip().upper()
        return body.startswith(term.upper())

    # Known legitimate terms that should NEVER be corrected
    # These are real Latin/French/archaic English terms that happen to contain
    # O-for-C-looking sequences
    KNOWN_LEGIT = {
        "ACROACH", "ACROOCHER", "ACOROOCHER", "ACOROACH",
        "GARD", "FERMER", "DALE", "SPITAL", "STAPULA",
        "ROUTOUSLY", "INROLL", "ENROLL", "ENROL",
        "DROIT", "EXPLOIT", "FOISON", "OYER",
        "VOITURE", "SEISOR", "DISSEISSOR",
        "AGIO", "RATIO", "ORATIO", "COGNOVIT",
        "SERVO", "PROVO", "PROVOST",
        # Short terms where O<->C swap produces another real word
        "OUT", "CUT", "COT", "COD", "COG", "COP", "COR",
        "COW", "CRO", "CUR", "OAR", "OAT", "ORE",
        "EO", "REO", "GO", "GC", "AO", "AC",
        "ALIO", "DIANATIO", "USUCAPIO",
    }

    candidates = [
        e for e in overlay
        if e["entry_type"] in ("legacy_unresolved", "legacy_retained")
    ]

    corrections = []  # headword_corrected
    duplicates = []   # legacy_duplicate (target exists as verified_main)

    for entry in candidates:
        term = entry["term"]

        if term in KNOWN_LEGIT:
            continue
        if len(term) < 4:
            continue
        if not body_starts_with(term):
            continue

        garbled_count = count_in_corpus(term)

        # Try O->C single swaps
        best = None
        for i, ch in enumerate(term):
            if ch != "O":
                continue
            corrected = term[:i] + "C" + term[i + 1:]
            if corrected == term:
                continue

            # Check if corrected form exists as verified_main -> duplicate
            if corrected in all_overlay_terms:
                target_entries = overlay_by_term.get(corrected, [])
                for te in target_entries:
                    if te["entry_type"] == "verified_main":
                        duplicates.append({
                            "term": term,
                            "corrected": corrected,
                            "target_type": "verified_main",
                            "target_id": te["id"],
                            "swap": f"pos {i}: O->C",
                        })
                        break
                continue  # skip — either duplicate or already exists

            c_count = count_in_corpus(corrected)
            in_body = in_own_body(term, corrected)

            # Accept if corrected is more common, or found in own body
            if c_count > garbled_count or (in_body and c_count >= 1 and len(corrected) >= 6):
                if best is None or c_count > best[1]:
                    best = (corrected, c_count, f"pos {i}: O->C", in_body)

        # Try double O->C swaps
        o_positions = [i for i, ch in enumerate(term) if ch == "O"]
        if len(o_positions) >= 2:
            for a in range(len(o_positions)):
                for b in range(a + 1, len(o_positions)):
                    chars = list(term)
                    chars[o_positions[a]] = "C"
                    chars[o_positions[b]] = "C"
                    corrected = "".join(chars)
                    if corrected in all_overlay_terms:
                        target_entries = overlay_by_term.get(corrected, [])
                        for te in target_entries:
                            if te["entry_type"] == "verified_main":
                                duplicates.append({
                                    "term": term,
                                    "corrected": corrected,
                                    "target_type": "verified_main",
                                    "target_id": te["id"],
                                    "swap": f"pos {o_positions[a]},{o_positions[b]}: O->C",
                                })
                                break
                        continue

                    c_count = count_in_corpus(corrected)
                    in_body = in_own_body(term, corrected)
                    if c_count > garbled_count or (in_body and c_count >= 1 and len(corrected) >= 6):
                        if best is None or c_count > best[1]:
                            best = (corrected, c_count, f"pos {o_positions[a]},{o_positions[b]}: O->C", in_body)

        if best:
            corrected, c_count, swap, in_body = best
            # Final safety: skip if garbled form is used definitionally elsewhere
            # (more than just in its own entry)
            if garbled_count > 2 and c_count <= garbled_count:
                continue  # garbled form appears too often — might be real
            corrections.append({
                "term": term,
                "corrected": corrected,
                "garbled_count": garbled_count,
                "corrected_count": c_count,
                "in_own_body": in_body,
                "swap": swap,
                "id": entry["id"],
            })

    # Remove any corrections that are already done (headword_corrected)
    already_corrected = {e["original_term"] for e in overlay if e.get("original_term")}
    corrections = [c for c in corrections if c["term"] not in already_corrected]
    duplicates = [d for d in duplicates if d["term"] not in already_corrected]

    # Also remove already-suppressed phantoms
    already_phantom = {e["term"] for e in overlay if e["entry_type"] == "alias_phantom"}
    corrections = [c for c in corrections if c["term"] not in already_phantom]
    duplicates = [d for d in duplicates if d["term"] not in already_phantom]

    # Write report
    report = {
        "corrections": sorted(corrections, key=lambda x: x["term"]),
        "duplicates": sorted(duplicates, key=lambda x: x["term"]),
        "summary": {
            "candidates_scanned": len(candidates),
            "corrections_proposed": len(corrections),
            "duplicates_found": len(duplicates),
        },
    }

    report_path = REPO / "rebuild" / "reports" / "phase3_ocr_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Candidates scanned: {len(candidates)}")
    print(f"Corrections proposed: {len(corrections)}")
    print(f"Duplicates found: {len(duplicates)}")
    print()

    print("=== PROPOSED CORRECTIONS ===")
    for c in report["corrections"]:
        flag = " [in body]" if c["in_own_body"] else ""
        print(f"  {c['term']} -> {c['corrected']} (g={c['garbled_count']}, c={c['corrected_count']}{flag}) [{c['swap']}]")

    print()
    print("=== DUPLICATES (target exists as verified_main) ===")
    for d in report["duplicates"]:
        print(f"  {d['term']} -> {d['corrected']} ({d['target_type']}, {d['target_id']}) [{d['swap']}]")

    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
