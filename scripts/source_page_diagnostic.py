#!/usr/bin/env python3
"""
source_page_diagnostic.py — Two-part diagnostic:

Part 1: Diagnose the 3,854 monotonicity breaks.
  - Are they systematic (same offset pattern) or scattered?
  - Are they leaf-vs-page confusion?
  - What's the distribution of backward jump sizes?
  - Should the threshold be adjusted, or is there a pipeline offset?

Part 2: Build a recovery worklist for the 24 out-of-range entries.
  - Extract body-oracle headword candidates
  - Look up what entries SHOULD be on that source page
  - Cross-reference against overlay and live corpus
  - Generate IA viewer URLs for manual verification
  - Output a ready-to-act worklist

Usage:
    python3 scripts/source_page_diagnostic.py

Requires:
    - blacks_entries.json (live corpus)
    - rebuild/reports/source_page_validation.json (from source_page_validator.py)
    - rebuild/overlay/editorial_overlay.json (for classification lookups)
    - rebuild/out/source_pages.jsonl (for page content lookups)

Outputs:
    rebuild/reports/monotonicity_diagnostic.json
    rebuild/reports/monotonicity_diagnostic.md
    rebuild/reports/out_of_range_recovery.json
    rebuild/reports/out_of_range_recovery.md
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

REPO_ROOT = Path(".")
LIVE_CORPUS = REPO_ROOT / "blacks_entries.json"
VALIDATION_REPORT = REPO_ROOT / "rebuild" / "reports" / "source_page_validation.json"
OVERLAY = REPO_ROOT / "rebuild" / "overlay" / "editorial_overlay.json"
SOURCE_PAGES = REPO_ROOT / "rebuild" / "out" / "source_pages.jsonl"
REPORT_DIR = REPO_ROOT / "rebuild" / "reports"

IA_IDENTIFIER = "blacks-law-dictionary-2nd-edition-1910"
IA_URL_TEMPLATE = f"https://archive.org/details/{IA_IDENTIFIER}/page/n{{leaf}}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_letter(hw: str) -> str:
    hw = hw.strip().upper()
    for ch in hw:
        if ch.isalpha():
            return ch
    return "?"


def extract_pages(entry: dict) -> list[int]:
    sp = entry.get("source_pages", [])
    if not sp:
        return []
    if isinstance(sp, (int, float)):
        return [int(sp)]
    if isinstance(sp, list):
        pages = []
        for item in sp:
            if isinstance(item, (int, float)):
                pages.append(int(item))
            elif isinstance(item, str):
                try:
                    pages.append(int(item))
                except ValueError:
                    pass
            elif isinstance(item, dict):
                for key in ("leaf", "page", "leaf_number", "page_number"):
                    if key in item:
                        try:
                            pages.append(int(item[key]))
                        except (ValueError, TypeError):
                            pass
        return pages
    if isinstance(sp, str):
        try:
            return [int(sp)]
        except ValueError:
            return []
    return []


def extract_body_oracle_candidate(body: str) -> str | None:
    """
    Try to extract a headword candidate from the first sentence of the body.
    Many entries start by restating the headword:
      "ACCION. In Spanish law, ..."
      "CHATTEL. An article of personal property."
    """
    if not body:
        return None

    body = body.strip()

    # Strategy 1: First capitalized word/phrase before a period or comma
    m = re.match(r'^([A-Z][A-Z\s\-\'\.]{1,60}?)\s*[.,;:]', body)
    if m:
        candidate = m.group(1).strip().rstrip('.')
        if len(candidate) >= 2 and candidate.upper() == candidate:
            return candidate

    # Strategy 2: "See TERM" or "Same as TERM" pattern
    m = re.search(r'(?:See|Same as|Vide)\s+([A-Z][A-Z\s\-]{1,40}?)[\s.,;]', body)
    if m:
        return m.group(1).strip()

    # Strategy 3: First significant word if body starts with a language marker
    # e.g., "Fr. To drive..." -> look further in
    m = re.match(r'^(?:L\.\s*)?(?:Fr|Lat|Sp|Germ?|Eng)\.\s*(.*)', body, re.IGNORECASE)
    if m:
        rest = m.group(1).strip()
        # This is a definition, not a headword echo — return None
        return None

    return None


def load_source_page_content() -> dict[int, str]:
    """Load source_pages.jsonl to get page text by leaf number."""
    content = {}
    sp_path = SOURCE_PAGES
    if not sp_path.exists():
        return content
    with open(sp_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                leaf = obj.get("leaf") or obj.get("leaf_number") or obj.get("page")
                text = obj.get("text", "")
                if leaf is not None:
                    content[int(leaf)] = text
            except (json.JSONDecodeError, ValueError):
                pass
    return content


def find_nearby_entries_for_page(page: int, entries_by_page: dict, window: int = 3) -> list[dict]:
    """Find entries whose source_pages are within `window` of the given page."""
    nearby = []
    for p in range(page - window, page + window + 1):
        if p in entries_by_page:
            nearby.extend(entries_by_page[p])
    return nearby


# ---------------------------------------------------------------------------
# Part 1: Monotonicity diagnostic
# ---------------------------------------------------------------------------

def diagnose_monotonicity(entries: list[dict], validation_report: dict) -> dict:
    """Analyze the pattern of monotonicity breaks."""

    breaks_by_letter = validation_report.get("monotonicity_breaks", {})
    total_breaks = sum(len(v) for v in breaks_by_letter.items())

    # Collect all backward jump sizes
    all_jumps = []
    jumps_by_letter = defaultdict(list)
    for letter, breaks in breaks_by_letter.items():
        for b in breaks:
            jump = b.get("backward_jump", 0)
            all_jumps.append(jump)
            jumps_by_letter[letter].append(jump)

    if not all_jumps:
        return {"finding": "no_breaks", "detail": "No monotonicity breaks found."}

    # Jump size distribution
    jump_counter = Counter()
    for j in all_jumps:
        if j <= 5:
            jump_counter["1-5"] += 1
        elif j <= 10:
            jump_counter["6-10"] += 1
        elif j <= 20:
            jump_counter["11-20"] += 1
        elif j <= 50:
            jump_counter["21-50"] += 1
        elif j <= 100:
            jump_counter["51-100"] += 1
        else:
            jump_counter["100+"] += 1

    # Check for systematic pattern: are most breaks small (< 10)?
    small_breaks = sum(1 for j in all_jumps if j <= 10)
    medium_breaks = sum(1 for j in all_jumps if 10 < j <= 50)
    large_breaks = sum(1 for j in all_jumps if j > 50)

    # Check: are breaks concentrated in specific letters?
    breaks_per_letter = {letter: len(breaks) for letter, breaks in breaks_by_letter.items()}

    # Check: what's the median jump?
    sorted_jumps = sorted(all_jumps)
    median_jump = sorted_jumps[len(sorted_jumps) // 2]
    mean_jump = sum(all_jumps) / len(all_jumps)

    # Determine if this is a "two-column interleaving" pattern
    # In a two-column dictionary, the alphabetical order weaves between
    # left column (lower y) and right column (higher y) on the same page.
    # When entries are sorted by headword, you'd see: page N (left col),
    # page N (right col), page N+1 (left col)... The right-col entry
    # may have the same page as the left-col entry of the next alphabetical
    # term, creating apparent backward jumps of 0-2 pages.
    two_col_pattern = sum(1 for j in all_jumps if j <= 3)

    # Check: source_pages — are they leaves (0-indexed) or printed pages?
    # Printed pages typically start around 1-10 for front matter.
    # Leaves for this book go 0-1327.
    # If source_pages for "A" section start at ~12, they're leaves.
    # If they start at ~1-10, they're printed pages.
    a_entries = [e for e in entries if get_letter(e.get("headword", "")) == "A"]
    a_pages = []
    for e in a_entries:
        a_pages.extend(extract_pages(e))
    a_min = min(a_pages) if a_pages else 0

    # The dictionary body starts at leaf 12.
    # Printed page 1 of the dictionary is ~leaf 12.
    # If A section source_pages start around 12, they're leaf numbers.
    # If they start around 1, they're printed page numbers.
    page_type = "leaf_numbers" if a_min >= 10 else "printed_pages"

    # Build diagnosis
    if two_col_pattern > len(all_jumps) * 0.6:
        primary_cause = "two_column_interleaving"
        explanation = (
            f"{two_col_pattern} of {len(all_jumps)} breaks ({100*two_col_pattern//len(all_jumps)}%) "
            f"are jumps of 1-3 pages. This is the expected pattern for a two-column dictionary: "
            f"alphabetical order weaves between left and right columns on the same page, "
            f"creating small apparent backward jumps when sorted by headword. "
            f"These are not data errors. The monotonicity threshold should be raised to >3 "
            f"to filter them out, or the check should be made two-column-aware."
        )
        actionable = False
    elif small_breaks > len(all_jumps) * 0.7:
        primary_cause = "small_jump_noise"
        explanation = (
            f"{small_breaks} of {len(all_jumps)} breaks are jumps of 1-10 pages. "
            f"Likely a combination of two-column interleaving and minor source_pages "
            f"assignment imprecision. Not individually actionable."
        )
        actionable = False
    else:
        primary_cause = "mixed_or_systematic_offset"
        explanation = (
            f"Breaks are distributed across multiple size ranges. "
            f"Median jump: {median_jump}, mean: {mean_jump:.1f}. "
            f"Large breaks (>50 pages): {large_breaks}. "
            f"This may indicate a systematic offset in source_pages assignment "
            f"or genuine headword misplacements beyond what the out-of-range detector caught."
        )
        actionable = large_breaks > 0

    return {
        "total_breaks": len(all_jumps),
        "page_type": page_type,
        "a_section_min_page": a_min,
        "jump_size_distribution": dict(jump_counter),
        "small_breaks_lte_10": small_breaks,
        "medium_breaks_11_50": medium_breaks,
        "large_breaks_gt_50": large_breaks,
        "two_col_pattern_lte_3": two_col_pattern,
        "median_jump": median_jump,
        "mean_jump": round(mean_jump, 1),
        "breaks_per_letter": breaks_per_letter,
        "primary_cause": primary_cause,
        "explanation": explanation,
        "actionable": actionable,
        "recommendation": (
            "Raise the monotonicity backward-jump threshold to at least 10 pages "
            "to filter out two-column interleaving noise. Only investigate breaks "
            "with backward jumps > 50 pages as potential misplacements."
            if not actionable else
            "Investigate the large backward jumps (>50 pages) individually. "
            "These may be genuine misplacements not caught by the out-of-range detector."
        ),
        "large_break_samples": [
            b for letter_breaks in breaks_by_letter.values()
            for b in letter_breaks
            if b.get("backward_jump", 0) > 50
        ][:30],
    }


# ---------------------------------------------------------------------------
# Part 2: Out-of-range recovery worklist
# ---------------------------------------------------------------------------

def build_recovery_worklist(entries: list[dict], validation_report: dict) -> dict:
    """Build actionable recovery worklist for out-of-range entries."""

    oor_entries = validation_report.get("out_of_range_entries", [])
    if not oor_entries:
        return {"count": 0, "worklist": []}

    # Build lookup structures
    entries_by_id = {e.get("id", ""): e for e in entries}

    # Build page -> entries index
    entries_by_page = defaultdict(list)
    for e in entries:
        for p in extract_pages(e):
            entries_by_page[p].append({
                "id": e.get("id", ""),
                "headword": e.get("headword", ""),
                "letter": get_letter(e.get("headword", "")),
            })

    # Build headword set for duplicate checking
    headword_set = {e.get("headword", "").strip().upper() for e in entries}

    # Load overlay if available
    overlay_by_id = {}
    if OVERLAY.exists():
        with open(OVERLAY, encoding="utf-8") as f:
            overlay_data = json.load(f)
        # Handle both list and dict formats
        if isinstance(overlay_data, list):
            for oe in overlay_data:
                oid = oe.get("id", "")
                if oid:
                    overlay_by_id[oid] = oe
        elif isinstance(overlay_data, dict):
            overlay_by_id = overlay_data

    # Load source page content if available
    page_content = load_source_page_content()

    worklist = []
    for oor in oor_entries:
        entry_id = oor.get("id", "")
        headword = oor.get("headword", "")
        letter = oor.get("letter", "")
        source_pages = oor.get("source_pages", [])
        inferred_letter = oor.get("inferred_letter", "?")
        body_preview = oor.get("body_preview", "")
        severity = oor.get("severity", "medium")

        # Get full entry
        full_entry = entries_by_id.get(entry_id, {})
        full_body = full_entry.get("body", "")

        # Body-oracle: try to extract the real headword from body text
        oracle_candidate = extract_body_oracle_candidate(full_body)

        # Check if oracle candidate already exists in corpus
        oracle_exists = False
        if oracle_candidate:
            oracle_exists = oracle_candidate.strip().upper() in headword_set

        # Get overlay info
        overlay_entry = overlay_by_id.get(entry_id, {})
        entry_type = overlay_entry.get("entry_type", "unknown")

        # Get nearby entries (what's on the same source page?)
        nearby = []
        for sp in source_pages:
            nearby.extend(find_nearby_entries_for_page(sp, entries_by_page, window=2))
        # Deduplicate and remove self
        seen_ids = {entry_id}
        nearby_deduped = []
        for n in nearby:
            if n["id"] not in seen_ids:
                seen_ids.add(n["id"])
                nearby_deduped.append(n)

        # Get source page text snippet if available
        page_text_snippet = ""
        for sp in source_pages:
            if sp in page_content:
                page_text_snippet = page_content[sp][:300]
                break

        # Build IA URLs for manual verification
        ia_urls = [IA_URL_TEMPLATE.format(leaf=sp) for sp in source_pages]

        # Determine recommended action
        if oracle_candidate and oracle_exists:
            action = "suppress_duplicate"
            detail = (f"Body starts with '{oracle_candidate}' which already exists as a live entry. "
                      f"This is likely a garbled duplicate. Suppress as legacy_duplicate.")
        elif oracle_candidate and not oracle_exists:
            action = "correct_headword"
            detail = (f"Body starts with '{oracle_candidate}' which is not in the live corpus. "
                      f"If this is a legitimate term, correct the headword via headword_corrected.")
        else:
            action = "manual_review"
            detail = (f"Body-oracle could not extract a candidate. "
                      f"Check the IA page to identify the correct headword visually.")

        worklist.append({
            "entry_id": entry_id,
            "current_headword": headword,
            "current_letter": letter,
            "source_pages": source_pages,
            "inferred_letter": inferred_letter,
            "severity": severity,
            "entry_type": entry_type,
            "body_preview": full_body[:200],
            "body_length": len(full_body),
            "oracle_candidate": oracle_candidate,
            "oracle_exists_in_corpus": oracle_exists,
            "nearby_entries": nearby_deduped[:5],
            "page_text_snippet": page_text_snippet,
            "ia_urls": ia_urls,
            "recommended_action": action,
            "action_detail": detail,
        })

    return {
        "count": len(worklist),
        "action_summary": Counter(w["recommended_action"] for w in worklist),
        "worklist": worklist,
    }


# ---------------------------------------------------------------------------
# Report writing
# ---------------------------------------------------------------------------

def write_monotonicity_report(diag: dict):
    lines = [
        "# Monotonicity Break Diagnostic",
        "",
        f"## Diagnosis: **{diag['primary_cause']}**",
        "",
        diag["explanation"],
        "",
        f"## Statistics",
        "",
        f"- Total breaks: {diag['total_breaks']}",
        f"- Page type: {diag['page_type']} (A section starts at page {diag['a_section_min_page']})",
        f"- Median backward jump: {diag['median_jump']} pages",
        f"- Mean backward jump: {diag['mean_jump']} pages",
        "",
        "## Jump Size Distribution",
        "",
        "| Range | Count |",
        "|-------|-------|",
    ]
    for rng in ["1-5", "6-10", "11-20", "21-50", "51-100", "100+"]:
        count = diag["jump_size_distribution"].get(rng, 0)
        lines.append(f"| {rng} pages | {count} |")

    lines.extend([
        "",
        "## Breaks by Letter",
        "",
        "| Letter | Breaks |",
        "|--------|--------|",
    ])
    for letter, count in sorted(diag["breaks_per_letter"].items()):
        lines.append(f"| {letter} | {count} |")

    if diag["large_break_samples"]:
        lines.extend([
            "",
            "## Large Breaks (>50 pages) — Investigate These",
            "",
            "| Headword | Pages | After | After Pages | Jump |",
            "|----------|-------|-------|-------------|------|",
        ])
        for b in diag["large_break_samples"]:
            pages = ", ".join(str(p) for p in b.get("source_pages", []))
            prev_pages = ", ".join(str(p) for p in b.get("prev_pages", []))
            lines.append(
                f"| {b.get('headword', '')} | {pages} | "
                f"{b.get('prev_headword', '')} | {prev_pages} | -{b.get('backward_jump', 0)} |"
            )

    lines.extend([
        "",
        f"## Recommendation",
        "",
        diag["recommendation"],
    ])

    out = REPORT_DIR / "monotonicity_diagnostic.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote: {out}")


def write_recovery_report(recovery: dict):
    lines = [
        "# Out-of-Range Entry Recovery Worklist",
        "",
        f"**{recovery['count']} entries to process**",
        "",
        "## Action Summary",
        "",
        "| Action | Count |",
        "|--------|-------|",
    ]
    for action, count in recovery["action_summary"].items():
        lines.append(f"| {action} | {count} |")

    lines.extend([
        "",
        "## Worklist",
        "",
    ])

    for i, w in enumerate(recovery["worklist"], 1):
        lines.extend([
            f"### {i}. {w['current_headword']} ({w['entry_id']})",
            "",
            f"- **Current letter:** {w['current_letter']}",
            f"- **Source pages:** {', '.join(str(p) for p in w['source_pages'])}",
            f"- **Inferred letter:** {w['inferred_letter']}",
            f"- **Severity:** {w['severity']}",
            f"- **Entry type:** {w['entry_type']}",
            f"- **Recommended action:** `{w['recommended_action']}`",
            f"- **Detail:** {w['action_detail']}",
            "",
            f"**Body preview:** {w['body_preview'][:150]}",
            "",
        ])

        if w["oracle_candidate"]:
            exists = "YES (duplicate candidate)" if w["oracle_exists_in_corpus"] else "NO (novel correction candidate)"
            lines.append(f"**Body-oracle candidate:** `{w['oracle_candidate']}` — exists in corpus: {exists}")
            lines.append("")

        if w["nearby_entries"]:
            lines.append("**Nearby entries on same page(s):**")
            for n in w["nearby_entries"]:
                lines.append(f"  - {n['headword']} ({n['letter']}, {n['id']})")
            lines.append("")

        if w["ia_urls"]:
            lines.append("**IA viewer links:**")
            for url in w["ia_urls"]:
                lines.append(f"  - {url}")
            lines.append("")

        lines.append("---")
        lines.append("")

    out = REPORT_DIR / "out_of_range_recovery.md"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote: {out}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not LIVE_CORPUS.exists():
        print(f"ERROR: {LIVE_CORPUS} not found. Run from repo root.")
        sys.exit(1)

    if not VALIDATION_REPORT.exists():
        print(f"ERROR: {VALIDATION_REPORT} not found. Run source_page_validator.py first.")
        sys.exit(1)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    print("Loading corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    # Normalize field names: our corpus uses 'term', script expects 'headword'
    for entry in entries:
        if "headword" not in entry and "term" in entry:
            entry["headword"] = entry["term"]
        if "id" not in entry:
            entry["id"] = entry.get("headword", entry.get("term", ""))
    print(f"  {len(entries)} entries")

    print("Loading validation report...")
    with open(VALIDATION_REPORT, encoding="utf-8") as f:
        validation = json.load(f)

    # Part 1: Monotonicity diagnostic
    print("\n=== Part 1: Monotonicity Break Diagnostic ===")
    diag = diagnose_monotonicity(entries, validation)

    diag_json = REPORT_DIR / "monotonicity_diagnostic.json"
    with open(diag_json, "w", encoding="utf-8") as f:
        json.dump(diag, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {diag_json}")

    write_monotonicity_report(diag)

    print(f"\n  Primary cause: {diag['primary_cause']}")
    print(f"  Actionable: {diag['actionable']}")
    print(f"  Small (1-10): {diag['small_breaks_lte_10']}, "
          f"Medium (11-50): {diag['medium_breaks_11_50']}, "
          f"Large (>50): {diag['large_breaks_gt_50']}")

    # Part 2: Recovery worklist
    print("\n=== Part 2: Out-of-Range Recovery Worklist ===")
    recovery = build_recovery_worklist(entries, validation)

    recovery_json = REPORT_DIR / "out_of_range_recovery.json"
    with open(recovery_json, "w", encoding="utf-8") as f:
        json.dump(recovery, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {recovery_json}")

    write_recovery_report(recovery)

    print(f"\n  Entries to process: {recovery['count']}")
    for action, count in recovery["action_summary"].items():
        print(f"    {action}: {count}")

    # Print the worklist summary
    print(f"\n{'='*60}")
    print("RECOVERY WORKLIST SUMMARY")
    print(f"{'='*60}")
    for w in recovery["worklist"]:
        oracle = f" -> oracle: '{w['oracle_candidate']}'" if w["oracle_candidate"] else ""
        exists = " (EXISTS)" if w["oracle_exists_in_corpus"] else ""
        print(f"  [{w['severity']}] {w['current_headword']} "
              f"(p.{','.join(str(p) for p in w['source_pages'])}, "
              f"inferred {w['inferred_letter']}) "
              f"=> {w['recommended_action']}{oracle}{exists}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
