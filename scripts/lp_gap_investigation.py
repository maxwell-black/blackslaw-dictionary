#!/usr/bin/env python3
"""
lp_gap_investigation.py — Cross-reference 71 LP-only entries (def > 500 chars)
against the editorial overlay and DjVu source data.

Classifies each as:
  FOUND_IN_OVERLAY  — term exists in overlay (any entry_type, exact or fuzzy)
  RECOVERABLE_FROM_DJVU — term found in source_candidates.jsonl
  NOT_FOUND — candidate for import/policy decision
  LP_DEBRIS — on inspection, not a real entry
"""

import json
import re
from pathlib import Path
from collections import Counter, defaultdict

REPO = Path(".")
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
COMPARISON_PATH = REPO / "rebuild" / "reports" / "lexpredict_comparison.json"
LIVE_CORPUS = REPO / "blacks_entries.json"
SOURCE_CAND_PATH = REPO / "rebuild" / "out" / "source_candidates.jsonl"
SOURCE_PAGES_PATH = REPO / "rebuild" / "out" / "source_pages.jsonl"
REPORT_DIR = REPO / "rebuild" / "reports"
REPORT_JSON = REPORT_DIR / "lexpredict_gap_investigation.json"
REPORT_MD = REPORT_DIR / "lexpredict_gap_investigation.md"


def normalize(hw):
    hw = hw.strip().upper()
    hw = hw.replace("\u00c6", "AE").replace("\u00e6", "AE")
    hw = hw.replace("\u0152", "OE").replace("\u0153", "OE")
    hw = re.sub(r'[.,;:\-\u2014]+$', '', hw)
    hw = re.sub(r'\s+', ' ', hw).strip()
    return hw


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


def main():
    print("Loading overlay...")
    overlay = json.load(open(OVERLAY_PATH, encoding="utf-8"))
    print(f"  {len(overlay)} overlay entries")

    print("Loading LP comparison report...")
    report = json.load(open(COMPARISON_PATH, encoding="utf-8"))

    print("Loading live corpus...")
    live = json.load(open(LIVE_CORPUS, encoding="utf-8"))
    live_terms = {normalize(e["term"]): e["term"] for e in live}
    print(f"  {len(live_terms)} live terms")

    # Build overlay index: normalized term -> list of entries
    overlay_by_norm = defaultdict(list)
    overlay_norms_unique = set()
    for e in overlay:
        n = normalize(e.get("term", ""))
        if n:
            overlay_by_norm[n].append(e)
            overlay_norms_unique.add(n)
    print(f"  {len(overlay_norms_unique)} unique overlay norms")

    # Load source candidates
    source_cand = {}
    if SOURCE_CAND_PATH.exists():
        with open(SOURCE_CAND_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    hw = obj.get("headword", "").strip()
                    if hw:
                        source_cand[normalize(hw)] = obj
                except json.JSONDecodeError:
                    pass
        print(f"  {len(source_cand)} source candidates loaded")
    else:
        print("  source_candidates.jsonl not found")

    # Get the 71 entries
    gaps = sorted(report["true_lp_only_potential_gaps"], key=lambda x: -x["definition_length"])
    big_gaps = [g for g in gaps if g["definition_length"] > 500]
    print(f"\nProcessing {len(big_gaps)} LP-only entries with def > 500 chars...\n")

    results = []
    for g in big_gaps:
        term = g["term"]
        norm = g["norm"]
        deflen = g["definition_length"]
        preview = g["definition_preview"]

        classification = None
        detail = {}

        # (a) Check overlay — exact match
        if norm in overlay_by_norm:
            matches = overlay_by_norm[norm]
            classification = "FOUND_IN_OVERLAY"
            detail = {
                "match_type": "exact",
                "overlay_entries": [{
                    "id": m["id"],
                    "term": m["term"],
                    "entry_type": m.get("entry_type", "?"),
                    "source_pages": m.get("source_pages", []),
                } for m in matches]
            }

        # (a) Check overlay — fuzzy match (Lev <= 2)
        if not classification:
            best_dist = 3
            best_match_norms = []
            for on in overlay_norms_unique:
                if abs(len(on) - len(norm)) > 2:
                    continue
                d = levenshtein(norm, on)
                if d < best_dist:
                    best_dist = d
                    best_match_norms = [on]
                elif d == best_dist and d <= 2:
                    best_match_norms.append(on)
            if best_dist <= 2 and best_match_norms:
                best_matches = []
                for bmn in best_match_norms[:3]:
                    best_matches.extend(overlay_by_norm[bmn])
                classification = "FOUND_IN_OVERLAY"
                detail = {
                    "match_type": f"fuzzy (distance={best_dist})",
                    "overlay_entries": [{
                        "id": m["id"],
                        "term": m["term"],
                        "entry_type": m.get("entry_type", "?"),
                        "source_pages": m.get("source_pages", []),
                    } for m in best_matches[:5]]
                }

        # Check live corpus exact match
        if not classification and norm in live_terms:
            classification = "FOUND_IN_OVERLAY"
            detail = {"match_type": "live_corpus_exact", "note": f"Found as '{live_terms[norm]}' in live corpus"}

        # (b) Check source candidates — exact
        if not classification and norm in source_cand:
            sc = source_cand[norm]
            classification = "RECOVERABLE_FROM_DJVU"
            detail = {
                "source_candidate": sc.get("headword", ""),
                "source_page": sc.get("leaf", sc.get("page", "")),
                "match_type": "exact",
            }

        # (b) Check source candidates — fuzzy
        if not classification:
            for scn in source_cand:
                if abs(len(scn) - len(norm)) > 2:
                    continue
                d = levenshtein(norm, scn)
                if d <= 2:
                    sc = source_cand[scn]
                    classification = "RECOVERABLE_FROM_DJVU"
                    detail = {
                        "source_candidate": sc.get("headword", ""),
                        "source_page": sc.get("leaf", sc.get("page", "")),
                        "match_type": f"fuzzy (distance={d})",
                    }
                    break

        # Check if term is a subentry within a parent entry in the live corpus
        if not classification:
            # Try to find the term embedded in a parent entry body
            # e.g. "COURT OF EXCHEQUER" might be in the body of "COURT" or "EXCHEQUER"
            words = norm.split()
            parent_candidates = set()
            for w in words:
                if w in live_terms:
                    parent_candidates.add(w)
            # Also check first word, last word
            if words:
                for cand in [words[0], words[-1], " ".join(words[:2])]:
                    if cand in live_terms:
                        parent_candidates.add(cand)

            subentry_in = None
            for pc in parent_candidates:
                parent_hw = live_terms[pc]
                parent_entry = next((e for e in live if e["term"] == parent_hw), None)
                if parent_entry and norm in parent_entry.get("body", "").upper():
                    subentry_in = parent_hw
                    break

            if subentry_in:
                classification = "SUBENTRY_IN_PARENT"
                detail = {
                    "parent_entry": subentry_in,
                    "note": f"Term appears in body of '{subentry_in}' as a subentry or reference"
                }

        # (c) Check for LP debris
        if not classification:
            if re.match(r'^[A-Z]\s+[A-Z]\.\s', term):
                classification = "LP_DEBRIS"
                detail = {"reason": "Garbled term format (letter space letter-dot pattern)"}
            elif re.match(r'^[A-Z]\s+[A-Z]\.\s*$', term):
                classification = "LP_DEBRIS"
                detail = {"reason": "Garbled abbreviation fragment"}
            elif len(term.strip()) <= 2 and not term.strip().isalpha():
                classification = "LP_DEBRIS"
                detail = {"reason": "Very short non-alpha term"}

        if not classification:
            classification = "NOT_FOUND"
            detail = {"note": "Not in overlay or source candidates. Candidate for policy decision."}

        results.append({
            "rank": len(results) + 1,
            "term": term,
            "norm": norm,
            "definition_length": deflen,
            "definition_preview": preview,
            "classification": classification,
            "detail": detail,
        })

    # Summary
    class_counts = Counter(r["classification"] for r in results)
    print("=== Classification Summary ===")
    for cls, cnt in class_counts.most_common():
        print(f"  {cls}: {cnt}")

    # Write JSON
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": dict(class_counts), "entries": results}, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {REPORT_JSON}")

    # Write MD
    md_lines = [
        "# LexPredict Gap Investigation Report",
        "",
        "71 LP-only entries with definitions > 500 chars, cross-referenced against",
        "the editorial overlay (13,641 entries, all types) and DjVu source data.",
        "Fuzzy matching (Levenshtein <= 2) used to account for OCR noise in both corpora.",
        "",
        "## Summary",
        "",
        "| Classification | Count | Description |",
        "|---------------|-------|-------------|",
    ]
    descriptions = {
        "FOUND_IN_OVERLAY": "Already in overlay (may be live, suppressed, or garbled match)",
        "SUBENTRY_IN_PARENT": "Embedded as subentry/reference in a parent entry body",
        "RECOVERABLE_FROM_DJVU": "Found in DjVu source, recoverable with source page",
        "NOT_FOUND": "Not in overlay or DjVu source — candidate for import",
        "LP_DEBRIS": "On inspection, OCR debris in LexPredict data",
    }
    for cls in ["FOUND_IN_OVERLAY", "SUBENTRY_IN_PARENT", "RECOVERABLE_FROM_DJVU", "NOT_FOUND", "LP_DEBRIS"]:
        cnt = class_counts.get(cls, 0)
        md_lines.append(f"| {cls} | {cnt} | {descriptions.get(cls, '')} |")

    md_lines.extend(["", "---", ""])

    # FOUND_IN_OVERLAY section
    found = [r for r in results if r["classification"] == "FOUND_IN_OVERLAY"]
    if found:
        md_lines.append(f"## FOUND_IN_OVERLAY ({len(found)} entries)")
        md_lines.append("")
        md_lines.append("These entries already exist in the overlay. No action needed unless the entry_type")
        md_lines.append("indicates suppression — in which case, review whether the suppression was correct.")
        md_lines.append("")
        md_lines.append("| # | LP Term | Def Len | Match | Overlay ID | Overlay Term | Type |")
        md_lines.append("|---|---------|---------|-------|------------|-------------|------|")
        for r in found:
            d = r["detail"]
            mt = d.get("match_type", "?")
            if "overlay_entries" in d:
                oe = d["overlay_entries"][0]
                oid = oe["id"]
                oterm = oe["term"]
                otype = oe["entry_type"]
            else:
                oid = "—"
                oterm = d.get("note", "—")
                otype = "—"
            md_lines.append(f"| {r['rank']} | {r['term']} | {r['definition_length']} | {mt} | {oid} | {oterm} | {otype} |")

    md_lines.extend(["", "---", ""])

    # SUBENTRY_IN_PARENT section
    subentries = [r for r in results if r["classification"] == "SUBENTRY_IN_PARENT"]
    if subentries:
        md_lines.append(f"## SUBENTRY_IN_PARENT ({len(subentries)} entries)")
        md_lines.append("")
        md_lines.append("These terms appear in the body of a parent entry as subentries or references.")
        md_lines.append("They exist in our corpus but not as standalone headwords — LexPredict split them")
        md_lines.append("into separate entries. No action needed unless we want to promote them to standalone.")
        md_lines.append("")
        md_lines.append("| # | LP Term | Def Len | Parent Entry |")
        md_lines.append("|---|---------|---------|-------------|")
        for r in subentries:
            d = r["detail"]
            parent = d.get("parent_entry", "?")
            md_lines.append(f"| {r['rank']} | {r['term']} | {r['definition_length']} | {parent} |")

    md_lines.extend(["", "---", ""])

    # RECOVERABLE_FROM_DJVU section
    recoverable = [r for r in results if r["classification"] == "RECOVERABLE_FROM_DJVU"]
    if recoverable:
        md_lines.append(f"## RECOVERABLE_FROM_DJVU ({len(recoverable)} entries)")
        md_lines.append("")
        md_lines.append("These entries exist in the DjVu source scan but are not in the overlay.")
        md_lines.append("They could be recovered by adding them to the overlay pipeline.")
        md_lines.append("")
        md_lines.append("| # | LP Term | Def Len | Source Page | Match |")
        md_lines.append("|---|---------|---------|------------|-------|")
        for r in recoverable:
            d = r["detail"]
            sp = d.get("source_page", "?")
            mt = d.get("match_type", "exact")
            md_lines.append(f"| {r['rank']} | {r['term']} | {r['definition_length']} | {sp} | {mt} |")

    md_lines.extend(["", "---", ""])

    # NOT_FOUND section
    not_found = [r for r in results if r["classification"] == "NOT_FOUND"]
    if not_found:
        md_lines.append(f"## NOT_FOUND ({len(not_found)} entries)")
        md_lines.append("")
        md_lines.append("These entries are in LexPredict but not in our overlay or DjVu source.")
        md_lines.append("They are candidates for import, but each needs policy review:")
        md_lines.append("- Is it a real dictionary entry or LexPredict OCR artifact?")
        md_lines.append("- If real, should it be added to the overlay as a new entry?")
        md_lines.append("")
        md_lines.append("| # | LP Term | Def Len | Definition Preview |")
        md_lines.append("|---|---------|---------|-------------------|")
        for r in not_found:
            preview = r["definition_preview"].replace("|", "/").replace("\n", " ")[:100]
            md_lines.append(f"| {r['rank']} | {r['term']} | {r['definition_length']} | {preview} |")

    md_lines.extend(["", "---", ""])

    # LP_DEBRIS section
    debris = [r for r in results if r["classification"] == "LP_DEBRIS"]
    if debris:
        md_lines.append(f"## LP_DEBRIS ({len(debris)} entries)")
        md_lines.append("")
        md_lines.append("These are OCR artifacts in the LexPredict dataset, not real entries.")
        md_lines.append("")
        md_lines.append("| # | LP Term | Def Len | Reason |")
        md_lines.append("|---|---------|---------|--------|")
        for r in debris:
            reason = r["detail"].get("reason", "?")
            md_lines.append(f"| {r['rank']} | {r['term']} | {r['definition_length']} | {reason} |")

    md_lines.append("")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Wrote: {REPORT_MD}")


if __name__ == "__main__":
    main()
