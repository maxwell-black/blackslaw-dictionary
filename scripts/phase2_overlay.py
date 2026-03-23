#!/usr/bin/env python3
"""
phase2_overlay.py — OCR headword correction + reclassification pass.

Reads the Phase 1 overlay and applies:
  1. OCR headword corrections for legacy_unresolved entries where the
     corrected form does NOT already exist as a live entry.
  2. Reclassifies legacy_unresolved entries whose corrected headword
     DOES already exist as legacy_duplicate (suppress).
  3. Detects garbled rebuilt bodies and flags them for legacy fallback.

Writes an updated overlay to rebuild/overlay/editorial_overlay.json
(overwrites Phase 1 output — Phase 1 is recoverable from git/backups).
Also writes rebuild/overlay/phase2_actions.json.

Does NOT touch live files.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from itertools import product
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent if (SCRIPT_DIR.parent / "blacks_entries.json").exists() else Path.cwd()

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
LEGACY_PATH = REPO / "blacks_entries.json"
CLASSIFICATION_PATH = REPO / "rebuild" / "reports" / "unmatched_classification.json"
OVERLAY_DIR = REPO / "rebuild" / "overlay"

# ============================================================
# Known OCR confusion pairs (bidirectional)
# ============================================================
OCR_PAIRS = [
    ("C", "O"),
    ("O", "C"),
    ("C", "G"),
    ("G", "C"),
    ("I", "L"),
    ("L", "I"),
    ("U", "V"),
    ("V", "U"),
    ("M", "N"),
    ("N", "M"),
    ("E", "F"),
    ("F", "E"),
    ("T", "I"),
    ("I", "T"),
    ("H", "N"),
    ("N", "H"),
    ("R", "K"),
    ("K", "R"),
    ("Z", "S"),
    ("S", "Z"),
    ("D", "O"),
    ("O", "D"),
    ("B", "D"),
    ("D", "B"),
    ("P", "R"),
    ("R", "P"),
]

# Multi-char substitutions
OCR_MULTI = [
    ("OO", "CC"),
    ("CC", "OO"),
    ("OC", "CC"),
    ("AO", "AC"),
    ("IO", "IC"),
    ("OI", "CI"),
    ("EO", "EC"),
    ("OE", "CE"),
    ("TZ", "TIO"),
    ("OT", "CT"),
    ("LL", "L"),
    ("OOH", "CCH"),
    ("OH", "CH"),
]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.upper().strip().rstrip(".,;:")
    t = re.sub(r"\s+", " ", t)
    return t


def generate_corrections(term: str) -> list[str]:
    """Generate candidate corrections by applying OCR confusion pairs."""
    upper = term.upper()
    candidates: set[str] = set()

    # Single-char substitutions
    for i, ch in enumerate(upper):
        for old, new in OCR_PAIRS:
            if ch == old:
                fixed = upper[:i] + new + upper[i + 1:]
                if fixed != upper:
                    candidates.add(fixed)

    # Multi-char substitutions
    for old, new in OCR_MULTI:
        if old in upper:
            fixed = upper.replace(old, new, 1)
            if fixed != upper:
                candidates.add(fixed)

    # Double substitutions (apply two single-char fixes)
    for i, ch_i in enumerate(upper):
        for old_i, new_i in OCR_PAIRS:
            if ch_i != old_i:
                continue
            partial = upper[:i] + new_i + upper[i + 1:]
            for j, ch_j in enumerate(partial):
                if j == i:
                    continue
                for old_j, new_j in OCR_PAIRS:
                    if ch_j != old_j:
                        continue
                    fixed = partial[:j] + new_j + partial[j + 1:]
                    if fixed != upper:
                        candidates.add(fixed)

    return sorted(candidates)


def body_starts_with_headword(term: str, body: str) -> bool:
    if not body:
        return False
    tn = term.upper().rstrip(".,;:")
    return body[:len(tn) + 20].upper().startswith(tn)


def rebuilt_body_looks_garbled(term: str, body: str) -> bool:
    """Detect rebuilt bodies that are obviously broken."""
    if not body or len(body.strip()) < 10:
        return True
    b = body.strip()
    # Starts with isolated short fragment
    if re.match(r"^[a-z]{1,3}\.\s*\n", b):
        return True
    if re.match(r"^[a-z]{1,3}\.\s+from\.", b):
        return True
    # Starts with punctuation
    if b[0] in {",", ".", ";"}:
        return True
    # Starts with "v.\n" or "n.\n" followed by garbage
    if re.match(r"^[a-z]{1,2}\.\s*\n\s*from\.", b):
        return True
    # Body is just a sense marker with no content
    if re.match(r"^[a-z]{1,3}\.\s*\n\s*[.,;]", b):
        return True
    return False


def main() -> int:
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

    # Load everything
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

    classification: dict = {}
    if CLASSIFICATION_PATH.exists():
        with CLASSIFICATION_PATH.open("r", encoding="utf-8") as fh:
            classification = json.load(fh)

    # Build lookup: which normalized terms already exist as live entries?
    live_norms: dict[str, str] = {}  # norm -> original term
    for o in overlay:
        if o["entry_type"] in ("verified_main", "provisional_main",
                                "recovered_main", "low_confidence_main"):
            live_norms[norm(o["term"])] = o["term"]

    # Also track all terms in overlay for duplicate detection
    all_terms_norm: dict[str, list[int]] = {}
    for idx, o in enumerate(overlay):
        all_terms_norm.setdefault(norm(o["term"]), []).append(idx)

    # ============================================================
    # Pass 1: OCR headword correction for legacy_unresolved entries
    # ============================================================
    actions: list[dict] = []
    corrections_applied = 0
    duplicates_found = 0
    garbled_flagged = 0

    for idx, o in enumerate(overlay):
        if o["entry_type"] != "legacy_unresolved":
            continue

        term = o["term"]
        tn = norm(term)
        legacy_body = (legacy_by_term.get(term, {}).get("body") or "").strip()

        # Try OCR corrections
        corrections = generate_corrections(tn)

        best_correction = None
        best_target = None

        for candidate in corrections:
            if candidate in live_norms:
                # Corrected form already exists — this is a duplicate
                best_target = live_norms[candidate]
                break

        if best_target:
            # Check body similarity to confirm it's a real duplicate
            target_body = (legacy_by_term.get(best_target, {}).get("body") or "").strip()
            ratio = 0.0
            if legacy_body and target_body:
                ratio = SequenceMatcher(
                    None, legacy_body[:2000].lower(), target_body[:2000].lower()
                ).ratio()

            if ratio >= 0.4:
                # Confirmed duplicate
                o["entry_type"] = "legacy_duplicate"
                o["canonical_target"] = best_target
                duplicates_found += 1
                actions.append({
                    "id": o["id"],
                    "term": term,
                    "entry_type": "legacy_duplicate",
                    "canonical_target": best_target,
                    "reason": f"OCR correction {tn}->{norm(best_target)}, body ratio={ratio:.3f}",
                })
            else:
                # Headword is garbled but body is different — might be a
                # different sense or subentry. Keep as unresolved but note it.
                # Don't auto-suppress.
                pass
        else:
            # Corrected form doesn't exist anywhere — this entry is unique.
            # Fix the headword if we can find a plausible correction.
            for candidate in corrections:
                # Check if the legacy body starts with something close to the candidate
                if legacy_body:
                    body_start = legacy_body[:50].upper()
                    # The body often starts with the garbled headword too,
                    # so check if the correction makes sense
                    if candidate.replace(" ", "") in body_start.replace(" ", ""):
                        best_correction = candidate
                        break

            # Also try: does body contain the correction as a word?
            if not best_correction and legacy_body:
                for candidate in corrections:
                    if len(candidate) >= 5 and candidate in legacy_body.upper():
                        best_correction = candidate
                        break

            if best_correction:
                # Apply headword fix
                old_term = o["term"]
                o["term"] = best_correction
                o["original_term"] = old_term
                o["entry_type"] = "headword_corrected"
                corrections_applied += 1
                actions.append({
                    "id": o["id"],
                    "term": best_correction,
                    "original_term": old_term,
                    "entry_type": "headword_corrected",
                    "reason": f"OCR correction: {old_term} -> {best_correction}",
                })

    # ============================================================
    # Pass 2: Flag garbled rebuilt bodies for legacy fallback
    # ============================================================
    for idx, o in enumerate(overlay):
        if o["entry_type"] not in ("verified_main", "provisional_main",
                                    "recovered_main", "low_confidence_main"):
            continue

        rebuilt_body = (rebuilt[idx].get("body") or "").strip()
        if rebuilt_body_looks_garbled(o["term"], rebuilt_body):
            if "garbled_rebuilt_body" not in o.get("flags", []):
                o.setdefault("flags", []).append("garbled_rebuilt_body")
                garbled_flagged += 1
                actions.append({
                    "id": o["id"],
                    "term": o["term"],
                    "entry_type": o["entry_type"],
                    "reason": "rebuilt body garbled, will fall back to legacy",
                })

    # ============================================================
    # Recompute stats
    # ============================================================
    type_counts: Counter = Counter()
    for o in overlay:
        type_counts[o["entry_type"]] += 1

    live_types = {"verified_main", "provisional_main", "recovered_main",
                  "low_confidence_main", "alias_variant", "reversed_polarity",
                  "unmatched_keep", "subentry", "headword_corrected"}
    promotable_types = {"legacy_unresolved"}
    excluded_types = {"alias_phantom", "legacy_duplicate", "fragment_artifact",
                      "junk_headword", "appendix_abbrev"}

    # ============================================================
    # Write outputs
    # ============================================================
    with (OVERLAY_DIR / "editorial_overlay.json").open("w", encoding="utf-8") as fh:
        json.dump(overlay, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    with (OVERLAY_DIR / "phase2_actions.json").open("w", encoding="utf-8") as fh:
        json.dump(actions, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    stats = {
        "total_entries": len(overlay),
        "types": dict(type_counts.most_common()),
        "phase2_corrections_applied": corrections_applied,
        "phase2_duplicates_found": duplicates_found,
        "phase2_garbled_bodies_flagged": garbled_flagged,
    }
    with (OVERLAY_DIR / "overlay_stats.json").open("w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*60}")
    print(f"PHASE 2 OVERLAY COMPLETE")
    print(f"{'='*60}")
    print(f"\nTotal entries: {len(overlay)}")
    print(f"\nPhase 2 changes:")
    print(f"  Headword corrections applied: {corrections_applied}")
    print(f"  Duplicates found (suppress):  {duplicates_found}")
    print(f"  Garbled bodies flagged:        {garbled_flagged}")

    print(f"\nEntry types after Phase 2:")
    for t, c in type_counts.most_common():
        print(f"  {t:25s} {c:>6,}")

    print(f"\nOutput: {OVERLAY_DIR}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
