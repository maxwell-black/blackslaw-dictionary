#!/usr/bin/env python3
"""
phase2c_overlay.py — Fixed OCR headword correction pass.

CRITICAL FIX from phase2b: Only attempts headword corrections on
entries classified as OCR duplicates in unmatched_classification.json.
All other legacy_unresolved entries keep their headwords as-is.

Reads the Phase 1 overlay and:
  1. For OCR-duplicate legacy_unresolved entries: try OCR substitutions.
     - If corrected form exists as live entry + body similar -> legacy_duplicate
     - If corrected form does NOT exist as live entry -> headword_corrected
  2. For non-OCR-duplicate legacy_unresolved entries: leave as-is (they get
     promoted to legacy_retained by the corpus generator).
  3. Flags garbled rebuilt bodies.

Must run on PHASE 1 overlay (not phase2/2b output). If phase2/2b already
ran, first restore phase 1 overlay:
  cd ~/blackslaw-dictionary && python3 scripts/phase1_overlay.py

Then run this script.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent if (SCRIPT_DIR.parent / "blacks_entries.json").exists() else Path.cwd()

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
LEGACY_PATH = REPO / "blacks_entries.json"
CLASSIFICATION_PATH = REPO / "rebuild" / "reports" / "unmatched_classification.json"
OVERLAY_DIR = REPO / "rebuild" / "overlay"

# OCR substitutions (applied to headword, single-char)
SINGLE_SUBS = [
    ("O", "C"), ("C", "O"),
    ("O", "G"), ("G", "O"),
    ("I", "L"), ("L", "I"),
    ("U", "V"), ("V", "U"),
    ("M", "N"), ("N", "M"),
    ("Z", "S"), ("S", "Z"),
    ("D", "O"), ("O", "D"),
]

MULTI_SUBS = [
    ("OO", "CC"), ("CC", "OO"),
    ("OC", "CC"), ("AO", "AC"),
    ("IO", "IC"), ("OI", "CI"),
    ("EO", "EC"), ("OE", "CE"),
    ("OT", "CT"), ("OH", "CH"),
    ("OOH", "CCH"),
]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.upper().strip().rstrip(".,;:")
    t = re.sub(r"\s+", " ", t)
    return t


def generate_corrections(term_upper: str) -> list[str]:
    """Generate candidate corrections via OCR confusion substitutions."""
    results: set[str] = set()

    # Multi-char first
    for old, new in MULTI_SUBS:
        idx = 0
        while True:
            pos = term_upper.find(old, idx)
            if pos == -1:
                break
            fixed = term_upper[:pos] + new + term_upper[pos + len(old):]
            if fixed != term_upper:
                results.add(fixed)
            idx = pos + 1

    # Single-char
    for i, ch in enumerate(term_upper):
        for old, new in SINGLE_SUBS:
            if ch == old:
                fixed = term_upper[:i] + new + term_upper[i + 1:]
                if fixed != term_upper:
                    results.add(fixed)

    return sorted(results)


def body_ratio(a: str, b: str, limit: int = 2000) -> float:
    a = (a or "").strip()[:limit].lower()
    b = (b or "").strip()[:limit].lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def rebuilt_body_garbled(body: str) -> bool:
    if not body or len(body.strip()) < 10:
        return True
    b = body.strip()
    flat = re.sub(r"\s+", " ", b[:80]).strip()
    if re.match(r"^[a-z]{1,3}\. from\.", flat):
        return True
    if re.match(r"^[a-z]{1,3}\. [.,;]", flat):
        return True
    if re.match(r"^[a-z]{1,3}\.\s*[.,;]", flat):
        return True
    if b[0] in {",", ";"}:
        return True
    if b[0] == "." and len(b) > 1 and b[1] in {" ", "\n"}:
        return True
    return False


def main() -> int:
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

    with OVERLAY_PATH.open("r", encoding="utf-8") as fh:
        overlay: list[dict] = json.load(fh)
    print(f"Loaded {len(overlay)} overlay entries")

    with REBUILT_PATH.open("r", encoding="utf-8") as fh:
        rebuilt: list[dict] = json.load(fh)

    with LEGACY_PATH.open("r", encoding="utf-8") as fh:
        legacy: list[dict] = json.load(fh)
    legacy_by_term: dict[str, dict] = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)

    # Load classification to identify OCR duplicates
    ocr_dupe_terms: set[str] = set()
    if CLASSIFICATION_PATH.exists():
        with CLASSIFICATION_PATH.open("r", encoding="utf-8") as fh:
            classification = json.load(fh)
        for d in classification.get("ocr_duplicates", []):
            ocr_dupe_terms.add(d["term"])
    print(f"OCR duplicate terms from classification: {len(ocr_dupe_terms)}")

    # Live entry lookup
    live_norms: dict[str, str] = {}
    for o in overlay:
        if o["entry_type"] in ("verified_main", "provisional_main",
                                "recovered_main", "low_confidence_main"):
            live_norms[norm(o["term"])] = o["term"]

    corrected_norms: set[str] = set()
    actions: list[dict] = []
    corrections_applied = 0
    duplicates_found = 0
    garbled_flagged = 0
    skipped_not_ocr_dupe = 0

    # ============================================================
    # Pass 1: Headword correction — OCR duplicates ONLY
    # ============================================================
    for idx, o in enumerate(overlay):
        if o["entry_type"] != "legacy_unresolved":
            continue

        term = o["term"]

        # ONLY attempt corrections on entries classified as OCR duplicates
        if term not in ocr_dupe_terms:
            skipped_not_ocr_dupe += 1
            continue

        tn = norm(term)
        legacy_body = (legacy_by_term.get(term, {}).get("body") or "").strip()

        if len(legacy_body) < 20:
            continue

        corrections = generate_corrections(tn)
        if not corrections:
            continue

        # Check: does corrected form exist as a live entry?
        handled = False
        for candidate in corrections:
            if candidate in corrected_norms:
                continue

            if candidate in live_norms:
                target = live_norms[candidate]
                target_body = (legacy_by_term.get(target, {}).get("body") or "").strip()
                ratio = body_ratio(legacy_body, target_body)

                if ratio >= 0.4:
                    o["entry_type"] = "legacy_duplicate"
                    o["canonical_target"] = target
                    duplicates_found += 1
                    actions.append({
                        "id": o["id"],
                        "term": term,
                        "entry_type": "legacy_duplicate",
                        "canonical_target": target,
                        "reason": f"OCR {tn}->{candidate}, body ratio={ratio:.3f}, "
                                  f"target '{target}' is live",
                    })
                    handled = True
                    break

        if handled:
            continue

        # No live entry for corrected form. Apply best correction.
        for candidate in corrections:
            if candidate in live_norms or candidate in corrected_norms:
                continue
            o["original_term"] = term
            o["term"] = candidate
            o["entry_type"] = "headword_corrected"
            corrected_norms.add(candidate)
            corrections_applied += 1
            actions.append({
                "id": o["id"],
                "term": candidate,
                "original_term": term,
                "entry_type": "headword_corrected",
                "reason": f"OCR correction: {term} -> {candidate}",
            })
            break

    # ============================================================
    # Pass 2: Flag garbled rebuilt bodies
    # ============================================================
    for idx, o in enumerate(overlay):
        if o["entry_type"] not in ("verified_main", "provisional_main",
                                    "recovered_main", "low_confidence_main"):
            continue
        rb = (rebuilt[idx].get("body") or "").strip()
        if rebuilt_body_garbled(rb):
            flags = o.get("flags", [])
            if "garbled_rebuilt_body" not in flags:
                flags.append("garbled_rebuilt_body")
                o["flags"] = flags
                garbled_flagged += 1
                actions.append({
                    "id": o["id"],
                    "term": o["term"],
                    "entry_type": o["entry_type"],
                    "reason": f"rebuilt body garbled: {repr(rb[:60])}",
                })

    # ============================================================
    # Write outputs
    # ============================================================
    type_counts: Counter = Counter(o["entry_type"] for o in overlay)

    with (OVERLAY_DIR / "editorial_overlay.json").open("w", encoding="utf-8") as fh:
        json.dump(overlay, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with (OVERLAY_DIR / "phase2c_actions.json").open("w", encoding="utf-8") as fh:
        json.dump(actions, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    stats = {
        "total_entries": len(overlay),
        "types": dict(type_counts.most_common()),
        "corrections_applied": corrections_applied,
        "duplicates_found": duplicates_found,
        "garbled_bodies_flagged": garbled_flagged,
        "skipped_not_ocr_dupe": skipped_not_ocr_dupe,
    }
    with (OVERLAY_DIR / "overlay_stats.json").open("w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"\n{'='*60}")
    print(f"PHASE 2C OVERLAY COMPLETE")
    print(f"{'='*60}")
    print(f"\nPhase 2c changes:")
    print(f"  Headword corrections applied: {corrections_applied}")
    print(f"  Duplicates suppressed:         {duplicates_found}")
    print(f"  Garbled bodies flagged:         {garbled_flagged}")
    print(f"  Skipped (not OCR dupe):         {skipped_not_ocr_dupe}")
    print(f"\nEntry types:")
    for t, c in type_counts.most_common():
        print(f"  {t:25s} {c:>6,}")
    print(f"\nOutput: {OVERLAY_DIR}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
