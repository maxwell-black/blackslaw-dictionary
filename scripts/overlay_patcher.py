#!/usr/bin/env python3
"""
overlay_patcher.py — Phase 1 editorial overlay for blackslaw corpus.

Adds immutable IDs and entry_type classifications to every entry.
Handles:
  - 10 confirmed OCR phantoms (auto-suppress)
  - 15 legitimate variant/alias entries (alias_variant)
  - 3 reversed-polarity headword swaps
  - 5 subentry relationships
  - 4 keep-as-standalone overrides
  - 107 abbreviation-pattern entries (appendix_abbrev)
  - ZYTHUM bleed flag (leaf > 1249)
  - Junk source candidate markers (digits, Roman numerals, <2 char)

Writes:
  rebuild/overlay/editorial_overlay.json   — full overlay keyed by ID
  rebuild/overlay/id_map.json              — term -> ID mapping
  rebuild/overlay/overlay_stats.json       — summary counts by type
  rebuild/overlay/phase1_actions.json      — log of every non-default action taken

Does NOT mutate blacks_entries.json or any live file.
"""
from __future__ import annotations

import json
import re
import hashlib
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
# If run from scripts/, ROOT is the repo root's parent — adjust
if (ROOT / "blacks_entries.json").exists():
    REPO = ROOT
elif (ROOT.parent / "blacks_entries.json").exists():
    REPO = ROOT.parent
else:
    REPO = Path.cwd()

REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
CLASSIFICATION_PATH = REPO / "rebuild" / "reports" / "unmatched_classification.json"
OVERLAY_DIR = REPO / "rebuild" / "overlay"

# ============================================================
# Manual classifications from body-similarity analysis (37 entries)
# ============================================================

# OCR phantoms: garbled headword, near-identical body, no independent meaning.
# Action: suppress from live build, redirect searches to canonical term.
PHANTOM_SUPPRESS: dict[str, str] = {
    "AQUZ HAUSTUS": "AQUA HAUSTUS",
    "DETRAOCTION": "DETRACTION",
    "EXOESSIVE": "EXCESSIVE",
    "FAOCIO": "FACIO",
    "HALLAZCO": "HALLAZGO",
    "PERINDEK": "PERINDE",
    "PROPATRAUS": "PROPATRUUS",
    "RETRAOT": "RETRAIT",
    "UNCEASETH": "UNCEASESATH",
    "VENDITZ": "VENDITIO",
}

# Legitimate variant spellings/forms. Keep as alias redirects.
# User searching either form should find the entry.
ALIAS_VARIANT: dict[str, str] = {
    "CARPE MEALS": "CARPEMEALS",
    "CENIGILD": "CENEGILD",
    "CO-HEIR": "COHEIR",
    "FALERAE": "FALERE",
    "FLOOD-MARK": "FLODE-MARK",
    "HERETARE": "HAERETARE",
    "JUMPNUM": "JAMPNUM",
    "LAHSLIT": "LAHLSLIT",
    "MARSHALL": "MARSHAL",
    "MARITAGIO": "MARITAGIUM",
    "PARATITULA": "PARATITLA",
    "PORTATIVE": "PORTATICA",
    "SACRIER": "SACQUIER",
    "TWELFHYNDI": "TWELFHINDI",
    "FONSADA": "FONSADERA",
}

# Reversed polarity: the "unmatched" entry has the better/correct headword.
# The matched entry's headword is the garbled one.
# Action: swap canonical direction. The unmatched term becomes the display headword.
REVERSED_POLARITY: dict[str, str] = {
    "INFIGHT": "INFIHT",
    "SUZERAIN": "SUZEREIGN",
    "ADVISARE": "ADVISE",
}

# Subentries: body shared because one entry lives inside the other's text.
# Action: mark as subentry, link to parent. Keep searchable.
SUBENTRY_OF: dict[str, str] = {
    "STARR": "STARE",
    "HERNESIUM": "HERNESCUS",
    "EMBASSAGE": "EMBASSADOR",
    "WINDING-UP": "WINDING",
    "PRETENSED": "PRETENSE",
}

# Keep as standalone despite body similarity — distinct real terms.
KEEP_STANDALONE: set[str] = {"PAGE", "OXFORD", "THESAURUS"}

# ============================================================
# Detection patterns
# ============================================================

# Abbreviation entries: A.B., I.C., O.R., etc.
# Dotted uppercase patterns typical of the appendix table.
ABBREV_RE = re.compile(
    r"^(?:[A-Z]\.){1,6}(?:\s*&\s*(?:[A-Z]\.){1,4})?$"
    r"|^[A-Z]\.\s*[A-Z]\.$"
    r"|^[A-Z]\.[A-Z&]\."
)

# Roman numeral headwords (not in a real dictionary)
ROMAN_RE = re.compile(r"^[IVXLCDM]+\.?$")

# Pure digit headwords
DIGIT_RE = re.compile(r"^\d+\.?$")


def make_id(index: int, term: str) -> str:
    """Stable immutable ID: BLD2-{5-digit index}."""
    return f"BLD2-{index:05d}"


def is_abbreviation_entry(term: str, body: str) -> bool:
    """Detect appendix abbreviation entries by headword pattern."""
    term_clean = term.strip()
    if ABBREV_RE.match(term_clean):
        return True
    # Also catch entries like "C.&" "C.)" etc.
    if re.match(r"^[A-Z]\.[&)\(\]]", term_clean):
        return True
    return False


def is_junk_headword(term: str) -> bool:
    """Detect junk source candidates: digits, Roman numerals, <2 chars."""
    term_clean = term.strip().rstrip(".,;:")
    if DIGIT_RE.match(term_clean):
        return True
    if ROMAN_RE.match(term_clean) and len(term_clean) <= 6:
        return True
    if len(term_clean) < 2:
        return True
    return False


def main() -> int:
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

    # Load rebuilt entries
    with REBUILT_PATH.open("r", encoding="utf-8") as fh:
        rebuilt: list[dict] = json.load(fh)

    print(f"Loaded {len(rebuilt)} rebuilt entries from {REBUILT_PATH}")

    # Load classification report if available
    classification: dict = {}
    if CLASSIFICATION_PATH.exists():
        with CLASSIFICATION_PATH.open("r", encoding="utf-8") as fh:
            classification = json.load(fh)
        print(f"Loaded classification from {CLASSIFICATION_PATH}")

    # Build term -> index lookup
    term_to_indices: dict[str, list[int]] = {}
    for idx, entry in enumerate(rebuilt):
        term_to_indices.setdefault(entry["term"], []).append(idx)

    # ============================================================
    # Assign IDs and default types
    # ============================================================
    overlay: list[dict] = []
    actions: list[dict] = []
    type_counts: Counter = Counter()

    for idx, entry in enumerate(rebuilt):
        entry_id = make_id(idx, entry["term"])
        term = entry["term"]
        has_source = entry.get("source_headword") is not None
        confidence = entry.get("confidence", 0.0)

        # Default type
        if has_source and confidence >= 0.90:
            entry_type = "verified_main"
        elif has_source and confidence >= 0.70:
            entry_type = "provisional_main"
        elif has_source:
            entry_type = "low_confidence_main"
        else:
            entry_type = "unmatched"

        canonical_target = None
        action_reason = None

        # ---- Manual classifications from the 37 ----

        if term in PHANTOM_SUPPRESS:
            entry_type = "alias_phantom"
            canonical_target = PHANTOM_SUPPRESS[term]
            action_reason = "body-similar OCR garble; suppress and redirect"

        elif term in ALIAS_VARIANT:
            entry_type = "alias_variant"
            canonical_target = ALIAS_VARIANT[term]
            action_reason = "legitimate spelling/form variant; keep as searchable alias"

        elif term in REVERSED_POLARITY:
            entry_type = "reversed_polarity"
            canonical_target = REVERSED_POLARITY[term]
            action_reason = (
                f"unmatched '{term}' is the correct headword; "
                f"matched '{REVERSED_POLARITY[term]}' is garbled"
            )

        elif term in SUBENTRY_OF:
            entry_type = "subentry"
            canonical_target = SUBENTRY_OF[term]
            action_reason = f"body embedded within parent entry '{SUBENTRY_OF[term]}'"

        elif term in KEEP_STANDALONE:
            if entry_type == "unmatched":
                entry_type = "unmatched_keep"
                action_reason = "manually classified as distinct real term despite body similarity"

        # ---- Abbreviation detection ----
        if entry_type in ("unmatched", "low_confidence_main") and is_abbreviation_entry(term, entry.get("body", "")):
            entry_type = "appendix_abbrev"
            action_reason = f"abbreviation-pattern headword '{term}'"

        # ---- Junk headword detection (for source candidate quality) ----
        if entry_type == "unmatched" and is_junk_headword(term):
            entry_type = "junk_headword"
            action_reason = f"junk headword pattern: '{term}'"

        # ---- ZYTHUM bleed check ----
        leaves = entry.get("leaves", [])
        if leaves and any(leaf > 1249 for leaf in leaves):
            if "zythum_bleed" not in (entry.get("flags") or []):
                entry.setdefault("flags", []).append("zythum_bleed")
            if entry_type.endswith("_main") or entry_type == "verified_main":
                # Don't retype matched entries, just flag
                pass
            action_reason = (action_reason or "") + "; leaf > 1249 (appendix territory)"

        type_counts[entry_type] += 1

        record = {
            "id": entry_id,
            "index": idx,
            "term": term,
            "entry_type": entry_type,
            "confidence": confidence,
            "source_headword": entry.get("source_headword"),
            "source_pages": entry.get("source_pages", []),
            "flags": entry.get("flags", []),
        }
        if canonical_target:
            record["canonical_target"] = canonical_target
        overlay.append(record)

        if action_reason:
            actions.append({
                "id": entry_id,
                "term": term,
                "entry_type": entry_type,
                "canonical_target": canonical_target,
                "reason": action_reason.strip("; "),
            })

    # ============================================================
    # Build ID map (term -> list of IDs, since terms can repeat)
    # ============================================================
    id_map: dict[str, list[str]] = {}
    for record in overlay:
        id_map.setdefault(record["term"], []).append(record["id"])

    # ============================================================
    # Write outputs
    # ============================================================
    def write_json(path: Path, obj: object) -> None:
        with path.open("w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    write_json(OVERLAY_DIR / "editorial_overlay.json", overlay)
    write_json(OVERLAY_DIR / "id_map.json", id_map)
    write_json(OVERLAY_DIR / "phase1_actions.json", actions)

    stats = {
        "total_entries": len(rebuilt),
        "types": dict(type_counts.most_common()),
        "phase1_actions_taken": len(actions),
        "phantoms_suppressed": sum(1 for a in actions if "alias_phantom" in a.get("entry_type", "")),
        "variants_aliased": sum(1 for a in actions if "alias_variant" in a.get("entry_type", "")),
        "reversed_polarity": sum(1 for a in actions if "reversed_polarity" in a.get("entry_type", "")),
        "subentries_linked": sum(1 for a in actions if "subentry" in a.get("entry_type", "")),
        "abbreviations_tagged": sum(1 for a in actions if "appendix_abbrev" in a.get("entry_type", "")),
        "junk_headwords_tagged": sum(1 for a in actions if "junk_headword" in a.get("entry_type", "")),
    }
    write_json(OVERLAY_DIR / "overlay_stats.json", stats)

    # ============================================================
    # Print summary
    # ============================================================
    print("\n=== OVERLAY STATS ===")
    print(f"Total entries:          {stats['total_entries']}")
    print()
    print("Entry types:")
    for entry_type, count in type_counts.most_common():
        print(f"  {entry_type:25s} {count:>6,}")
    print()
    print(f"Phase 1 actions taken:  {stats['phase1_actions_taken']}")
    print(f"  phantoms suppressed:  {stats['phantoms_suppressed']}")
    print(f"  variants aliased:     {stats['variants_aliased']}")
    print(f"  reversed polarity:    {stats['reversed_polarity']}")
    print(f"  subentries linked:    {stats['subentries_linked']}")
    print(f"  abbreviations tagged: {stats['abbreviations_tagged']}")
    print(f"  junk headwords:       {stats['junk_headwords_tagged']}")
    print()
    print(f"Output: {OVERLAY_DIR}/")
    print("  editorial_overlay.json")
    print("  id_map.json")
    print("  phase1_actions.json")
    print("  overlay_stats.json")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
