#!/usr/bin/env python3
"""
xref_resolution.py — Triage and resolve unresolved cross-references.

Categories:
  1. truncated_ref: OCR cut off the reference mid-word (e.g., "See IN F")
  2. ocr_garbled: Target name has OCR damage (e.g., "JNSANITY" for "INSANITY")
  3. variant_spelling: Target exists under a different spelling/form
  4. suppressed_entry: Target exists in overlay but was suppressed
  5. legitimately_absent: Target genuinely doesn't exist in Black's 2nd Ed
  6. subentry_reference: Target is a subentry/compound defined within another entry

Writes:
  - rebuild/reports/xref_resolution.md
  - rebuild/reports/xref_resolution.json
"""

import json
import re
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent.parent
LIVE_CORPUS = REPO / "blacks_entries.json"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
REPORT_JSON = REPO / "rebuild" / "reports" / "xref_resolution.json"
REPORT_MD = REPO / "rebuild" / "reports" / "xref_resolution.md"


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


def normalize_for_match(s):
    """Normalize term for fuzzy matching."""
    s = s.upper().strip()
    s = re.sub(r'[.,;:\-\s]+', ' ', s).strip()
    return s


def is_truncated_ref(ref):
    """Check if reference looks truncated (cut off mid-word by OCR)."""
    ref = ref.strip()
    # Very short refs (1-3 chars) are almost always truncated
    if len(ref) <= 3:
        return True
    words = ref.split()
    if words:
        last_word = words[-1]
        # Single letter at end (except 'A' as article)
        if len(last_word) == 1 and last_word not in ('A',):
            return True
        # 2-3 char fragment at end of multi-word ref
        if len(last_word) <= 3 and len(words) > 1:
            # Allow known short Latin/legal endings
            if last_word not in ('LAW', 'BAR', 'USE', 'ACT', 'FEE', 'TAX',
                                 'AID', 'SUM', 'DAM', 'VIS', 'RES', 'REI',
                                 'JUS', 'LEX', 'REX', 'DUX', 'PAX', 'LEY',
                                 'SE', 'OF', 'AND', 'THE', 'IN', 'VIN'):
                return True
    return False


# Known OCR character substitutions in this corpus
OCR_SUBS = {
    'B': 'R',   # b/r confusion
    'Z': 'AE',  # z for ae ligature
    'J': 'I',   # j/i confusion
    'P': 'D',   # p/d confusion
    'N': 'IN',  # n for in
}


def try_ocr_correction(ref, headwords_set):
    """Try common OCR corrections to find the real target."""
    ref_upper = ref.upper()

    # Direct character substitution patterns seen in this corpus
    corrections = [
        # b->h swaps
        (r'B(?=[AEIOUY])', 'H'),
        # r/b confusion
        (r'(?<=[A-Z])B(?=[A-Z])', 'R'),
        (r'BIPABIAN', 'RIPARIAN'),
        # Common specific OCR errors
    ]

    # Try specific known corrections
    known_fixes = {
        'JNSANITY': 'INSANITY',
        'ULTRA VIBES': 'ULTRA VIRES',
        'MABITIME INTEBEST': 'MARITIME INTEREST',
        'CROWN OFFICE IN CHANCERBY': 'CROWN OFFICE IN CHANCERY',
        'MEBITS': 'MERITS',
        'EABNINGS': 'EARNINGS',
        'RIPABIAN': 'RIPARIAN',
        'WATEE': 'WATER',
        'MABRIAGE': 'MARRIAGE',
        'PREZEMUNIRE': 'PRAEMUNIRE',
        'PRELIMINABY': 'PRELIMINARY',
        'DVIDENCE': 'EVIDENCE',
        'EXTRAORDINABY': 'EXTRAORDINARY',
        'CHANCELLORB': 'CHANCELLOR',
        'AUNCEL WEIGUT': 'AUNCEL WEIGHT',
        'EVECTMENT': 'EJECTMENT',
        'IORMEDON': 'FORMEDON',
        'BARNEST': 'EARNEST',
        'LN DEMEIES': 'IN DEMESNE',
        'INPURE': 'UMPIRE',
        'DUPLEX VALOR MARITATII': 'DUPLEX VALOR MARITAGII',
        'PRASUMPTIO': 'PRAESUMPTIO',
        'COUTHLAUGH': 'COUTHUTLAUGH',
        'FELONY DE SE': 'FELO DE SE',
        'DE MEDIETATE LINGUS': 'DE MEDIETATE LINGUAE',
        'INGROSS': 'ENGROSS',
    }

    if ref_upper in known_fixes:
        corrected = known_fixes[ref_upper]
        if corrected in headwords_set:
            return corrected
        # Try fuzzy on corrected
        for hw in headwords_set:
            if abs(len(hw) - len(corrected)) <= 2:
                if levenshtein(hw, corrected) <= 2:
                    return hw

    # Try b->r substitution throughout
    if 'B' in ref_upper:
        for i, c in enumerate(ref_upper):
            if c == 'B':
                candidate = ref_upper[:i] + 'R' + ref_upper[i+1:]
                if candidate in headwords_set:
                    return candidate

    return None


def main():
    print("Loading live corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    print("  %d entries" % len(entries))

    live_terms = {e["term"].upper() for e in entries}

    print("Loading overlay...")
    with open(OVERLAY_PATH, encoding="utf-8") as f:
        overlay = json.load(f)
    overlay_by_term = {}
    suppressed_types = {'fragment_artifact', 'legacy_duplicate', 'junk_headword',
                        'legacy_unresolved', 'alias_phantom', 'appendix_abbrev'}
    for o in overlay:
        t = o.get("term", "").upper()
        if t:
            overlay_by_term[t] = o
    print("  %d overlay entries" % len(overlay))

    # Find all unresolved cross-references
    see_pattern = re.compile(r"\bSee ([A-Z][A-Z ]{2,})")
    ref_counter = Counter()
    all_refs = []

    for entry in entries:
        body = entry.get("body", "") or ""
        for m in see_pattern.finditer(body):
            ref = m.group(1).strip()
            if ref.upper() not in live_terms:
                ref_counter[ref] += 1
                all_refs.append({
                    "term": entry["term"],
                    "ref": ref,
                    "snippet": body[max(0, m.start()-30):m.end()+30],
                })

    print("  %d unresolved refs, %d unique targets" % (len(all_refs), len(ref_counter)))

    # Classify each unique missing target
    results = {
        "truncated_ref": [],
        "ocr_garbled": [],
        "variant_match": [],
        "suppressed_entry": [],
        "legitimately_absent": [],
        "subentry_reference": [],
    }

    for ref, count in ref_counter.most_common():
        ref_upper = ref.upper()

        # Get entries that reference this target
        referencing_entries = [r["term"] for r in all_refs if r["ref"] == ref]

        # 1. Try OCR correction FIRST (before truncation check)
        corrected = try_ocr_correction(ref, live_terms)
        if corrected:
            results["ocr_garbled"].append({
                "target": ref,
                "corrected_to": corrected,
                "count": count,
                "referencing_entries": referencing_entries,
            })
            continue

        # 2. Check if it's a truncated reference
        if is_truncated_ref(ref):
            results["truncated_ref"].append({
                "target": ref,
                "count": count,
                "referencing_entries": referencing_entries,
                "reason": "Reference appears truncated by OCR",
            })
            continue

        # 3. Check overlay for suppressed entry
        if ref_upper in overlay_by_term:
            o = overlay_by_term[ref_upper]
            etype = o.get("entry_type", "")
            if etype in suppressed_types:
                results["suppressed_entry"].append({
                    "target": ref,
                    "entry_type": etype,
                    "count": count,
                    "referencing_entries": referencing_entries,
                })
                continue

        # 4. Try without hyphens/spaces (exact after normalization)
        ref_compact = re.sub(r'[\s\-]', '', ref_upper)
        compact_match = None
        for hw in live_terms:
            hw_compact = re.sub(r'[\s\-]', '', hw)
            if ref_compact == hw_compact:
                compact_match = hw
                break

        if compact_match:
            results["variant_match"].append({
                "target": ref,
                "matched_to": compact_match,
                "distance": 0,
                "count": count,
                "referencing_entries": referencing_entries,
                "match_type": "compact_match",
            })
            continue

        # 5. Check if target appears in body text (subentry)
        # Do this BEFORE fuzzy match to avoid false positives
        ref_in_body = False
        for entry in entries:
            body = (entry.get("body", "") or "").upper()
            if ref_upper in body and entry["term"].upper() != ref_upper:
                ref_in_body = True
                break

        if ref_in_body:
            results["subentry_reference"].append({
                "target": ref,
                "count": count,
                "referencing_entries": referencing_entries,
                "reason": "Target appears as subentry in body text",
            })
            continue

        # 6. Fuzzy match against live headwords (last resort)
        # Only for refs >= 8 chars with max distance 1, >= 12 chars with max distance 2
        max_dist = 0
        if len(ref_upper) >= 12:
            max_dist = 2
        elif len(ref_upper) >= 8:
            max_dist = 1

        best_match = None
        best_dist = max_dist + 1
        if max_dist > 0:
            for hw in live_terms:
                if abs(len(hw) - len(ref_upper)) > max_dist:
                    continue
                d = levenshtein(ref_upper, hw)
                if d < best_dist:
                    best_dist = d
                    best_match = hw
                if d == 0:
                    break

        if best_match and best_dist <= max_dist:
            results["variant_match"].append({
                "target": ref,
                "matched_to": best_match,
                "distance": best_dist,
                "count": count,
                "referencing_entries": referencing_entries,
            })
            continue

        # 7. Legitimately absent
        results["legitimately_absent"].append({
            "target": ref,
            "count": count,
            "referencing_entries": referencing_entries,
        })

    # Print summary
    print("\n" + "=" * 60)
    print("CROSS-REFERENCE RESOLUTION RESULTS")
    print("=" * 60)
    total = 0
    for cat, items in results.items():
        n = sum(r["count"] for r in items)
        total += n
        print("  %-25s: %3d unique (%3d refs)" % (cat, len(items), n))
    print("  %-25s: %3d unique (%3d refs)" % ("TOTAL", sum(len(v) for v in results.values()), total))
    print("=" * 60)

    # Write JSON report
    report = {
        "total_unresolved_refs": len(all_refs),
        "unique_missing_targets": len(ref_counter),
        "summary": {cat: len(items) for cat, items in results.items()},
        "details": results,
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("\nSaved: %s" % REPORT_JSON)

    # Write Markdown report
    md = [
        "# Unresolved Cross-Reference Resolution Report",
        "",
        "Analyzed %d unresolved cross-references (%d unique missing targets)." % (len(all_refs), len(ref_counter)),
        "",
        "## Summary",
        "",
        "| Category | Unique Targets | Total Refs | Description |",
        "|----------|---------------|------------|-------------|",
    ]
    descs = {
        "truncated_ref": "OCR truncated reference (false positive)",
        "ocr_garbled": "OCR-garbled target name (correctable)",
        "variant_match": "Target exists under variant spelling",
        "suppressed_entry": "Target is suppressed in overlay",
        "legitimately_absent": "Target genuinely absent from dictionary",
        "subentry_reference": "Target is a subentry within another entry",
    }
    for cat, items in results.items():
        n = sum(r["count"] for r in items)
        md.append("| %s | %d | %d | %s |" % (cat, len(items), n, descs.get(cat, "")))
    md.extend(["", "---", ""])

    # Truncated refs
    if results["truncated_ref"]:
        md.append("## Truncated References (%d)" % len(results["truncated_ref"]))
        md.append("")
        md.append("These are regex false positives where OCR truncated the reference mid-word.")
        md.append("No action needed — these are not real cross-references.")
        md.append("")
        md.append("| Target | Count | Referenced By |")
        md.append("|--------|-------|---------------|")
        for r in results["truncated_ref"]:
            entries_str = ", ".join(r["referencing_entries"][:3])
            if len(r["referencing_entries"]) > 3:
                entries_str += "..."
            md.append("| %s | %d | %s |" % (r["target"], r["count"], entries_str))
        md.extend(["", "---", ""])

    # OCR garbled
    if results["ocr_garbled"]:
        md.append("## OCR-Garbled Targets (%d)" % len(results["ocr_garbled"]))
        md.append("")
        md.append("Target headword name damaged by OCR. Actual target identified.")
        md.append("")
        md.append("| Garbled Target | Corrected To | Count | Referenced By |")
        md.append("|----------------|-------------|-------|---------------|")
        for r in results["ocr_garbled"]:
            entries_str = ", ".join(r["referencing_entries"][:3])
            md.append("| %s | %s | %d | %s |" % (r["target"], r["corrected_to"], r["count"], entries_str))
        md.extend(["", "---", ""])

    # Variant matches
    if results["variant_match"]:
        md.append("## Variant Spelling Matches (%d)" % len(results["variant_match"]))
        md.append("")
        md.append("Target exists under a slightly different spelling.")
        md.append("")
        md.append("| Target | Matched To | Distance | Count |")
        md.append("|--------|-----------|----------|-------|")
        for r in results["variant_match"]:
            md.append("| %s | %s | %d | %d |" % (r["target"], r["matched_to"], r["distance"], r["count"]))
        md.extend(["", "---", ""])

    # Suppressed entries
    if results["suppressed_entry"]:
        md.append("## Suppressed Entries (%d)" % len(results["suppressed_entry"]))
        md.append("")
        md.append("Target exists in overlay but is suppressed (not in live corpus).")
        md.append("")
        md.append("| Target | Entry Type | Count | Referenced By |")
        md.append("|--------|-----------|-------|---------------|")
        for r in results["suppressed_entry"]:
            entries_str = ", ".join(r["referencing_entries"][:3])
            md.append("| %s | %s | %d | %s |" % (r["target"], r["entry_type"], r["count"], entries_str))
        md.extend(["", "---", ""])

    # Subentry references
    if results["subentry_reference"]:
        md.append("## Subentry References (%d)" % len(results["subentry_reference"]))
        md.append("")
        md.append("Target term appears within body text of other entries (not standalone).")
        md.append("")
        md.append("| Target | Count | Referenced By |")
        md.append("|--------|-------|---------------|")
        for r in results["subentry_reference"]:
            entries_str = ", ".join(r["referencing_entries"][:3])
            md.append("| %s | %s | %d | %s |" % (r["target"], r["reason"][:30], r["count"], entries_str))
        md.extend(["", "---", ""])

    # Legitimately absent
    if results["legitimately_absent"]:
        md.append("## Legitimately Absent (%d)" % len(results["legitimately_absent"]))
        md.append("")
        md.append("Target does not exist in the dictionary. These are references to")
        md.append("terms that Black either defined inline, omitted, or that are too")
        md.append("common/obvious to warrant a separate entry.")
        md.append("")
        md.append("| Target | Count | Referenced By |")
        md.append("|--------|-------|---------------|")
        for r in results["legitimately_absent"]:
            entries_str = ", ".join(r["referencing_entries"][:3])
            md.append("| %s | %d | %s |" % (r["target"], r["count"], entries_str))
        md.append("")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("Saved: %s" % REPORT_MD)


if __name__ == "__main__":
    main()
