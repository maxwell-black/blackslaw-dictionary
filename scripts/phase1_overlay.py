#!/usr/bin/env python3
"""
phase1_overlay.py — Complete Phase 1 editorial overlay for blackslaw corpus.

Reads rebuilt entries, source candidates, and classification reports.
Assigns immutable IDs and entry_type to every entry based on:
  - Manual classifications from body-similarity analysis (37 entries)
  - Source candidate alignment status
  - OCR duplicate detection with body comparison
  - Fragment artifact detection
  - Abbreviation pattern detection
  - Junk headword detection

Writes to rebuild/overlay/ — never touches live files.
"""

import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

# ============================================================
# Path setup
# ============================================================
SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent if (SCRIPT_DIR.parent / "blacks_entries.json").exists() else Path.cwd()

REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
CLASSIFICATION_PATH = REPO / "rebuild" / "reports" / "unmatched_classification.json"
SOURCE_CANDIDATES_PATH = REPO / "rebuild" / "out" / "source_candidates.jsonl"
LEGACY_PATH = REPO / "blacks_entries.json"
OVERLAY_DIR = REPO / "rebuild" / "overlay"

# ============================================================
# Manual classifications from body-similarity analysis
# ============================================================

PHANTOM_SUPPRESS: dict[str, str] = {
    "ABSTRAOT": "ABSTRACT",
    "AQUZ HAUSTUS": "AQUA HAUSTUS",
    "DETRAOCTION": "DETRACTION",
    "EXOESSIVE": "EXCESSIVE",
    "FAOCIO": "FACIO",
    "HALLAZCO": "HALLAZGO",
    "BISHOPRIO": "BISHOPRIC",
    "DIPTYOHA": "DIPTYCHA",
    "OFFIOIAL": "OFFICIAL",
    "PERINDEK": "PERINDE",
    "PROPATRAUS": "PROPATRUUS",
    "RETRAOT": "RETRAIT",
    "UNCEASETH": "UNCEASESATH",
    "VENDITZ": "VENDITIO",
}

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

REVERSED_POLARITY: dict[str, str] = {
    "INFIGHT": "INFIHT",
    "SUZERAIN": "SUZEREIGN",
    "ADVISARE": "ADVISE",
}

SUBENTRY_OF: dict[str, str] = {
    "STARR": "STARE",
    "HERNESIUM": "HERNESCUS",
    "EMBASSAGE": "EMBASSADOR",
    "WINDING-UP": "WINDING",
    "PRETENSED": "PRETENSE",
}

KEEP_STANDALONE: set[str] = {"PAGE", "OXFORD", "THESAURUS"}

# ============================================================
# Detection patterns
# ============================================================

ABBREV_RE = re.compile(
    r"^(?:[A-Z]\.){1,6}(?:\s*[&]\s*(?:[A-Z]\.){1,4})?$"
    r"|^[A-Z]\.\s*[A-Z]\.$"
    r"|^[A-Z]\.[A-Z&]\."
    r"|^[A-Z]\.[&)\(\]]"
)

# Single-letter dot patterns: A.B, A.C, B.D, etc.
SINGLE_DOT_ABBREV_RE = re.compile(r"^[A-Z]\.[A-Z]$")

ROMAN_RE = re.compile(r"^[IVXLCDM]+\.?$")
DIGIT_RE = re.compile(r"^\d+\.?$")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.upper().strip().rstrip(".,;:")
    t = re.sub(r"\s+", " ", t)
    return t


def body_ratio(a: str, b: str, limit: int = 2000) -> float:
    a = (a or "").strip()[:limit].lower()
    b = (b or "").strip()[:limit].lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def is_abbreviation_entry(term: str) -> bool:
    t = term.strip()
    if ABBREV_RE.match(t):
        return True
    if SINGLE_DOT_ABBREV_RE.match(t):
        return True
    return False


def is_junk_headword(term: str) -> bool:
    t = term.strip().rstrip(".,;:")
    if DIGIT_RE.match(t):
        return True
    if ROMAN_RE.match(t) and len(t) <= 6:
        return True
    if len(t) < 2:
        return True
    return False


def is_fragment_term(term: str) -> bool:
    """Detect column/page-break suffix fragments."""
    t = term.strip()
    if len(t) <= 4 and re.fullmatch(r"[A-Z]+", t):
        return True
    if len(t) <= 5 and not re.match(r"^[AEIOU]", t.upper()) and re.fullmatch(r"[A-Za-z]+", t):
        return True
    return False


def body_starts_with_headword(term: str, body: str) -> bool:
    if not body:
        return False
    tn = term.upper().rstrip(".,;:")
    return body[:len(tn) + 20].upper().startswith(tn)


def main() -> int:
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Load all data
    # ============================================================
    with REBUILT_PATH.open("r", encoding="utf-8") as fh:
        rebuilt: list[dict] = json.load(fh)
    print(f"Loaded {len(rebuilt)} rebuilt entries")

    with LEGACY_PATH.open("r", encoding="utf-8") as fh:
        legacy: list[dict] = json.load(fh)
    legacy_by_term: dict[str, dict] = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)
    print(f"Loaded {len(legacy)} legacy entries")

    classification: dict = {}
    if CLASSIFICATION_PATH.exists():
        with CLASSIFICATION_PATH.open("r", encoding="utf-8") as fh:
            classification = json.load(fh)

    source_candidates: list[dict] = []
    if SOURCE_CANDIDATES_PATH.exists():
        with SOURCE_CANDIDATES_PATH.open("r", encoding="utf-8") as fh:
            source_candidates = [json.loads(line) for line in fh if line.strip()]
    print(f"Loaded {len(source_candidates)} source candidates")

    # Build lookups
    src_by_norm: dict[str, list[dict]] = {}
    for c in source_candidates:
        n = norm(c["source_headword"])
        src_by_norm.setdefault(n, []).append(c)

    ocr_dupes_map = {d["term"]: d for d in classification.get("ocr_duplicates", [])}
    prefix_map = {d["term"]: d for d in classification.get("prefix_of_matched", [])}

    # Build matched entry lookup (source-backed entries)
    matched_by_norm: dict[str, str] = {}  # norm -> term
    matched_bodies: dict[str, str] = {}   # term -> rebuilt body
    for i, entry in enumerate(rebuilt):
        if entry.get("source_headword") is not None:
            matched_by_norm[norm(entry["term"])] = entry["term"]
            matched_bodies[entry["term"]] = entry.get("body", "")

    # ============================================================
    # Classify every entry
    # ============================================================
    overlay: list[dict] = []
    actions: list[dict] = []
    type_counts: Counter = Counter()

    for idx, entry in enumerate(rebuilt):
        entry_id = f"BLD2-{idx:05d}"
        term = entry["term"]
        has_source = entry.get("source_headword") is not None
        confidence = entry.get("confidence", 0.0)
        body = entry.get("body", "")
        legacy_body = legacy_by_term.get(term, {}).get("body", "")

        # Default type based on source alignment
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

        # ---- Priority 1: Manual classifications (37 entries) ----
        if term in PHANTOM_SUPPRESS:
            entry_type = "alias_phantom"
            canonical_target = PHANTOM_SUPPRESS[term]
            action_reason = "manual: body-similar OCR garble"
        elif term in ALIAS_VARIANT:
            entry_type = "alias_variant"
            canonical_target = ALIAS_VARIANT[term]
            action_reason = "manual: legitimate spelling/form variant"
        elif term in REVERSED_POLARITY:
            entry_type = "reversed_polarity"
            canonical_target = REVERSED_POLARITY[term]
            action_reason = "manual: unmatched term is correct headword"
        elif term in SUBENTRY_OF:
            entry_type = "subentry"
            canonical_target = SUBENTRY_OF[term]
            action_reason = f"manual: body embedded in parent '{SUBENTRY_OF[term]}'"
        elif term in KEEP_STANDALONE:
            if entry_type == "unmatched":
                entry_type = "unmatched_keep"
                action_reason = "manual: distinct real term"

        # ---- Priority 2: Only reclassify remaining unmatched entries ----
        if entry_type == "unmatched":
            tn = norm(term)
            in_source = tn in src_by_norm

            # 2a: Abbreviation detection
            if is_abbreviation_entry(term):
                entry_type = "appendix_abbrev"
                action_reason = f"abbreviation pattern: '{term}'"

            # 2b: Junk headword detection
            elif is_junk_headword(term):
                entry_type = "junk_headword"
                action_reason = f"junk headword: '{term}'"

            # 2c: In-source but unaligned
            elif in_source:
                src = src_by_norm[tn][0]
                src_body = (src.get("body") or "").strip()

                if not src_body:
                    # Empty source candidate
                    entry_type = "fragment_artifact"
                    action_reason = "in source but empty body"
                elif is_fragment_term(term) and len(term) < 6 and not body_starts_with_headword(term, src_body):
                    entry_type = "fragment_artifact"
                    action_reason = f"fragment: short term '{term}', body doesn't start with headword"
                else:
                    r = body_ratio(legacy_body, src_body)
                    if r >= 0.7 or body_starts_with_headword(term, src_body) or len(term) >= 6:
                        entry_type = "recovered_main"
                        action_reason = f"in source, recoverable (body_ratio={r:.3f})"
                    else:
                        entry_type = "fragment_artifact"
                        action_reason = f"in source but looks like fragment (body_ratio={r:.3f})"

            # 2d: Not in source — OCR duplicate check
            elif term in ocr_dupes_map:
                closest = ocr_dupes_map[term].get("closest_matched", "")

                # Check body similarity against closest matched entry
                # Use legacy-to-legacy comparison
                closest_legacy_body = legacy_by_term.get(closest, {}).get("body", "")
                closest_rebuilt_body = matched_bodies.get(closest, "")

                ll_ratio = body_ratio(legacy_body, closest_legacy_body)
                lr_ratio = body_ratio(legacy_body, closest_rebuilt_body)
                best_ratio = max(ll_ratio, lr_ratio)

                if best_ratio >= 0.5:
                    # True phantom — body matches
                    entry_type = "legacy_duplicate"
                    canonical_target = closest
                    action_reason = f"OCR dupe, body similar to '{closest}' (ratio={best_ratio:.3f})"
                elif body_starts_with_headword(term, legacy_body):
                    # Has a real body but no source evidence
                    if is_fragment_term(term) and len(legacy_body) < 50:
                        entry_type = "fragment_artifact"
                        action_reason = f"short fragment, no source evidence"
                    else:
                        entry_type = "legacy_unresolved"
                        action_reason = f"OCR dupe of '{closest}' by headword but body differs (ratio={best_ratio:.3f})"
                else:
                    # Body doesn't start with headword — fragment
                    entry_type = "fragment_artifact"
                    action_reason = f"body doesn't start with headword, no source"

            # 2e: Prefix of matched entry
            elif term in prefix_map:
                entry_type = "legacy_unresolved"
                action_reason = f"prefix of matched entry '{prefix_map[term].get('closest_matched', '')}'"

            # 2f: Everything else
            else:
                if body_starts_with_headword(term, legacy_body) and len(legacy_body) >= 30:
                    entry_type = "legacy_unresolved"
                    action_reason = "no source, no classification, but has coherent legacy body"
                elif is_fragment_term(term):
                    entry_type = "fragment_artifact"
                    action_reason = "short unclassified term, likely fragment"
                else:
                    entry_type = "legacy_unresolved"
                    action_reason = "unclassified, preserved for future recovery"

        # ---- ZYTHUM bleed flag ----
        source_pages = entry.get("source_pages", [])
        pages_int = []
        for p in source_pages:
            try:
                pages_int.append(int(p))
            except (ValueError, TypeError):
                pass
        flags = list(entry.get("flags", []))
        if pages_int and max(pages_int) > 1192:
            if "zythum_bleed" not in flags:
                flags.append("zythum_bleed")

        type_counts[entry_type] += 1

        record = {
            "id": entry_id,
            "index": idx,
            "term": term,
            "entry_type": entry_type,
            "confidence": confidence,
            "source_headword": entry.get("source_headword"),
            "source_pages": source_pages,
            "flags": flags,
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
                "reason": action_reason,
            })

    # ============================================================
    # Build ID map
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

    # Compute stats
    live_types = {"verified_main", "provisional_main", "recovered_main",
                  "low_confidence_main", "alias_variant", "reversed_polarity",
                  "unmatched_keep", "subentry"}
    excluded_types = {"alias_phantom", "legacy_duplicate", "fragment_artifact",
                      "junk_headword", "appendix_abbrev"}
    deferred_types = {"legacy_unresolved"}

    live_count = sum(1 for o in overlay if o["entry_type"] in live_types)
    excluded_count = sum(1 for o in overlay if o["entry_type"] in excluded_types)
    deferred_count = sum(1 for o in overlay if o["entry_type"] in deferred_types)

    stats = {
        "total_entries": len(rebuilt),
        "live_count": live_count,
        "excluded_count": excluded_count,
        "deferred_count": deferred_count,
        "types": dict(type_counts.most_common()),
        "phase1_actions_taken": len(actions),
    }
    write_json(OVERLAY_DIR / "overlay_stats.json", stats)

    # ============================================================
    # Print summary
    # ============================================================
    print(f"\n{'='*60}")
    print(f"PHASE 1 OVERLAY COMPLETE")
    print(f"{'='*60}")
    print(f"\nTotal entries: {len(rebuilt)}")
    print(f"\n--- LIVE BUILD (included in blacks_entries.json) ---")
    for t in ["verified_main", "provisional_main", "recovered_main",
              "low_confidence_main", "alias_variant", "reversed_polarity",
              "unmatched_keep", "subentry"]:
        if type_counts[t]:
            print(f"  {t:25s} {type_counts[t]:>6,}")
    print(f"  {'TOTAL LIVE':25s} {live_count:>6,}")

    print(f"\n--- EXCLUDED (suppressed from live build) ---")
    for t in ["alias_phantom", "legacy_duplicate", "fragment_artifact",
              "junk_headword", "appendix_abbrev"]:
        if type_counts[t]:
            print(f"  {t:25s} {type_counts[t]:>6,}")
    print(f"  {'TOTAL EXCLUDED':25s} {excluded_count:>6,}")

    print(f"\n--- DEFERRED (legacy body preserved, not in live build) ---")
    for t in ["legacy_unresolved"]:
        if type_counts[t]:
            print(f"  {t:25s} {type_counts[t]:>6,}")
    print(f"  {'TOTAL DEFERRED':25s} {deferred_count:>6,}")

    print(f"\nPhase 1 actions taken: {len(actions)}")
    print(f"\nOutput: {OVERLAY_DIR}/")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
