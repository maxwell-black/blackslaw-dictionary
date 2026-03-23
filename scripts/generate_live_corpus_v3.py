#!/usr/bin/env python3
"""
generate_live_corpus_v3.py — Build the live corpus from the Phase 2 overlay.

Changes from v2:
  - Includes headword_corrected entries (OCR-fixed headwords)
  - Respects garbled_rebuilt_body flag for legacy fallback
  - Better garbled body detection (handles newlines)
  - Promotes legacy_unresolved with substantial bodies to legacy_retained

Writes:
  rebuild/out/blacks_entries.live_candidate.json
  rebuild/out/live_build_report.json
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent if (SCRIPT_DIR.parent / "blacks_entries.json").exists() else Path.cwd()

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
LEGACY_PATH = REPO / "rebuild" / "out" / "blacks_entries.legacy_original.json"
BODY_CORRECTIONS_PATH = REPO / "rebuild" / "overlay" / "body_corrections.json"
OUT_DIR = REPO / "rebuild" / "out"

# Types always in live build
LIVE_TYPES = {
    "verified_main",
    "provisional_main",
    "recovered_main",
    "low_confidence_main",
    "alias_variant",
    "reversed_polarity",
    "unmatched_keep",
    "subentry",
    "headword_corrected",
}

# Types promotable with substantial legacy body
PROMOTABLE_TYPES = {"legacy_unresolved"}

MIN_LEGACY_BODY = 40


def strip_leading_headword(term: str, body: str) -> str:
    if not body:
        return body
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    sense_re = re.compile(
        rf"^\s*{escaped}\s*,\s*((?:v|n|adj|adv|vb|prep|part|pl|pp)\.)\s*",
        re.IGNORECASE,
    )
    m = sense_re.match(body)
    if m:
        return f"{m.group(1)} {body[m.end():].lstrip()}"
    plain_re = re.compile(rf"^\s*{escaped}\s*[.,;:]\s*", re.IGNORECASE)
    if plain_re.match(body):
        return plain_re.sub("", body, count=1).lstrip()
    start_re = re.compile(rf"^\s*{escaped}\s+", re.IGNORECASE)
    sm = start_re.match(body)
    if sm and len(body) > len(term) + 5:
        after = body[sm.end():]
        if after and after[0] in "([":
            return after
    return body


def body_looks_garbled(term: str, body: str) -> bool:
    if not body or len(body.strip()) < 10:
        return True
    b = body.strip()
    # Normalize: collapse leading whitespace/newlines for checking
    b_flat = re.sub(r"\s+", " ", b[:60]).strip()
    # Starts with isolated sense marker then garbage
    if re.match(r"^[a-z]{1,3}\. from\.", b_flat):
        return True
    if re.match(r"^[a-z]{1,3}\. [.,;]", b_flat):
        return True
    # Starts with just "v." or "n." and then a comma or period
    if re.match(r"^[a-z]{1,3}\.\s*[.,;]", b_flat):
        return True
    # Starts with punctuation
    if b[0] in {",", ";"}:
        return True
    if b[0] == "." and len(b) > 1 and b[1] in {" ", "\n"}:
        return True
    return False


def pick_body(
    overlay_rec: dict,
    rebuilt_entry: dict,
    legacy_entry: dict | None,
    original_term: str | None,
    body_corrections: dict | None = None,
) -> tuple[str, str]:
    rebuilt_body = (rebuilt_entry.get("body") or "").strip()
    legacy_body = ((legacy_entry or {}).get("body") or "").strip()
    term = overlay_rec["term"]
    flags = overlay_rec.get("flags", [])

    # Manual body corrections take highest priority
    if body_corrections and term in body_corrections:
        return body_corrections[term]["body"], "manual_correction"

    # If garbled_rebuilt_body flagged, skip rebuilt
    use_rebuilt = True
    if "garbled_rebuilt_body" in flags:
        use_rebuilt = False
    if rebuilt_body and body_looks_garbled(term, rebuilt_body):
        use_rebuilt = False

    has_source = overlay_rec.get("source_headword") is not None

    # Source-backed: prefer rebuilt if not garbled
    if has_source and use_rebuilt and rebuilt_body:
        return rebuilt_body, "rebuilt"

    # For headword_corrected entries, legacy body is under original_term
    if overlay_rec["entry_type"] == "headword_corrected" and original_term:
        orig_legacy = legacy_entry  # already looked up by original_term
        if orig_legacy:
            lb = (orig_legacy.get("body") or "").strip()
            if lb:
                return lb, "legacy"

    # Legacy fallback
    if legacy_body:
        return legacy_body, "legacy"
    if use_rebuilt and rebuilt_body:
        return rebuilt_body, "rebuilt_garbled"
    if rebuilt_body:
        return rebuilt_body, "rebuilt_garbled"
    return "", "empty"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with OVERLAY_PATH.open("r", encoding="utf-8") as fh:
        overlay: list[dict] = json.load(fh)
    print(f"Loaded {len(overlay)} overlay entries")

    with REBUILT_PATH.open("r", encoding="utf-8") as fh:
        rebuilt: list[dict] = json.load(fh)
    print(f"Loaded {len(rebuilt)} rebuilt entries")

    with LEGACY_PATH.open("r", encoding="utf-8") as fh:
        legacy: list[dict] = json.load(fh)
    legacy_by_term: dict[str, dict] = {}
    for e in legacy:
        legacy_by_term.setdefault(e["term"], e)
    print(f"Loaded {len(legacy)} legacy entries")

    body_corrections: dict = {}
    if BODY_CORRECTIONS_PATH.exists():
        with BODY_CORRECTIONS_PATH.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
        body_corrections = {k: v for k, v in raw.items() if not k.startswith("_")}
        print(f"Loaded {len(body_corrections)} body corrections")

    assert len(overlay) == len(rebuilt)

    live_entries: list[dict] = []
    report_entries: list[dict] = []
    body_source_counts: dict[str, int] = {}
    type_in_live: dict[str, int] = {}
    promoted_count = 0

    for idx, (o, r) in enumerate(zip(overlay, rebuilt)):
        entry_type = o["entry_type"]
        term = o["term"]
        original_term = o.get("original_term")

        # Look up legacy body by original_term for corrected entries
        if original_term:
            legacy_entry = legacy_by_term.get(original_term)
        else:
            legacy_entry = legacy_by_term.get(term)

        include = False

        if entry_type in LIVE_TYPES:
            include = True
        elif entry_type in PROMOTABLE_TYPES:
            lb = ((legacy_entry or {}).get("body") or "").strip()
            if len(lb) >= MIN_LEGACY_BODY:
                include = True
                entry_type = "legacy_retained"
                promoted_count += 1

        if not include:
            continue

        body, body_source = pick_body(o, r, legacy_entry, original_term, body_corrections)

        # Strip duplicate leading headword (use current term, not original)
        body = strip_leading_headword(term, body)

        # For corrected headwords, also strip the OLD garbled headword
        if original_term and original_term != term:
            body = strip_leading_headword(original_term, body)

        source_pages = o.get("source_pages", [])

        body_source_counts[body_source] = body_source_counts.get(body_source, 0) + 1
        type_in_live[entry_type] = type_in_live.get(entry_type, 0) + 1

        live_entries.append({
            "term": term,
            "body": body,
            "source_pages": source_pages,
        })

        report_entries.append({
            "id": o["id"],
            "term": term,
            "original_term": original_term,
            "entry_type": entry_type,
            "body_source": body_source,
            "body_length": len(body),
        })

    # Write outputs
    live_path = OUT_DIR / "blacks_entries.live_candidate.json"
    with live_path.open("w", encoding="utf-8") as fh:
        json.dump(live_entries, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    report_path = OUT_DIR / "live_build_report.json"
    with report_path.open("w", encoding="utf-8") as fh:
        json.dump({
            "total_overlay_entries": len(overlay),
            "live_entries": len(live_entries),
            "promoted_from_legacy": promoted_count,
            "body_sources": body_source_counts,
            "types_in_live": type_in_live,
            "entries": report_entries,
        }, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    # Summary
    print(f"\n{'='*60}")
    print(f"LIVE CORPUS V3 GENERATED")
    print(f"{'='*60}")
    print(f"\nTotal overlay entries:    {len(overlay)}")
    print(f"Live entries:            {len(live_entries)}")
    print(f"Excluded:                {len(overlay) - len(live_entries)}")
    print(f"Promoted from legacy:    {promoted_count}")

    print(f"\nEntry types in live build:")
    for t in ["verified_main", "provisional_main", "recovered_main",
              "low_confidence_main", "headword_corrected", "legacy_retained",
              "alias_variant", "reversed_polarity", "unmatched_keep", "subentry"]:
        if type_in_live.get(t, 0):
            print(f"  {t:25s} {type_in_live[t]:>6,}")
    print(f"  {'TOTAL':25s} {len(live_entries):>6,}")

    print(f"\nBody sources:")
    for src, count in sorted(body_source_counts.items(), key=lambda x: -x[1]):
        print(f"  {src:25s} {count:>6,}")

    print(f"\nOutput: {live_path}")
    print(f"Report: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
