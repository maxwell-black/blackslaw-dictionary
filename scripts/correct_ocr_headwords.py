#!/usr/bin/env python3
"""
correct_ocr_headwords.py — Identify and correct garbled OCR headwords.

For each garbled legacy_unresolved entry classified as an OCR duplicate:
1. Find verified_main entries within edit distance <= 3
2. Check if any candidate appears in the garbled entry's body text
3. Filter out legitimate variant spellings and foreign-language terms
4. If the correct headword is already verified_main, mark as legacy_duplicate
5. Output a correction report for review + an overlay patch file

Usage:
    python scripts/correct_ocr_headwords.py [--apply]

Without --apply, writes rebuild/out/ocr_corrections_report.json for review.
With --apply, also writes rebuild/overlay/ocr_headword_patches.json for
use by overlay_patcher.py.
"""

import json
import re
import sys
from collections import Counter
from difflib import get_close_matches, SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── Variant-detection patterns ────────────────────────────────────────────
# These patterns indicate the body introduces the candidate as a known
# alternate spelling, NOT an OCR correction.
_VARIANT_PATTERNS = [
    # "TERM, or CANDIDATE" / "TERM or CANDIDATE"
    r'{gt}[,.]?\s+(?:OR|ALSO|OTHERWISE)\s+{ct}',
    # "CANDIDATE, or TERM"
    r'{ct}[,.]?\s+(?:OR|ALSO|OTHERWISE)\s+{gt}',
    # "TERM, CANDIDATE." (comma-separated variant list at start of body)
    r'{gt}\s*,\s*{ct}[.\s,)]',
    # "TERM, ..., or CANDIDATE" (multi-variant list)
    r'{gt}[,.](?:\s+\w+[,.])*\s*(?:OR\s+)?{ct}',
    # "TERM (also spelled CANDIDATE)" / "TERM (CANDIDATE)"
    r'{gt}\s*\(\s*(?:ALSO\s+(?:SPELLED\s+)?)?{ct}\s*\)',
    # "CANDIDATE (also TERM)" / reverse
    r'{ct}\s*\(\s*(?:ALSO\s+(?:SPELLED\s+)?)?{gt}\s*\)',
    # Cross-ref: "See CANDIDATE" right after headword (first 30 chars after term)
    r'{gt}[.\s]+SEE\s+{ct}',
]

# Language markers near start of body → foreign-language entry, not garble
_LANG_MARKER_RE = re.compile(
    r'^\s*\.?\s*(?:Lat|Fr|Span|Germ|Sax|Norm|Ital)\b', re.IGNORECASE
)
# Broader language context patterns (searched in first 100 chars after headword)
_LANG_CONTEXT_RE = re.compile(
    r'In\s+(?:the\s+)?(?:Spanish|Roman|civil|feudal|old\s+(?:English|French|German)|'
    r'Scotch|canon|maritime|French|Italian|medieval)\s+law\b',
    re.IGNORECASE
)
# Latin-like suffixes that suggest a foreign headword
_LATIN_SUFFIX_RE = re.compile(
    r'(?:IO|IUS|TUS|AE|UM|ALIS|ILIS|IVUS|IVI|ALE|ARE)$'
)
# Headwords that are clearly derivational forms of their candidates
# (suffix additions/removals) and thus separate legitimate entries
_DERIVATIONAL_SUFFIXES = ['EE', 'ER', 'OR', 'ED', 'ING', 'MENT', 'NESS', 'LY', 'AL', 'TION',
                          'SION', 'ENCE', 'ANCE', 'IBLE', 'ABLE', 'IVE', 'OUS', 'FUL', 'LESS',
                          'ISH', 'LIKE', 'SHIP', 'WARD', 'WISE', 'DOM', 'HOOD', 'IST', 'ISM']


def edit_distance(a: str, b: str) -> int:
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i - 1] == b[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    return dp[n]


def is_variant_spelling(body: str, garbled: str, candidate: str) -> bool:
    """Check if body introduces candidate as a known variant/alternate form."""
    upper = body.upper()
    gt = re.escape(garbled.upper())
    ct = re.escape(candidate.upper())
    for pat in _VARIANT_PATTERNS:
        if re.search(pat.format(gt=gt, ct=ct), upper):
            return True
    return False


def is_foreign_term(body: str, garbled: str) -> bool:
    """Check if the body identifies the headword as a foreign-language term."""
    # Strip the headword restatement from start
    text = body
    if text.upper().startswith(garbled.upper()):
        text = text[len(garbled):]
    first_part = text[:100]
    # Direct language abbreviation: "Lat.", "Fr.", etc.
    if _LANG_MARKER_RE.search(first_part[:50]):
        return True
    # Contextual: "In Spanish law", "In civil law", etc.
    if _LANG_CONTEXT_RE.search(first_part):
        return True
    # Latin-like suffix on the headword itself
    if _LATIN_SUFFIX_RE.search(garbled.upper()) and len(garbled) >= 6:
        return True
    return False


def is_derivational_pair(term_a: str, term_b: str) -> bool:
    """Check if two terms are derivationally related (one is a suffix
    modification of the other), suggesting they're separate entries."""
    a, b = term_a.upper(), term_b.upper()
    # Ensure a is the shorter one
    if len(a) > len(b):
        a, b = b, a
    # Check if the longer term starts with the shorter and adds a suffix
    if b.startswith(a):
        suffix = b[len(a):]
        if suffix in _DERIVATIONAL_SUFFIXES:
            return True
    # Check common pairs where the stem differs slightly
    for suf in _DERIVATIONAL_SUFFIXES:
        if a.endswith(suf) and not b.endswith(suf):
            stem_a = a[:-len(suf)]
            if len(stem_a) >= 3 and b.startswith(stem_a):
                return True
        if b.endswith(suf) and not a.endswith(suf):
            stem_b = b[:-len(suf)]
            if len(stem_b) >= 3 and a.startswith(stem_b):
                return True
    return False


def body_has_candidate_in_definition(body: str, garbled: str, candidate: str) -> bool:
    """Check if candidate appears in the first 200 chars of the definition
    (after stripping the headword restatement), as a whole word, and the
    candidate is at least 4 chars long."""
    if candidate.upper() == garbled.upper():
        return False
    if len(candidate) < 4:
        return False
    # Strip headword from start
    text = body
    if text.upper().startswith(garbled.upper()):
        text = text[len(garbled):]
    defn = text[:200].upper()
    pattern = r'\b' + re.escape(candidate.upper()) + r'\b'
    return bool(re.search(pattern, defn))


def body_similarity(body_a: str, body_b: str) -> float:
    """Compare two bodies using SequenceMatcher on first 500 chars."""
    return SequenceMatcher(None, body_a[:500].upper(), body_b[:500].upper()).ratio()


def main():
    apply_mode = "--apply" in sys.argv

    # Load data
    with open(ROOT / "rebuild/reports/unmatched_classification.json", encoding="utf-8") as f:
        classification = json.load(f)
    with open(ROOT / "rebuild/overlay/editorial_overlay.json", encoding="utf-8") as f:
        overlay = json.load(f)
    with open(ROOT / "rebuild/out/blacks_entries.rebuilt.json", encoding="utf-8") as f:
        rebuilt = json.load(f)

    overlay_map = {e["term"]: e for e in overlay}
    rebuilt_map = {e["term"]: e for e in rebuilt}
    verified_set = {e["term"] for e in overlay if e["entry_type"] == "verified_main"}
    verified_upper_map = {t.upper(): t for t in verified_set}
    verified_upper_list = sorted(verified_upper_map.keys())

    # Get garbled OCR duplicates that are legacy_unresolved
    garbled_entries = [
        d for d in classification["ocr_duplicates"]
        if d["edit_distance"] > 0
        and overlay_map.get(d["term"], {}).get("entry_type") == "legacy_unresolved"
    ]
    print(f"Garbled legacy_unresolved entries to process: {len(garbled_entries)}")

    # ── Classification buckets ────────────────────────────────────────────
    tier1 = []  # Very high confidence: body match + not variant + not foreign
    tier2 = []  # Medium: body match but foreign term, or closest_ed1
    tier3 = []  # Low: closest_matched only
    variants_detected = []  # Legitimate variants, not garbles
    no_correction = []

    for d in garbled_entries:
        term = d["term"]
        body = rebuilt_map.get(term, {}).get("body", "")
        closest = d["closest_matched"]
        closest_ed = d["edit_distance"]

        foreign = is_foreign_term(body, term)

        # Find verified_main terms close to garbled term that appear in body
        candidates = get_close_matches(
            term.upper(), verified_upper_list, n=10, cutoff=0.5
        )
        best_body_match = None
        detected_variant = False

        for c in candidates:
            if c == term.upper():
                continue
            ed = edit_distance(term.upper(), c)
            if ed > 3:
                continue

            real_term = verified_upper_map[c]

            if not body_has_candidate_in_definition(body, term, real_term):
                continue

            # Check if it's a variant spelling (ADVOWEE/AVOWEE pattern)
            if is_variant_spelling(body, term, real_term):
                detected_variant = True
                variants_detected.append({
                    "term": term,
                    "variant_of": real_term,
                    "overlay_id": overlay_map[term]["id"],
                    "body_preview": body[:120],
                })
                break  # Don't look for more candidates

            if best_body_match is None or ed < best_body_match[1]:
                best_body_match = (real_term, ed)

        if detected_variant:
            continue

        if best_body_match:
            corr_term, ed = best_body_match
            derivational = is_derivational_pair(term, corr_term)
            if foreign or derivational:
                # Foreign term or derivational pair — likely legitimate, needs review
                tier2.append({
                    "garbled_term": term,
                    "corrected_term": corr_term,
                    "edit_distance": ed,
                    "method": "body_match_foreign" if foreign else "body_match_derivational",
                    "confidence": "medium",
                    "overlay_id": overlay_map[term]["id"],
                    "action": "review",
                    "body_preview": body[:150],
                })
            elif ed <= 2 and len(term) >= 4:
                tier1.append({
                    "garbled_term": term,
                    "corrected_term": corr_term,
                    "edit_distance": ed,
                    "method": "body_match",
                    "confidence": "high",
                    "overlay_id": overlay_map[term]["id"],
                    "action": "retype_legacy_duplicate",
                    "body_preview": body[:150],
                })
            else:
                tier2.append({
                    "garbled_term": term,
                    "corrected_term": corr_term,
                    "edit_distance": ed,
                    "method": "body_match",
                    "confidence": "medium",
                    "overlay_id": overlay_map[term]["id"],
                    "action": "retype_legacy_duplicate",
                    "body_preview": body[:150],
                })
        elif closest in verified_set and closest_ed == 1 and len(term) >= 5:
            if not foreign:
                tier3.append({
                    "garbled_term": term,
                    "corrected_term": closest,
                    "edit_distance": closest_ed,
                    "method": "closest_ed1",
                    "confidence": "low",
                    "overlay_id": overlay_map[term]["id"],
                    "action": "review",
                    "body_preview": body[:150],
                })
            else:
                no_correction.append({
                    "term": term,
                    "closest_matched": closest,
                    "edit_distance": closest_ed,
                    "overlay_id": overlay_map[term]["id"],
                    "reason": "foreign_term_no_body_match",
                    "body_preview": body[:120],
                })
        else:
            no_correction.append({
                "term": term,
                "closest_matched": closest,
                "edit_distance": closest_ed,
                "overlay_id": overlay_map[term]["id"],
                "reason": "no_reliable_correction",
                "body_preview": body[:120],
            })

    print(f"\nResults:")
    print(f"  Tier 1 (high confidence, auto-apply): {len(tier1)}")
    print(f"  Tier 2 (medium, needs review):        {len(tier2)}")
    print(f"  Tier 3 (low, closest_matched only):   {len(tier3)}")
    print(f"  Variants (legitimate, not garble):     {len(variants_detected)}")
    print(f"  No correction found:                  {len(no_correction)}")

    # Show tier 1 samples
    print(f"\n-- Tier 1 samples (first 20) --")
    for c in tier1[:20]:
        print(f"  {c['garbled_term']:28s} -> {c['corrected_term']:28s} (ed={c['edit_distance']})")

    # Show variants
    print(f"\n-- Variants detected (all {len(variants_detected)}) --")
    for v in variants_detected:
        print(f"  {v['term']:28s} variant of {v['variant_of']}")

    # Write report
    report = {
        "summary": {
            "total_processed": len(garbled_entries),
            "tier1_high": len(tier1),
            "tier2_medium": len(tier2),
            "tier3_low": len(tier3),
            "variants_excluded": len(variants_detected),
            "no_correction": len(no_correction),
        },
        "tier1_corrections": tier1,
        "tier2_corrections": tier2,
        "tier3_corrections": tier3,
        "variants_excluded": variants_detected,
        "no_correction": no_correction,
    }
    report_path = ROOT / "rebuild/out/ocr_corrections_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport written to {report_path}")

    if apply_mode:
        # Generate overlay patches for tier 1 only (highest confidence)
        patches = []
        for c in tier1:
            patches.append({
                "id": c["overlay_id"],
                "term": c["garbled_term"],
                "action": "retype",
                "new_type": "legacy_duplicate",
                "reason": f"OCR garble of {c['corrected_term']} (body_match, high confidence)",
                "corrected_headword": c["corrected_term"],
            })
        patch_path = ROOT / "rebuild/overlay/ocr_headword_patches.json"
        with open(patch_path, "w", encoding="utf-8") as f:
            json.dump(patches, f, indent=2, ensure_ascii=False)
        print(f"\nTier 1 patches written to {patch_path} ({len(patches)} entries)")
        print("Run overlay_patcher.py to apply these patches.")
    else:
        print(f"\nRun with --apply to generate overlay patches for {len(tier1)} tier-1 corrections.")


if __name__ == "__main__":
    main()
