#!/usr/bin/env python3
"""
lexpredict_comparison.py — Compare blackslaw.io corpus against LexPredict's
independent OCR extraction of Black's Law Dictionary, 2nd Edition (1910).

Usage:
    python3 scripts/lexpredict_comparison.py

Prerequisites:
    - Run from the blackslaw-dictionary repo root
    - blacks_entries.json must exist (current live corpus)
    - Internet access to clone LexPredict repo (or cached copy)

Outputs:
    rebuild/reports/lexpredict_comparison.json   — machine-readable full report
    rebuild/reports/lexpredict_comparison.md      — human-readable summary

What this does:
    1. Downloads/caches the LexPredict dataset (CC-BY-SA 4.0)
    2. Normalizes both headword sets
    3. Computes intersection (confirmed real entries)
    4. Computes set differences (candidates for gaps or fabrications)
    5. Runs Levenshtein matching on unmatched entries to find OCR variants
    6. Categorizes every entry in both datasets
    7. Outputs actionable reports

IMPORTANT: The LexPredict dataset is ALSO OCR-corrupted. It is not ground truth.
It is a second independent extraction useful for triangulation. Entries missing
from LexPredict (like ABSTRACT, HABEAS CORPUS) are not necessarily invalid.
"""

import json
import csv
import os
import sys
import subprocess
import re
from pathlib import Path
from collections import Counter, defaultdict


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REPO_ROOT = Path(".")
LIVE_CORPUS = REPO_ROOT / "blacks_entries.json"
LEXPREDICT_CACHE = REPO_ROOT / "rebuild" / "external" / "lexpredict"
LEXPREDICT_CSV = LEXPREDICT_CACHE / "blacks_second_edition_terms.csv"
LEXPREDICT_REPO = "https://github.com/LexPredict/lexpredict-legal-dictionary.git"
REPORT_DIR = REPO_ROOT / "rebuild" / "reports"
REPORT_JSON = REPORT_DIR / "lexpredict_comparison.json"
REPORT_MD = REPORT_DIR / "lexpredict_comparison.md"

# Levenshtein distance threshold for "probable OCR variant"
LEVENSHTEIN_THRESHOLD = 3

# Minimum headword length to include in comparison (filters junk)
MIN_HEADWORD_LEN = 2


# ---------------------------------------------------------------------------
# Levenshtein distance (no external deps)
# ---------------------------------------------------------------------------

def levenshtein(s1: str, s2: str) -> int:
    """Standard dynamic-programming Levenshtein distance."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            # insertion, deletion, substitution
            curr_row.append(min(
                prev_row[j + 1] + 1,
                curr_row[j] + 1,
                prev_row[j] + (0 if c1 == c2 else 1)
            ))
        prev_row = curr_row
    return prev_row[-1]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_headword(hw: str) -> str:
    """
    Normalize a headword for comparison. Conservative:
    - uppercase
    - strip leading/trailing whitespace and punctuation
    - collapse internal whitespace
    - resolve common ligatures
    Does NOT do OCR correction (that's what we're trying to detect).
    """
    hw = hw.strip().upper()
    # Resolve ligatures
    hw = hw.replace("Æ", "AE").replace("æ", "AE")
    hw = hw.replace("Œ", "OE").replace("œ", "OE")
    # Strip trailing punctuation
    hw = re.sub(r'[.,;:\-—]+$', '', hw)
    # Collapse whitespace
    hw = re.sub(r'\s+', ' ', hw).strip()
    return hw


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def fetch_lexpredict():
    """Clone or use cached LexPredict data."""
    if LEXPREDICT_CSV.exists():
        print(f"Using cached LexPredict data: {LEXPREDICT_CSV}")
        return

    print("Downloading LexPredict dataset...")
    LEXPREDICT_CACHE.mkdir(parents=True, exist_ok=True)

    # Sparse clone — only the blacks_second_edition directory
    tmp_dir = REPO_ROOT / "rebuild" / "external" / "_lp_clone"
    if tmp_dir.exists():
        subprocess.run(["rm", "-rf", str(tmp_dir)], check=True)

    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
         LEXPREDICT_REPO, str(tmp_dir)],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        # Fallback: full shallow clone
        print("Sparse clone failed, trying shallow clone...")
        subprocess.run(
            ["git", "clone", "--depth", "1", LEXPREDICT_REPO, str(tmp_dir)],
            capture_output=True, text=True, check=True
        )

    # Try sparse checkout
    subprocess.run(
        ["git", "-C", str(tmp_dir), "sparse-checkout", "set",
         "sources/blacks_second_edition"],
        capture_output=True, text=True
    )

    src = tmp_dir / "sources" / "blacks_second_edition" / "blacks_second_edition_terms.csv"
    if not src.exists():
        # If sparse checkout didn't work, look for the file anyway
        for f in tmp_dir.rglob("blacks_second_edition_terms.csv"):
            src = f
            break

    if not src.exists():
        print(f"ERROR: Could not find blacks_second_edition_terms.csv in cloned repo")
        sys.exit(1)

    # Copy CSV to cache
    import shutil
    shutil.copy2(src, LEXPREDICT_CSV)

    # Also grab JSON if available
    src_json = src.parent / "blacks_second_edition_terms.json"
    if src_json.exists():
        shutil.copy2(src_json, LEXPREDICT_CACHE / "blacks_second_edition_terms.json")

    # Cleanup clone
    subprocess.run(["rm", "-rf", str(tmp_dir)], capture_output=True)
    print(f"Cached LexPredict data to {LEXPREDICT_CACHE}")


def load_lexpredict() -> list[dict]:
    """Load LexPredict CSV. Returns list of {term, definition, norm}."""
    entries = []
    with open(LEXPREDICT_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            term = row.get('term', '').strip()
            defn = row.get('definition', '').strip()
            if term:
                entries.append({
                    'term': term,
                    'definition': defn,
                    'norm': normalize_headword(term),
                })
    return entries


def load_live_corpus() -> list[dict]:
    """Load blackslaw.io live corpus. Returns list of {id, headword, body, norm}.

    Handles both field naming conventions:
    - 'term' (current live corpus format)
    - 'headword' (legacy format)
    """
    with open(LIVE_CORPUS, encoding='utf-8') as f:
        data = json.load(f)

    entries = []
    for entry in data:
        hw = entry.get('term', entry.get('headword', '')).strip()
        if hw:
            entries.append({
                'id': entry.get('id', hw),
                'headword': hw,
                'body': entry.get('body', ''),
                'norm': normalize_headword(hw),
            })
    return entries


# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------

def find_levenshtein_matches(unmatched_source: list[str],
                              unmatched_target: list[str],
                              threshold: int = LEVENSHTEIN_THRESHOLD) -> list[dict]:
    """
    For each unmatched source term, find the closest target term by
    Levenshtein distance. Returns matches within threshold.

    This is O(n*m) but both sets should be < 2000, so ~4M comparisons max.
    """
    matches = []
    for s in unmatched_source:
        best_dist = threshold + 1
        best_match = None
        for t in unmatched_target:
            # Quick length filter
            if abs(len(s) - len(t)) > threshold:
                continue
            d = levenshtein(s, t)
            if d < best_dist:
                best_dist = d
                best_match = t
        if best_match is not None and best_dist <= threshold:
            matches.append({
                'source': s,
                'target': best_match,
                'distance': best_dist,
            })
    return matches


def classify_levenshtein_match(source_term: str, target_term: str) -> str:
    """Classify what kind of OCR error produced the difference."""
    patterns = []
    s, t = source_term.upper(), target_term.upper()

    # Check known OCR confusion pairs
    confusions = [
        ('O', 'C'), ('I', 'L'), ('U', 'V'), ('M', 'N'),
        ('H', 'N'), ('Z', 'S'), ('0', 'O'), ('1', 'I'),
        ('B', 'D'), ('F', 'P'), ('G', 'C'), ('E', 'F'),
    ]

    if len(s) == len(t):
        diffs = [(i, s[i], t[i]) for i in range(len(s)) if s[i] != t[i]]
        for pos, sc, tc in diffs:
            pair = tuple(sorted([sc, tc]))
            for c1, c2 in confusions:
                if pair == tuple(sorted([c1, c2])):
                    patterns.append(f"{sc}->{tc} (pos {pos})")
                    break
            else:
                patterns.append(f"{sc}->{tc} (pos {pos})")

    if patterns:
        return "; ".join(patterns)
    return "length_or_complex_diff"


def run_comparison(live_entries: list[dict], lp_entries: list[dict]) -> dict:
    """Main comparison logic. Returns full report dict."""

    # Build normalized sets
    # For live corpus: norm -> list of entries (could have dupes)
    live_by_norm = defaultdict(list)
    for e in live_entries:
        if len(e['norm']) >= MIN_HEADWORD_LEN:
            live_by_norm[e['norm']].append(e)

    lp_by_norm = defaultdict(list)
    for e in lp_entries:
        if len(e['norm']) >= MIN_HEADWORD_LEN:
            lp_by_norm[e['norm']].append(e)

    live_norms = set(live_by_norm.keys())
    lp_norms = set(lp_by_norm.keys())

    # Set operations
    intersection = live_norms & lp_norms
    live_only = live_norms - lp_norms
    lp_only = lp_norms - live_norms

    print(f"\n=== Set comparison (normalized) ===")
    print(f"Live corpus unique normalized headwords: {len(live_norms)}")
    print(f"LexPredict unique normalized headwords:  {len(lp_norms)}")
    print(f"Intersection (confirmed in both):        {len(intersection)}")
    print(f"Live only (in blackslaw, not LexPredict): {len(live_only)}")
    print(f"LexPredict only (in LP, not blackslaw):   {len(lp_only)}")

    # Levenshtein matching on the unmatched sets
    print(f"\nRunning Levenshtein matching on {len(live_only)} x {len(lp_only)} unmatched pairs...")
    print(f"(threshold: {LEVENSHTEIN_THRESHOLD})")

    # Live-only -> closest LP match
    live_to_lp = find_levenshtein_matches(sorted(live_only), sorted(lp_only))
    # LP-only -> closest live match
    lp_to_live = find_levenshtein_matches(sorted(lp_only), sorted(live_only))

    print(f"Live->LP near matches: {len(live_to_lp)}")
    print(f"LP->Live near matches: {len(lp_to_live)}")

    # Classify matches
    for m in live_to_lp:
        m['ocr_pattern'] = classify_levenshtein_match(m['source'], m['target'])
    for m in lp_to_live:
        m['ocr_pattern'] = classify_levenshtein_match(m['source'], m['target'])

    # Build the matched-via-levenshtein sets
    lev_matched_live = {m['source'] for m in live_to_lp}
    lev_matched_lp = {m['source'] for m in lp_to_live}

    # True unmatched (no exact or Levenshtein match)
    true_live_only = live_only - lev_matched_live
    true_lp_only = lp_only - lev_matched_lp

    # Categorize true_lp_only (entries LP has that we don't, and no near match)
    # These are potential gaps in the blackslaw.io corpus
    lp_gaps = []
    for norm in sorted(true_lp_only):
        lp_e = lp_by_norm[norm][0]
        lp_gaps.append({
            'term': lp_e['term'],
            'norm': norm,
            'definition_preview': lp_e['definition'][:120],
            'definition_length': len(lp_e['definition']),
        })

    # Categorize true_live_only (entries we have that LP doesn't, and no near match)
    # These are either: (a) entries LP missed, or (b) our fabrications
    live_extras = []
    for norm in sorted(true_live_only):
        live_e = live_by_norm[norm][0]
        live_extras.append({
            'id': live_e['id'],
            'headword': live_e['headword'],
            'norm': norm,
            'body_preview': live_e['body'][:120],
            'body_length': len(live_e['body']),
        })

    # Summary statistics
    report = {
        'metadata': {
            'live_corpus_total': len(live_entries),
            'live_corpus_unique_normalized': len(live_norms),
            'lexpredict_total': len(lp_entries),
            'lexpredict_unique_normalized': len(lp_norms),
            'comparison_min_headword_len': MIN_HEADWORD_LEN,
            'levenshtein_threshold': LEVENSHTEIN_THRESHOLD,
        },
        'summary': {
            'exact_match_count': len(intersection),
            'exact_match_pct_of_live': round(100 * len(intersection) / len(live_norms), 1),
            'exact_match_pct_of_lp': round(100 * len(intersection) / len(lp_norms), 1),
            'live_only_total': len(live_only),
            'lp_only_total': len(lp_only),
            'levenshtein_matched_live_to_lp': len(live_to_lp),
            'levenshtein_matched_lp_to_live': len(lp_to_live),
            'true_unmatched_live_only': len(true_live_only),
            'true_unmatched_lp_only': len(true_lp_only),
        },
        'levenshtein_matches_live_to_lp': sorted(live_to_lp, key=lambda x: x['distance']),
        'levenshtein_matches_lp_to_live': sorted(lp_to_live, key=lambda x: x['distance']),
        'true_lp_only_potential_gaps': lp_gaps,
        'true_live_only_potential_extras': live_extras,
        # Don't dump the full intersection — it's 10K+ entries. Just count.
        'intersection_sample': sorted(list(intersection))[:50],
    }

    return report


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_markdown_report(report: dict):
    """Generate human-readable summary."""
    s = report['summary']
    m = report['metadata']

    lines = [
        "# LexPredict vs blackslaw.io Comparison Report",
        "",
        "## Dataset Overview",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| blackslaw.io live entries | {m['live_corpus_total']} |",
        f"| blackslaw.io unique normalized | {m['live_corpus_unique_normalized']} |",
        f"| LexPredict entries | {m['lexpredict_total']} |",
        f"| LexPredict unique normalized | {m['lexpredict_unique_normalized']} |",
        "",
        "## Match Results",
        "",
        f"| Category | Count | Notes |",
        f"|----------|-------|-------|",
        f"| Exact match (both) | {s['exact_match_count']} | {s['exact_match_pct_of_live']}% of live, {s['exact_match_pct_of_lp']}% of LP |",
        f"| Live only (before Lev) | {s['live_only_total']} | In blackslaw but not LP |",
        f"| LP only (before Lev) | {s['lp_only_total']} | In LP but not blackslaw |",
        f"| Levenshtein matched (live->LP) | {s['levenshtein_matched_live_to_lp']} | OCR variants |",
        f"| Levenshtein matched (LP->live) | {s['levenshtein_matched_lp_to_live']} | OCR variants |",
        f"| True unmatched (live only) | {s['true_unmatched_live_only']} | Possible LP gaps or our fabrications |",
        f"| True unmatched (LP only) | {s['true_unmatched_lp_only']} | **Possible blackslaw gaps** or LP fabrications |",
        "",
        "## Action Items",
        "",
        f"### Potential gaps in blackslaw.io ({s['true_unmatched_lp_only']} entries)",
        "",
        "These entries exist in LexPredict but have no exact or near match in blackslaw.io.",
        "Some are real entries we're missing. Some are LexPredict OCR artifacts.",
        "Review manually, prioritizing entries with longer definitions (more likely real).",
        "",
    ]

    # Top 50 potential gaps sorted by definition length (longer = more likely real)
    gaps = sorted(report['true_lp_only_potential_gaps'],
                  key=lambda x: -x['definition_length'])
    lines.append(f"Top potential gaps (by definition length, showing first 50):")
    lines.append("")
    lines.append("| Term | Def Length | Definition Preview |")
    lines.append("|------|-----------|-------------------|")
    for g in gaps[:50]:
        preview = g['definition_preview'].replace('|', '/').replace('\n', ' ')
        lines.append(f"| {g['term']} | {g['definition_length']} | {preview} |")

    lines.append("")
    lines.append(f"### Potential extras in blackslaw.io ({s['true_unmatched_live_only']} entries)")
    lines.append("")
    lines.append("These entries exist in blackslaw.io but have no exact or near match in LexPredict.")
    lines.append("Most are likely real entries that LexPredict missed (LP also has OCR gaps).")
    lines.append("Short-body entries with garbled headwords are candidates for further review.")
    lines.append("")

    extras = sorted(report['true_live_only_potential_extras'],
                    key=lambda x: x['body_length'])
    lines.append(f"Shortest-body extras (most suspicious, showing first 50):")
    lines.append("")
    lines.append("| Headword | Body Length | Body Preview |")
    lines.append("|----------|-----------|-------------|")
    for e in extras[:50]:
        preview = e['body_preview'].replace('|', '/').replace('\n', ' ')
        lines.append(f"| {e['headword']} | {e['body_length']} | {preview} |")

    lines.append("")
    lines.append("### Levenshtein near-matches (OCR variant pairs)")
    lines.append("")
    lines.append("These pairs differ by 1-3 characters and are likely the same entry")
    lines.append("garbled differently by different OCR engines.")
    lines.append("")

    lines.append("#### blackslaw -> LexPredict (distance 1 only, first 30):")
    lines.append("")
    lines.append("| blackslaw term | LexPredict term | Dist | OCR Pattern |")
    lines.append("|---------------|----------------|------|-------------|")
    d1_matches = [m for m in report['levenshtein_matches_live_to_lp'] if m['distance'] == 1]
    for m in d1_matches[:30]:
        lines.append(f"| {m['source']} | {m['target']} | {m['distance']} | {m['ocr_pattern']} |")

    lines.append("")
    lines.append("#### LexPredict -> blackslaw (distance 1 only, first 30):")
    lines.append("")
    lines.append("| LexPredict term | blackslaw term | Dist | OCR Pattern |")
    lines.append("|----------------|---------------|------|-------------|")
    d1_matches = [m for m in report['levenshtein_matches_lp_to_live'] if m['distance'] == 1]
    for m in d1_matches[:30]:
        lines.append(f"| {m['source']} | {m['target']} | {m['distance']} | {m['ocr_pattern']} |")

    lines.append("")
    lines.append("## Known LexPredict Issues")
    lines.append("")
    lines.append("The LexPredict dataset has its own OCR problems:")
    lines.append("- ABSTRACT is missing entirely")
    lines.append("- HABEAS CORPUS is missing entirely")
    lines.append("- Contains O-for-C garbling (OOURT, OONTRACTU, CCELO)")
    lines.append("- 59 duplicate headwords (C. C appears 11 times)")
    lines.append("- No OCR cleanup was applied (raw 2017 extraction)")
    lines.append("- Therefore: entries 'missing' from LP are not necessarily invalid in blackslaw")
    lines.append("")

    with open(REPORT_MD, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    print(f"Wrote: {REPORT_MD}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Verify we're in the right directory
    if not LIVE_CORPUS.exists():
        print(f"ERROR: {LIVE_CORPUS} not found. Run from the blackslaw-dictionary repo root.")
        sys.exit(1)

    # Ensure report directory exists
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    LEXPREDICT_CACHE.mkdir(parents=True, exist_ok=True)

    # Fetch LexPredict data
    fetch_lexpredict()

    # Load both datasets
    print("Loading live corpus...")
    live_entries = load_live_corpus()
    print(f"  Loaded {len(live_entries)} entries")

    print("Loading LexPredict dataset...")
    lp_entries = load_lexpredict()
    print(f"  Loaded {len(lp_entries)} entries")

    # Run comparison
    report = run_comparison(live_entries, lp_entries)

    # Write reports
    with open(REPORT_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {REPORT_JSON}")

    write_markdown_report(report)

    # Print summary
    s = report['summary']
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Confirmed in both:          {s['exact_match_count']}")
    print(f"OCR variant pairs found:    {s['levenshtein_matched_live_to_lp']} (live->LP), "
          f"{s['levenshtein_matched_lp_to_live']} (LP->live)")
    print(f"True unmatched (live only):  {s['true_unmatched_live_only']}  <- review for fabrications")
    print(f"True unmatched (LP only):    {s['true_unmatched_lp_only']}  <- review for GAPS")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
