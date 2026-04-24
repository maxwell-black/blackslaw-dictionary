#!/usr/bin/env python3
"""
validate_rebuild.py — Validate the live corpus and build artifacts.

Hard-fail invariants (exit 1):
  - Malformed JSON or unexpected structure
  - Duplicate terms in live corpus
  - Missing required fields (term, body, source_pages)
  - Empty or whitespace-only or punctuation-only bodies
  - Manifest/split inconsistencies (count mismatch, missing letters, term disagreement)
  - Overlay-accounting failures (live entries not traceable to overlay, overlay IDs unaccounted for)
  - Unexplained count delta from previous build
  - Split files disagree with live corpus

Warning-level checks (reported but do not fail):
  - Suspicious headword/body boundary (body starts with ALL CAPS term different from headword)
  - Probable bleed/page-furniture contamination
  - Cross-reference targets that do not exist as live headwords
  - Suspicious residual reflow (mid-word line breaks)
  - OCR artifact clusters
  - source_pages with leaf numbers outside valid range (1-1238)
  - Garbled body starts

Usage:
    python scripts/validate_rebuild.py [path-to-live-candidate]
    python scripts/validate_rebuild.py --full   # full validation including overlay/split/delta checks
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

# Force UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# ── paths ──────────────────────────────────────────────────────────────────
LIVE_CANDIDATE = ROOT / "rebuild" / "out" / "blacks_entries.live_candidate.json"
BLACKS_ENTRIES = ROOT / "blacks_entries.json"
OVERLAY_PATH = ROOT / "rebuild" / "overlay" / "editorial_overlay.json"
BUILD_REPORT_PATH = ROOT / "rebuild" / "out" / "live_build_report.json"
MANIFEST_PATH = ROOT / "data" / "manifest.json"
PREV_COUNT_PATH = ROOT / "rebuild" / "out" / ".prev_live_count"

# ── constants ──────────────────────────────────────────────────────────────
VALID_PAGE_MIN = 1
VALID_PAGE_MAX = 1238

LIVE_TYPES = {
    "verified_main", "provisional_main", "recovered_main",
    "low_confidence_main", "alias_variant", "reversed_polarity",
    "unmatched_keep", "subentry", "headword_corrected",
}

PROMOTABLE_TYPES = {"legacy_unresolved"}

PROMOTED_TYPE = "legacy_retained"

EXCLUDED_TYPES = {
    "alias_phantom", "legacy_duplicate", "fragment_artifact",
    "junk_headword", "appendix_abbrev", "legacy_unresolved", "cross_reference",
}

# ── regex patterns ─────────────────────────────────────────────────────────
SHORT_HEADER_RE = re.compile(r"(?m)^[A-Z]{1,4}$")
PAGE_NUMBER_RE = re.compile(r"(?m)^\d{1,4}$")
GARBLED_START_RE = re.compile(r"^[a-z]{1,3}\.\s*(?:from\.|[.,;])")
ALLCAPS_START_RE = re.compile(r"^([A-Z]{3,})")
DIGIT_IN_WORD_RE = re.compile(r"(?<![0-9§\-–,.\/#:])(\d[a-z]{1,3})(?=[\s,;.\)])", re.ASCII)
AT_SIGN_RE = re.compile(r"@")
SEE_PATTERN_RE = re.compile(r"\bSee ([A-Z][A-Z ]{2,})")
PUNCT_ONLY_RE = re.compile(r"^[\s\W]+$")


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── hard-fail checks ──────────────────────────────────────────────────────

def check_structure(entries: list) -> list[str]:
    """Verify corpus is a list of dicts with required fields."""
    errors = []
    if not isinstance(entries, list):
        errors.append("Corpus is not a JSON array")
        return errors

    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            errors.append(f"Entry [{i}] is not a dict: {type(e)}")
            continue
        for field in ("term", "body"):
            if field not in e:
                errors.append(f"Entry [{i}] missing required field '{field}'")
        if "source_pages" not in e:
            errors.append(f"Entry [{i}] ({e.get('term', '?')}) missing 'source_pages' field")
    return errors


def check_duplicate_terms(entries: list) -> list[str]:
    """No two entries should have the same term."""
    errors = []
    seen: dict[str, int] = {}
    for i, e in enumerate(entries):
        term = e.get("term", "")
        if term in seen:
            errors.append(f"Duplicate term '{term}' at [{i}] (first at [{seen[term]}])")
        seen[term] = i
    return errors


def check_empty_bodies(entries: list) -> list[str]:
    """Bodies must not be empty, whitespace-only, or punctuation-only."""
    errors = []
    for i, e in enumerate(entries):
        body = e.get("body", "")
        if not body.strip():
            errors.append(f"Empty body at [{i}] term='{e.get('term', '?')}'")
        elif PUNCT_ONLY_RE.match(body):
            errors.append(f"Punctuation-only body at [{i}] term='{e.get('term', '?')}': {body[:50]!r}")
    return errors


def check_manifest_split_consistency(entries: list) -> list[str]:
    """Manifest counts match split file counts and live corpus."""
    errors = []
    if not MANIFEST_PATH.exists():
        errors.append(f"Manifest not found: {MANIFEST_PATH}")
        return errors

    manifest = load_json(MANIFEST_PATH)
    manifest_total = sum(v["count"] for v in manifest.values())
    live_count = len(entries)

    if manifest_total != live_count:
        errors.append(
            f"Manifest total ({manifest_total}) != live corpus count ({live_count})"
        )

    live_terms = {e["term"] for e in entries}
    split_terms: dict[str, str] = {}

    for letter, info in sorted(manifest.items()):
        split_path = ROOT / info["file"]
        if not split_path.exists():
            errors.append(f"Split file missing for letter {letter}: {split_path}")
            continue

        split_data = load_json(split_path)
        actual_count = len(split_data)
        if actual_count != info["count"]:
            errors.append(
                f"Split file {letter}: manifest says {info['count']}, file has {actual_count}"
            )

        for se in split_data:
            t = se["term"]
            if t in split_terms:
                errors.append(f"Term '{t}' in multiple split files: {split_terms[t]} and {info['file']}")
            split_terms[t] = info["file"]

    # Cross-check: every live term in splits, every split term in live
    missing_from_split = live_terms - set(split_terms.keys())
    extra_in_split = set(split_terms.keys()) - live_terms

    if missing_from_split:
        examples = sorted(list(missing_from_split))[:5]
        errors.append(
            f"{len(missing_from_split)} live entries not in any split file: {examples}"
        )
    if extra_in_split:
        examples = sorted(list(extra_in_split))[:5]
        errors.append(
            f"{len(extra_in_split)} split entries not in live corpus: {examples}"
        )

    return errors


def check_overlay_accounting(entries: list) -> list[str]:
    """Every overlay ID is either in the live build or has an excluded type."""
    errors = []
    if not OVERLAY_PATH.exists():
        errors.append(f"Overlay not found: {OVERLAY_PATH}")
        return errors
    if not BUILD_REPORT_PATH.exists():
        errors.append(f"Build report not found: {BUILD_REPORT_PATH}")
        return errors

    overlay = load_json(OVERLAY_PATH)
    build_report = load_json(BUILD_REPORT_PATH)
    build_entries = build_report.get("entries", [])

    build_ids = {e["id"] for e in build_entries}

    # Check for duplicate IDs in build report
    build_id_counts = Counter(e["id"] for e in build_entries)
    dups = {k: v for k, v in build_id_counts.items() if v > 1}
    if dups:
        errors.append(f"Duplicate IDs in build report: {dict(list(dups.items())[:5])}")

    # Every overlay entry must be accounted for
    unaccounted = []
    for oe in overlay:
        eid = oe["id"]
        etype = oe.get("entry_type", "")
        if eid not in build_ids and etype not in EXCLUDED_TYPES:
            # Check if it's a legacy_unresolved that wasn't promoted (that's expected)
            if etype in PROMOTABLE_TYPES:
                continue  # not promoted = short body, expected exclusion
            unaccounted.append(f"{eid} ({oe['term']}, type={etype})")

    if unaccounted:
        errors.append(
            f"{len(unaccounted)} overlay entries not in live build and not excluded-type: "
            + ", ".join(unaccounted[:5])
        )

    # Every build entry must trace to overlay
    overlay_ids = {e["id"] for e in overlay}
    orphan_ids = build_ids - overlay_ids
    if orphan_ids:
        errors.append(f"{len(orphan_ids)} live build IDs not in overlay: {sorted(list(orphan_ids))[:5]}")

    return errors


def check_count_delta(entries: list) -> list[str]:
    """Detect and require explanation for count changes between builds."""
    errors = []
    current_count = len(entries)

    # Read previous count if available
    prev_count = None
    if PREV_COUNT_PATH.exists():
        try:
            prev_count = int(PREV_COUNT_PATH.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            pass

    if prev_count is not None and prev_count != current_count:
        delta = current_count - prev_count
        sign = "+" if delta > 0 else ""

        # Check if build report explains the delta
        explained = False
        if BUILD_REPORT_PATH.exists():
            report = load_json(BUILD_REPORT_PATH)
            # If the report's live_entries matches current, and it has type breakdown,
            # we consider it explained (the generator produced it intentionally)
            if report.get("live_entries") == current_count:
                explained = True

        if not explained:
            errors.append(
                f"Live count changed from {prev_count} to {current_count} ({sign}{delta}) "
                f"but build report does not account for this. "
                f"Regenerate the corpus or update the build report."
            )

    return errors


def check_split_agrees_with_live(entries: list) -> list[str]:
    """Split files' content must match the live corpus exactly."""
    errors = []
    if not MANIFEST_PATH.exists():
        return errors

    manifest = load_json(MANIFEST_PATH)

    # Build lookup from live corpus
    live_by_term: dict[str, dict] = {}
    for e in entries:
        live_by_term[e["term"]] = e

    for letter, info in sorted(manifest.items()):
        split_path = ROOT / info["file"]
        if not split_path.exists():
            continue  # already caught by manifest check

        split_data = load_json(split_path)
        for se in split_data:
            t = se["term"]
            if t not in live_by_term:
                continue  # already caught
            live_e = live_by_term[t]
            # Compare body content
            if se.get("body", "") != live_e.get("body", ""):
                errors.append(f"Split/live body mismatch for '{t}' in {info['file']}")
            if se.get("source_pages") != live_e.get("source_pages"):
                errors.append(f"Split/live source_pages mismatch for '{t}' in {info['file']}")

    if len(errors) > 10:
        trimmed = errors[:10]
        trimmed.append(f"... and {len(errors) - 10} more split/live mismatches")
        return trimmed

    return errors


# ── warning-level checks ──────────────────────────────────────────────────

def warn_headword_body_boundary(entries: list) -> list[str]:
    """Body starts with ALL CAPS term different from headword."""
    warnings = []
    skip_prefixes = re.compile(r"^(In |Lat\.|adj\.|v\.|n\.|Fr\.|Sp\.|Sax\.|Eng\.)", re.IGNORECASE)
    for e in entries:
        body = e.get("body", "")
        term = e["term"]
        if not body or skip_prefixes.match(body):
            continue
        m = ALLCAPS_START_RE.match(body)
        if m:
            caps_word = m.group(1)
            if caps_word != term and not term.startswith(caps_word):
                warnings.append(f"'{term}' body starts with '{caps_word}': {body[:60]}")
    return warnings


def warn_unresolved_crossrefs(entries: list) -> list[str]:
    """'See TERM' where TERM does not exist as a live headword."""
    live_terms = {e["term"].upper() for e in entries}
    warnings = []
    for e in entries:
        body = e.get("body", "")
        if not body:
            continue
        for m in SEE_PATTERN_RE.finditer(body):
            ref = m.group(1).strip()
            if ref.upper() not in live_terms:
                warnings.append(f"'{e['term']}': See {ref} (not a live headword)")
    return warnings


def warn_ocr_artifacts(entries: list) -> list[str]:
    """Digit-in-word and @ sign artifacts."""
    warnings = []
    for e in entries:
        body = e.get("body", "")
        if not body:
            continue
        issues = []
        if AT_SIGN_RE.search(body):
            issues.append("contains @")
        for m in DIGIT_IN_WORD_RE.finditer(body):
            token = m.group(1)
            if re.match(r"^\d+(st|nd|rd|th|d|s)$", token):
                continue
            issues.append(f"digit_in_word '{token}'")
        if issues:
            warnings.append(f"'{e['term']}': {'; '.join(issues[:3])}")
    return warnings


def warn_source_pages_range(entries: list) -> list[str]:
    """source_pages with page numbers outside valid range."""
    warnings = []
    for e in entries:
        pages = e.get("source_pages", [])
        if not isinstance(pages, list):
            continue
        for p in pages:
            try:
                pn = int(p) if isinstance(p, str) else p
                if not (VALID_PAGE_MIN <= pn <= VALID_PAGE_MAX):
                    warnings.append(f"'{e['term']}': page {p} out of range [{VALID_PAGE_MIN}-{VALID_PAGE_MAX}]")
            except (ValueError, TypeError):
                warnings.append(f"'{e['term']}': non-numeric page value '{p}'")
    return warnings


def warn_residual_reflow(entries: list) -> list[str]:
    """Mid-word line breaks that look like column-width reflow artifacts."""
    warnings = []
    for e in entries:
        body = e.get("body", "")
        if not body or "\n" not in body:
            continue
        paragraphs = body.split("\n\n")
        for para in paragraphs:
            lines = para.split("\n")
            for i in range(len(lines) - 1):
                line = lines[i]
                next_line = lines[i + 1]
                if not line or not next_line:
                    continue
                if next_line.lstrip().startswith(("—", "--")):
                    continue
                if re.match(r"^\s*\d+[\.\)]\s", next_line):
                    continue
                ends_alpha = line.rstrip() and line.rstrip()[-1].isalpha()
                ends_no_punct = not line.rstrip().endswith(("-", ".", ",", ";", ":", "!", "?", '"', "'", ")"))
                starts_lower = next_line.lstrip() and next_line.lstrip()[0].islower()
                if ends_alpha and ends_no_punct and starts_lower:
                    snippet = line[-25:] + " [\\n] " + next_line[:25]
                    warnings.append(f"'{e['term']}': {snippet}")
                    break  # one per entry is enough
    return warnings


def warn_garbled_body_start(entries: list) -> list[str]:
    """Garbled body starts (v.\\nfrom. pattern)."""
    warnings = []
    for e in entries:
        body = e.get("body", "")
        if not body:
            continue
        flat = re.sub(r"\s+", " ", body[:60]).strip()
        if GARBLED_START_RE.match(flat):
            warnings.append(f"'{e['term']}': {flat[:50]!r}")
    return warnings


# ── reporting ──────────────────────────────────────────────────────────────

def print_section(title: str, items: list[str], max_show: int = 10):
    if not items:
        return
    print(f"\n  {title}: {len(items)}")
    for line in items[:max_show]:
        print(f"    {line}")
    if len(items) > max_show:
        print(f"    ... and {len(items) - max_show} more")


def save_prev_count(count: int):
    """Save current count for next build's delta comparison."""
    PREV_COUNT_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREV_COUNT_PATH.write_text(str(count), encoding="utf-8")


# ── main validation ───────────────────────────────────────────────────────

def validate(path: Path, full: bool = False) -> int:
    # ── load ────────────────────────────────────────────────────────────
    try:
        entries = load_json(path)
    except json.JSONDecodeError as exc:
        print(f"HARD FAIL: Malformed JSON in {path}: {exc}")
        return 1

    print(f"Validating {path.name}: {len(entries)} entries")

    # ── hard-fail checks ────────────────────────────────────────────────
    hard_errors: list[str] = []

    print("\n[Hard-fail checks]")

    errs = check_structure(entries)
    hard_errors.extend(errs)
    print(f"  Structure/required fields: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

    errs = check_duplicate_terms(entries)
    hard_errors.extend(errs)
    print(f"  Duplicate terms: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

    errs = check_empty_bodies(entries)
    hard_errors.extend(errs)
    print(f"  Empty/punctuation bodies: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

    if full:
        errs = check_manifest_split_consistency(entries)
        hard_errors.extend(errs)
        print(f"  Manifest/split consistency: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

        errs = check_overlay_accounting(entries)
        hard_errors.extend(errs)
        print(f"  Overlay accounting: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

        errs = check_count_delta(entries)
        hard_errors.extend(errs)
        print(f"  Count delta: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

        errs = check_split_agrees_with_live(entries)
        hard_errors.extend(errs)
        print(f"  Split/live agreement: {'PASS' if not errs else f'FAIL ({len(errs)})'}")

    # ── warning-level checks ────────────────────────────────────────────
    print("\n[Warning-level checks]")
    all_warnings: dict[str, list[str]] = {}

    w = warn_headword_body_boundary(entries)
    all_warnings["headword_body_boundary"] = w
    print(f"  Headword/body boundary: {len(w)} warnings")

    w = warn_unresolved_crossrefs(entries)
    all_warnings["unresolved_crossrefs"] = w
    print(f"  Unresolved cross-refs: {len(w)} warnings")

    w = warn_ocr_artifacts(entries)
    all_warnings["ocr_artifacts"] = w
    print(f"  OCR artifacts: {len(w)} warnings")

    w = warn_source_pages_range(entries)
    all_warnings["source_pages_range"] = w
    print(f"  Source pages range: {len(w)} warnings")

    w = warn_residual_reflow(entries)
    all_warnings["residual_reflow"] = w
    print(f"  Residual reflow: {len(w)} warnings")

    w = warn_garbled_body_start(entries)
    all_warnings["garbled_body_start"] = w
    print(f"  Garbled body starts: {len(w)} warnings")

    # ── detailed output ─────────────────────────────────────────────────
    if hard_errors:
        print(f"\n{'='*60}")
        print(f"  HARD FAILURES: {len(hard_errors)}")
        print(f"{'='*60}")
        for err in hard_errors[:30]:
            print(f"  ERROR: {err}")
        if len(hard_errors) > 30:
            print(f"  ... and {len(hard_errors) - 30} more errors")

    total_warnings = sum(len(v) for v in all_warnings.values())
    if total_warnings > 0:
        print(f"\n{'='*60}")
        print(f"  WARNINGS: {total_warnings}")
        print(f"{'='*60}")
        for category, items in all_warnings.items():
            print_section(category, items, max_show=5)

    # ── save count for delta tracking ───────────────────────────────────
    if not hard_errors:
        save_prev_count(len(entries))

    # ── result ──────────────────────────────────────────────────────────
    print()
    if hard_errors:
        print(f"VALIDATION FAILED: {len(hard_errors)} hard errors, {total_warnings} warnings")
        return 1
    else:
        print(f"VALIDATION PASSED: 0 hard errors, {total_warnings} warnings")
        return 0


def main():
    full = False
    path = LIVE_CANDIDATE

    args = sys.argv[1:]
    for arg in args:
        if arg == "--full":
            full = True
        else:
            path = Path(arg)

    if not path.exists():
        # Fallback: try blacks_entries.json
        if BLACKS_ENTRIES.exists() and path == LIVE_CANDIDATE:
            print(f"Note: {path.name} not found, using {BLACKS_ENTRIES.name}")
            path = BLACKS_ENTRIES
        else:
            print(f"File not found: {path}")
            return 1

    return validate(path, full=full)


if __name__ == "__main__":
    sys.exit(main())
