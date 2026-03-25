#!/usr/bin/env python3
"""
djvu_recovery.py — Three-pass recovery of 46 missing entries.

Pass 1: Search source_candidates.jsonl and source_pages.jsonl for DjVu matches
Pass 2: Stage LP definitions for entries not found in DjVu
Pass 3: Apply DjVu recoveries to overlay (new entries or headword corrections)
"""

import json
import re
from pathlib import Path
from collections import defaultdict

REPO = Path(".")
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
GAP_REPORT = REPO / "rebuild" / "reports" / "lexpredict_gap_investigation.json"
SOURCE_CAND = REPO / "rebuild" / "out" / "source_candidates.jsonl"
SOURCE_PAGES = REPO / "rebuild" / "out" / "source_pages.jsonl"
LP_JSON = REPO / "rebuild" / "external" / "lexpredict" / "blacks_second_edition_terms.json"

RECOVERY_JSON = REPO / "rebuild" / "reports" / "djvu_recovery_results.json"
LP_IMPORT = REPO / "rebuild" / "out" / "lp_import_candidates.json"
SUMMARY_MD = REPO / "rebuild" / "reports" / "djvu_recovery_summary.md"


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


def load_source_candidates():
    """Load source_candidates.jsonl into a dict keyed by normalized headword."""
    candidates = {}
    candidates_by_idx = {}
    with open(SOURCE_CAND, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                hw = obj.get("source_headword", "").strip()
                if hw:
                    n = normalize(hw)
                    candidates[n] = obj
                    idx = obj.get("source_index")
                    if idx is not None:
                        candidates_by_idx[idx] = obj
            except json.JSONDecodeError:
                pass
    return candidates, candidates_by_idx


def load_source_pages():
    """Load source_pages.jsonl for text searching."""
    pages = []
    with open(SOURCE_PAGES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                pages.append(obj)
            except json.JSONDecodeError:
                pass
    return pages


def load_lp_data():
    """Load LexPredict terms and definitions."""
    with open(LP_JSON, encoding="utf-8") as f:
        data = json.load(f)
    terms = data["term"]
    defs = data["definition"]
    lp = {}
    for k in terms:
        t = terms[k]
        d = defs[k]
        n = normalize(t)
        lp[n] = {"term": t, "definition": d, "norm": n}
    return lp


def search_source_pages(pages, term_norm):
    """Search source_pages for a term appearing in page text."""
    matches = []
    # Try both the normalized term and variants
    search_terms = [term_norm]
    # Also try without commas for multi-word terms
    if "," in term_norm:
        search_terms.append(term_norm.replace(",", ""))

    for page in pages:
        page_text = " ".join(page.get("lines", [])).upper()
        for st in search_terms:
            if st in page_text:
                # Extract surrounding context
                idx = page_text.find(st)
                start = max(0, idx - 80)
                end = min(len(page_text), idx + len(st) + 120)
                context = page_text[start:end]
                matches.append({
                    "leaf": page.get("leaf"),
                    "printed_page": page.get("printed_page"),
                    "context": context,
                    "search_term": st,
                })
                break  # One match per page is enough
    return matches


def pass1_djvu_recovery(not_found_entries, source_cands, source_pages):
    """Pass 1: Search DjVu data for each of the 46 missing entries."""
    print("=== PASS 1: DjVu Oracle Recovery ===\n")
    results = []
    cand_norms = list(source_cands.keys())

    for entry in not_found_entries:
        term = entry["term"]
        norm = entry["norm"]
        deflen = entry["definition_length"]
        preview = entry["definition_preview"]

        classification = None
        detail = {}

        # (a) Exact match in source_candidates
        if norm in source_cands:
            sc = source_cands[norm]
            classification = "RECOVERED_FROM_DJVU"
            detail = {
                "match_type": "exact",
                "source_index": sc.get("source_index"),
                "source_headword": sc.get("source_headword"),
                "body": sc.get("body", ""),
                "leaves": sc.get("leaves", []),
            }

        # (a) Fuzzy match in source_candidates (Levenshtein <= 3)
        if not classification:
            best_dist = 4
            best_match = None
            for cn in cand_norms:
                if abs(len(cn) - len(norm)) > 3:
                    continue
                d = levenshtein(norm, cn)
                if d < best_dist:
                    best_dist = d
                    best_match = cn
            if best_match:
                sc = source_cands[best_match]
                classification = "RECOVERED_FROM_DJVU"
                detail = {
                    "match_type": f"fuzzy (distance={best_dist})",
                    "source_index": sc.get("source_index"),
                    "source_headword": sc.get("source_headword"),
                    "body": sc.get("body", ""),
                    "leaves": sc.get("leaves", []),
                    "matched_norm": best_match,
                }

        # (b) Search source_pages for term in page text
        if not classification:
            page_matches = search_source_pages(source_pages, norm)
            if page_matches:
                classification = "PARTIAL_DJVU"
                detail = {
                    "page_matches": page_matches[:5],  # Limit to 5 matches
                    "note": "Found in source page text but no clean candidate extraction",
                }

        # For multi-word terms, also try searching for individual significant words
        if not classification and len(norm.split()) > 1:
            # Try the full phrase first, then key words
            words = norm.split()
            # Try combinations
            for combo in [" ".join(words[:3]), " ".join(words[-2:]), " ".join(words[:2])]:
                if len(combo) > 5:
                    page_matches = search_source_pages(source_pages, combo)
                    if page_matches:
                        classification = "PARTIAL_DJVU"
                        detail = {
                            "page_matches": page_matches[:5],
                            "search_variant": combo,
                            "note": f"Found partial match '{combo}' in source page text",
                        }
                        break

        if not classification:
            classification = "NOT_IN_DJVU"
            detail = {"note": "Not found in DjVu source data"}

        result = {
            "rank": entry["rank"],
            "term": term,
            "norm": norm,
            "definition_length": deflen,
            "definition_preview": preview,
            "classification": classification,
            "detail": detail,
        }
        results.append(result)

        status = classification
        extra = ""
        if classification == "RECOVERED_FROM_DJVU":
            extra = f" [{detail['match_type']}, src_idx={detail.get('source_index')}]"
        elif classification == "PARTIAL_DJVU":
            extra = f" [{len(detail.get('page_matches', []))} page hits]"
        print(f"  {entry['rank']:>2}. {term:<45} -> {status}{extra}")

    # Summary
    from collections import Counter
    counts = Counter(r["classification"] for r in results)
    print(f"\n  RECOVERED_FROM_DJVU: {counts.get('RECOVERED_FROM_DJVU', 0)}")
    print(f"  PARTIAL_DJVU:       {counts.get('PARTIAL_DJVU', 0)}")
    print(f"  NOT_IN_DJVU:        {counts.get('NOT_IN_DJVU', 0)}")

    return results


def pass2_lp_import(results, lp_data):
    """Pass 2: Stage LP definitions for NOT_IN_DJVU and PARTIAL_DJVU entries."""
    print("\n=== PASS 2: LP Import Preparation ===\n")
    candidates = []

    for r in results:
        if r["classification"] in ("NOT_IN_DJVU", "PARTIAL_DJVU"):
            norm = r["norm"]
            lp_entry = lp_data.get(norm)
            if lp_entry:
                candidates.append({
                    "term": lp_entry["term"],
                    "body": lp_entry["definition"],
                    "body_source": "lexpredict",
                    "lp_definition_length": len(lp_entry["definition"]),
                    "djvu_classification": r["classification"],
                    "djvu_detail": r["detail"] if r["classification"] == "PARTIAL_DJVU" else None,
                })
                print(f"  Staged: {lp_entry['term']} ({len(lp_entry['definition'])} chars)")
            else:
                # Try fuzzy match in LP data
                lp_norms = list(lp_data.keys())
                best_dist = 4
                best_match = None
                for ln in lp_norms:
                    if abs(len(ln) - len(norm)) > 3:
                        continue
                    d = levenshtein(norm, ln)
                    if d < best_dist:
                        best_dist = d
                        best_match = ln
                if best_match:
                    lp_entry = lp_data[best_match]
                    candidates.append({
                        "term": lp_entry["term"],
                        "body": lp_entry["definition"],
                        "body_source": "lexpredict",
                        "lp_definition_length": len(lp_entry["definition"]),
                        "djvu_classification": r["classification"],
                        "lp_match_type": f"fuzzy (distance={best_dist})",
                    })
                    print(f"  Staged (fuzzy): {lp_entry['term']} ({len(lp_entry['definition'])} chars)")
                else:
                    print(f"  WARN: No LP definition found for {r['term']}")

    with open(LP_IMPORT, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, ensure_ascii=False)
    print(f"\n  Staged {len(candidates)} LP import candidates -> {LP_IMPORT}")

    return candidates


def pass3_apply_djvu(results, overlay, source_cands_by_idx):
    """Pass 3: Apply DjVu recoveries to overlay."""
    print("\n=== PASS 3: Apply DjVu Recoveries ===\n")

    recovered = [r for r in results if r["classification"] == "RECOVERED_FROM_DJVU"]
    if not recovered:
        print("  No RECOVERED_FROM_DJVU entries to apply.")
        return 0

    # Build overlay index by source_index
    overlay_by_src_idx = {}
    for e in overlay:
        si = e.get("source_index")
        if si is not None:
            overlay_by_src_idx[si] = e

    # Build overlay index by normalized term
    overlay_by_norm = defaultdict(list)
    for e in overlay:
        n = normalize(e.get("term", ""))
        if n:
            overlay_by_norm[n].append(e)

    # Find the max BLD2 ID for new entries
    max_id = 0
    for e in overlay:
        eid = e.get("id", "")
        if eid.startswith("BLD2-"):
            try:
                num = int(eid.split("-")[1])
                if num > max_id:
                    max_id = num
            except ValueError:
                pass
    next_id = max_id + 1

    applied = 0
    new_entries = []

    for r in recovered:
        d = r["detail"]
        src_idx = d.get("source_index")
        src_hw = d.get("source_headword", "")
        body = d.get("body", "")
        leaves = d.get("leaves", [])
        term = r["term"]

        # Check if overlay already has this source_index
        existing = overlay_by_src_idx.get(src_idx)
        if existing:
            # Existing entry with this source_index — check if it's garbled
            existing_norm = normalize(existing.get("term", ""))
            target_norm = normalize(term)
            if existing_norm != target_norm:
                # Headword correction needed
                old_term = existing["term"]
                existing["term"] = term
                existing["entry_type"] = "headword_corrected"
                print(f"  CORRECTED: {old_term} -> {term} (source_index={src_idx}, id={existing['id']})")
                applied += 1
            else:
                print(f"  SKIP: {term} already exists at source_index={src_idx} (id={existing['id']})")
            continue

        # Check if overlay already has this term (by normalized match)
        target_norm = normalize(term)
        if target_norm in overlay_by_norm:
            existing_entries = overlay_by_norm[target_norm]
            live = [e for e in existing_entries if e.get("entry_type") not in
                    ("fragment_artifact", "legacy_duplicate", "junk_headword")]
            if live:
                print(f"  SKIP: {term} already exists in overlay (id={live[0]['id']})")
                continue

        # Create new overlay entry
        new_id = f"BLD2-{next_id:05d}"
        next_id += 1
        new_entry = {
            "id": new_id,
            "term": term,
            "body": body,
            "entry_type": "recovered_main",
            "source_index": src_idx,
            "source_pages": leaves,
        }
        new_entries.append(new_entry)
        overlay.append(new_entry)
        print(f"  NEW: {term} -> {new_id} (source_index={src_idx})")
        applied += 1

    if new_entries:
        print(f"\n  Added {len(new_entries)} new entries to overlay")

    return applied


def write_summary(results, lp_candidates, applied_count):
    """Write summary markdown report."""
    from collections import Counter
    counts = Counter(r["classification"] for r in results)

    recovered = [r for r in results if r["classification"] == "RECOVERED_FROM_DJVU"]
    partial = [r for r in results if r["classification"] == "PARTIAL_DJVU"]
    not_in = [r for r in results if r["classification"] == "NOT_IN_DJVU"]

    lines = [
        "# DjVu Recovery Summary",
        "",
        f"46 NOT_FOUND entries from LexPredict gap investigation processed on 2026-03-25.",
        "",
        "## Results",
        "",
        "| Classification | Count | Description |",
        "|---------------|-------|-------------|",
        f"| RECOVERED_FROM_DJVU | {counts.get('RECOVERED_FROM_DJVU', 0)} | Found in DjVu source, recovered to overlay |",
        f"| PARTIAL_DJVU | {counts.get('PARTIAL_DJVU', 0)} | Found in source page text, no clean extraction |",
        f"| NOT_IN_DJVU | {counts.get('NOT_IN_DJVU', 0)} | Not in DjVu source data |",
        "",
        f"- **{applied_count}** entries applied to overlay (new or headword-corrected)",
        f"- **{len(lp_candidates)}** entries staged for LP import review",
        "",
        "---",
        "",
    ]

    if recovered:
        lines.append(f"## RECOVERED_FROM_DJVU ({len(recovered)} entries)")
        lines.append("")
        lines.append("| # | Term | Match Type | Source Index | Source Headword |")
        lines.append("|---|------|-----------|-------------|----------------|")
        for r in recovered:
            d = r["detail"]
            mt = d.get("match_type", "?")
            si = d.get("source_index", "?")
            sh = d.get("source_headword", "?")
            lines.append(f"| {r['rank']} | {r['term']} | {mt} | {si} | {sh} |")
        lines.extend(["", "---", ""])

    if partial:
        lines.append(f"## PARTIAL_DJVU ({len(partial)} entries)")
        lines.append("")
        lines.append("| # | Term | Page Hits | Leaves |")
        lines.append("|---|------|----------|--------|")
        for r in partial:
            d = r["detail"]
            pm = d.get("page_matches", [])
            leaves = ", ".join(str(m.get("leaf", "?")) for m in pm)
            lines.append(f"| {r['rank']} | {r['term']} | {len(pm)} | {leaves} |")
        lines.extend(["", "---", ""])

    if not_in:
        lines.append(f"## NOT_IN_DJVU ({len(not_in)} entries)")
        lines.append("")
        lines.append("These entries are staged for LP import review at `rebuild/out/lp_import_candidates.json`.")
        lines.append("")
        lines.append("| # | Term | Def Len |")
        lines.append("|---|------|---------|")
        for r in not_in:
            lines.append(f"| {r['rank']} | {r['term']} | {r['definition_length']} |")
        lines.append("")

    with open(SUMMARY_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nWrote summary: {SUMMARY_MD}")


def main():
    # Load the 46 NOT_FOUND entries
    print("Loading gap investigation report...")
    gap_report = json.load(open(GAP_REPORT, encoding="utf-8"))
    not_found = [e for e in gap_report["entries"] if e["classification"] == "NOT_FOUND"]
    print(f"  {len(not_found)} NOT_FOUND entries to process")

    # Load DjVu source data
    print("Loading source_candidates.jsonl...")
    source_cands, source_cands_by_idx = load_source_candidates()
    print(f"  {len(source_cands)} source candidates loaded")

    print("Loading source_pages.jsonl...")
    source_pages = load_source_pages()
    print(f"  {len(source_pages)} source pages loaded")

    # Load LP data
    print("Loading LexPredict data...")
    lp_data = load_lp_data()
    print(f"  {len(lp_data)} LP entries loaded")

    # Load overlay
    print("Loading overlay...")
    overlay = json.load(open(OVERLAY_PATH, encoding="utf-8"))
    print(f"  {len(overlay)} overlay entries")

    # Pass 1: DjVu Recovery
    results = pass1_djvu_recovery(not_found, source_cands, source_pages)

    # Save Pass 1 results
    with open(RECOVERY_JSON, "w", encoding="utf-8") as f:
        from collections import Counter
        counts = Counter(r["classification"] for r in results)
        json.dump({"summary": dict(counts), "entries": results}, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {RECOVERY_JSON}")

    # Pass 2: LP Import Preparation
    lp_candidates = pass2_lp_import(results, lp_data)

    # Pass 3: Apply DjVu Recoveries
    applied = pass3_apply_djvu(results, overlay, source_cands_by_idx)

    if applied > 0:
        # Save updated overlay
        with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
            json.dump(overlay, f, indent=2, ensure_ascii=False)
        print(f"\nSaved updated overlay ({len(overlay)} entries)")

    # Write summary
    write_summary(results, lp_candidates, applied)

    print("\n=== DjVu Recovery Complete ===")
    print(f"  Recovered from DjVu: {sum(1 for r in results if r['classification'] == 'RECOVERED_FROM_DJVU')}")
    print(f"  Partial DjVu:        {sum(1 for r in results if r['classification'] == 'PARTIAL_DJVU')}")
    print(f"  Not in DjVu:         {sum(1 for r in results if r['classification'] == 'NOT_IN_DJVU')}")
    print(f"  Applied to overlay:  {applied}")
    print(f"  Staged for LP:       {len(lp_candidates)}")


if __name__ == "__main__":
    main()
