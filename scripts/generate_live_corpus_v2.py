#!/usr/bin/env python3
"""
generate_live_corpus.py — Build the live corpus from the editorial overlay.

Reads:
  rebuild/overlay/editorial_overlay.json  — entry types and metadata
  rebuild/out/blacks_entries.rebuilt.json  — rebuilt entries (source bodies)
  blacks_entries.json                      — legacy entries (fallback bodies)

For each entry whose type is in the live set:
  - Use rebuilt source body if available, non-empty, and not garbled
  - Fall back to legacy body if rebuilt body is bad
  - Strip duplicate leading headwords

Additionally: promotes legacy_unresolved entries with substantial bodies
to legacy_retained and includes them in the live build.

Writes:
  rebuild/out/blacks_entries.live_candidate.json  — staged live corpus
  rebuild/out/live_build_report.json              — what went in and why

Does NOT overwrite blacks_entries.json directly.
Run validate_rebuild.py on the output before promoting.
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
LEGACY_PATH = REPO / "blacks_entries.json"
OUT_DIR = REPO / "rebuild" / "out"

# Types always included in live build
LIVE_TYPES = {
    "verified_main",
    "provisional_main",
    "recovered_main",
    "low_confidence_main",
    "alias_variant",
    "reversed_polarity",
    "unmatched_keep",
    "subentry",
}

# Types that can be promoted to live if they have a substantial legacy body
PROMOTABLE_TYPES = {
    "legacy_unresolved",
}

# Minimum body length (chars) to promote a legacy_unresolved entry
MIN_LEGACY_BODY = 40


def norm_term(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = t.upper().strip().rstrip(".,;:")
    t = re.sub(r"\s+", " ", t)
    return t


def strip_leading_headword(term: str, body: str) -> str:
    """Remove the headword from the start of the body if duplicated."""
    if not body:
        return body
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    # Match: TERM, sense. or TERM. or TERM;
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
    # Also strip if body starts with the headword followed by paren/bracket
    start_re = re.compile(rf"^\s*{escaped}\s+", re.IGNORECASE)
    sm = start_re.match(body)
    if sm and len(body) > len(term) + 5:
        after = body[sm.end():]
        if after and after[0] in "([":
            return after
    return body


def body_looks_garbled(term: str, body: str) -> bool:
    """Detect rebuilt bodies that are obviously broken."""
    if not body or len(body) < 10:
        return True
    first_30 = body[:30].strip()
    # Single-letter or very short fragment at start
    if re.match(r"^[a-z]{1,3}\.\s*$", first_30):
        return True
    if re.match(r"^[a-z]{1,3}\.\s+from\.", first_30):
        return True
    # Body starts with punctuation (truncated)
    if body.lstrip()[0:1] in {",", ".", ";"}:
        return True
    return False


def body_starts_with_headword(term: str, body: str) -> bool:
    if not body:
        return False
    tn = term.upper().rstrip(".,;:")
    return body[:len(tn) + 20].upper().startswith(tn)


def pick_body(
    overlay_rec: dict,
    rebuilt_entry: dict,
    legacy_entry: dict | None,
) -> tuple[str, str]:
    """Pick the best available body. Returns (body, source_label)."""
    rebuilt_body = (rebuilt_entry.get("body") or "").strip()
    legacy_body = ((legacy_entry or {}).get("body") or "").strip()
    term = overlay_rec["term"]
    has_source = overlay_rec.get("source_headword") is not None

    # For source-backed entries: prefer rebuilt, fall back to legacy if garbled
    if has_source and rebuilt_body and not body_looks_garbled(term, rebuilt_body):
        return rebuilt_body, "rebuilt"

    # If rebuilt body is garbled but legacy is good, use legacy
    if has_source and legacy_body and len(legacy_body) >= MIN_LEGACY_BODY:
        return legacy_body, "legacy_fallback"

    # Recovered or promoted entries: prefer rebuilt if available
    if rebuilt_body and not body_looks_garbled(term, rebuilt_body):
        return rebuilt_body, "rebuilt"

    # Fallback to legacy
    if legacy_body:
        return legacy_body, "legacy"

    # Last resort
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

    assert len(overlay) == len(rebuilt), "Overlay and rebuilt must have same length"

    # ============================================================
    # Build live corpus
    # ============================================================
    live_entries: list[dict] = []
    report_entries: list[dict] = []
    body_source_counts: dict[str, int] = {}
    type_in_live: dict[str, int] = {}
    promoted_count = 0

    for idx, (o, r) in enumerate(zip(overlay, rebuilt)):
        entry_type = o["entry_type"]
        term = o["term"]
        legacy_entry = legacy_by_term.get(term)
        include = False

        if entry_type in LIVE_TYPES:
            include = True
        elif entry_type in PROMOTABLE_TYPES:
            # Promote legacy_unresolved with substantial body
            lb = ((legacy_entry or {}).get("body") or "").strip()
            if len(lb) >= MIN_LEGACY_BODY:
                include = True
                entry_type = "legacy_retained"
                promoted_count += 1

        if not include:
            continue

        body, body_source = pick_body(o, r, legacy_entry)

        # Strip duplicate leading headword
        body = strip_leading_headword(term, body)

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
            "entry_type": entry_type,
            "body_source": body_source,
            "body_length": len(body),
            "confidence": o.get("confidence", 0.0),
        })

    # ============================================================
    # Write outputs
    # ============================================================
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

    # ============================================================
    # Summary
    # ============================================================
    print(f"\n{'='*60}")
    print(f"LIVE CORPUS GENERATED")
    print(f"{'='*60}")
    print(f"\nTotal overlay entries:    {len(overlay)}")
    print(f"Live entries:            {len(live_entries)}")
    print(f"Excluded:                {len(overlay) - len(live_entries)}")
    print(f"Promoted from legacy:    {promoted_count}")

    print(f"\nEntry types in live build:")
    for t in ["verified_main", "provisional_main", "recovered_main",
              "low_confidence_main", "legacy_retained", "alias_variant",
              "reversed_polarity", "unmatched_keep", "subentry"]:
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
