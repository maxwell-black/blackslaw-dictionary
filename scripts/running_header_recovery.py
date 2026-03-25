#!/usr/bin/env python3
"""
running_header_recovery.py — Recover 23 genuine gaps from running header analysis.

For each gap:
  (a) Search source_pages.jsonl on/near expected leaf for definition text
  (b) Search source_candidates.jsonl (exact + fuzzy Lev ≤ 3)
  (c) Check LexPredict dataset
  (d) Check overlay for garbled headword matches (body similarity)

Classify as: RECOVERED_FROM_DJVU, RECOVERED_FROM_LP, ALREADY_IN_OVERLAY, NOT_RECOVERABLE
"""

import json
import re
from pathlib import Path
from collections import defaultdict

REPO = Path(".")
EXTRACTION_JSON = REPO / "rebuild" / "reports" / "running_header_extraction.json"
SOURCE_CAND = REPO / "rebuild" / "out" / "source_candidates.jsonl"
SOURCE_PAGES = REPO / "rebuild" / "out" / "source_pages.jsonl"
LP_JSON = REPO / "rebuild" / "external" / "lexpredict" / "blacks_second_edition_terms.json"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
BODY_CORR_PATH = REPO / "rebuild" / "overlay" / "body_corrections.json"
LIVE_CORPUS = REPO / "blacks_entries.json"
REPORT_MD = REPO / "rebuild" / "reports" / "running_header_recovery.md"
REPORT_JSON = REPO / "rebuild" / "reports" / "running_header_recovery.json"

# OCR corrections for garbled running headers
HEADER_OCR_FIXES = {
    "DE ARTE. ET PARTE": "DE ARTE ET PARTE",
    "DE COMBUSTIONE DOMORUM. OF": "DE COMBUSTIONE DOMORUM",
    "DH-FIDE ET OFFICIO JUDICIS": "DE FIDE ET OFFICIO JUDICIS",
    "DF SUPERONERATIONE PASTURZ": "DE SUPERONERATIONE PASTURAE",
    "EIN VERBIS, NON VERBA": "IN VERBIS, NON VERBA",
    "SUSPICIOUS CHARACTER. IN THE": "SUSPICIOUS CHARACTER",
}


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


def normalize(hw):
    hw = hw.strip().upper()
    hw = hw.replace("\u00c6", "AE").replace("\u00e6", "AE")
    hw = hw.replace("\u0152", "OE").replace("\u0153", "OE")
    hw = re.sub(r'[.,;:\-\u2014]+$', '', hw)
    hw = re.sub(r'\s+', ' ', hw).strip()
    return hw


def load_source_candidates():
    candidates = {}
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
            except json.JSONDecodeError:
                pass
    return candidates


def load_source_pages():
    pages = {}
    with open(SOURCE_PAGES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                pages[obj.get("leaf", -1)] = obj
            except json.JSONDecodeError:
                pass
    return pages


def load_lp_data():
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


def search_source_pages_near(pages, term, expected_leaf, window=5):
    """Search source pages near expected leaf for term text."""
    results = []
    for offset in range(-window, window + 1):
        leaf = expected_leaf + offset
        page = pages.get(leaf)
        if not page:
            continue
        text = " ".join(page.get("lines", [])).upper()
        if term.upper() in text:
            idx = text.find(term.upper())
            start = max(0, idx - 40)
            end = min(len(text), idx + len(term) + 200)
            context = text[start:end]
            results.append({
                "leaf": leaf,
                "printed_page": page.get("printed_page"),
                "context": context,
            })
    return results


def search_candidates_fuzzy(candidates, term, max_dist=3):
    """Search source_candidates for exact or fuzzy match."""
    norm = normalize(term)

    # Exact
    if norm in candidates:
        return candidates[norm], "exact", 0

    # Fuzzy
    best_dist = max_dist + 1
    best_match = None
    for cn in candidates:
        if abs(len(cn) - len(norm)) > max_dist:
            continue
        d = levenshtein(norm, cn)
        if d < best_dist:
            best_dist = d
            best_match = cn
    if best_match:
        return candidates[best_match], f"fuzzy(dist={best_dist})", best_dist
    return None, None, None


def search_overlay_by_body(overlay, term, leaf, live_entries):
    """Search overlay for entries near the expected leaf with similar content."""
    norm = normalize(term)
    # Look for overlay entries whose source_pages overlap with expected leaf
    nearby = []
    for e in overlay:
        sp = e.get("source_pages", [])
        if sp and any(abs(int(p) - leaf) <= 3 for p in sp if str(p).isdigit()):
            nearby.append(e)

    # Check if any nearby entry might be this term under a garbled headword
    for e in nearby:
        etype = e.get("entry_type", "")
        # If it's suppressed or garbled, it might be our entry
        if etype in ("legacy_unresolved", "fragment_artifact", "junk_headword"):
            body = (e.get("body") or "").upper()
            # Check if the body mentions our search term
            search_words = [w for w in norm.split() if len(w) > 3]
            if search_words and all(w in body for w in search_words[:2]):
                return e
    return None


def main():
    print("Loading data...")
    extraction = json.load(open(EXTRACTION_JSON, encoding="utf-8"))
    gaps = [c for c in extraction["classified"] if c["classification"] == "GENUINE_GAP"]
    print(f"  {len(gaps)} genuine gaps")

    candidates = load_source_candidates()
    print(f"  {len(candidates)} source candidates")

    pages = load_source_pages()
    print(f"  {len(pages)} source pages")

    lp_data = load_lp_data()
    print(f"  {len(lp_data)} LP entries")

    overlay = json.load(open(OVERLAY_PATH, encoding="utf-8"))
    print(f"  {len(overlay)} overlay entries")

    live = json.load(open(LIVE_CORPUS, encoding="utf-8"))
    print(f"  {len(live)} live entries")

    body_corrections = json.load(open(BODY_CORR_PATH, encoding="utf-8"))

    # Process each gap
    print(f"\n=== Processing {len(gaps)} gaps ===\n")
    results = []

    for g in gaps:
        raw_term = g["header_term"]
        leaf = g["leaf"]
        corrected = HEADER_OCR_FIXES.get(raw_term, raw_term)
        norm = normalize(corrected)

        classification = None
        detail = {}

        # (a) Search source_pages near expected leaf
        page_hits = search_source_pages_near(pages, corrected, leaf)

        # (b) Search source_candidates (exact + fuzzy)
        cand, match_type, dist = search_candidates_fuzzy(candidates, corrected)

        if cand:
            classification = "RECOVERED_FROM_DJVU"
            detail = {
                "match_type": match_type,
                "source_index": cand.get("source_index"),
                "source_headword": cand.get("source_headword"),
                "body": cand.get("body", ""),
                "leaves": cand.get("leaves", []),
            }
        else:
            # Try with words from the term
            words = corrected.split()
            if len(words) >= 2:
                # Try "COURT OF THE CORONER" variants
                for variant in [corrected, " ".join(words)]:
                    c2, mt2, d2 = search_candidates_fuzzy(candidates, variant)
                    if c2:
                        classification = "RECOVERED_FROM_DJVU"
                        detail = {
                            "match_type": mt2,
                            "source_index": c2.get("source_index"),
                            "source_headword": c2.get("source_headword"),
                            "body": c2.get("body", ""),
                            "leaves": c2.get("leaves", []),
                        }
                        break

        # (c) Check LP dataset
        if not classification:
            lp_norm = normalize(corrected)
            lp_entry = lp_data.get(lp_norm)
            if not lp_entry:
                # Fuzzy LP search
                best_dist = 4
                best_lp = None
                for ln in lp_data:
                    if abs(len(ln) - len(lp_norm)) > 3:
                        continue
                    d = levenshtein(lp_norm, ln)
                    if d < best_dist:
                        best_dist = d
                        best_lp = ln
                if best_lp:
                    lp_entry = lp_data[best_lp]

            if lp_entry:
                classification = "RECOVERED_FROM_LP"
                detail = {
                    "lp_term": lp_entry["term"],
                    "lp_definition": lp_entry["definition"],
                    "lp_def_length": len(lp_entry["definition"]),
                }

        # (d) Check overlay for garbled headword matches
        if not classification:
            overlay_match = search_overlay_by_body(overlay, corrected, leaf, live)
            if overlay_match:
                classification = "ALREADY_IN_OVERLAY"
                detail = {
                    "overlay_id": overlay_match.get("id"),
                    "overlay_term": overlay_match.get("term"),
                    "overlay_type": overlay_match.get("entry_type"),
                }

        # Use page_hits as supporting evidence
        if not classification and page_hits:
            # We found it in the page text but couldn't extract a clean entry
            classification = "PARTIAL_DJVU"
            detail = {
                "page_hits": page_hits[:3],
                "note": "Found in page text but no clean headword/body extraction",
            }

        if not classification:
            classification = "NOT_RECOVERABLE"
            detail = {"note": "Not found in DjVu, LP, or overlay"}

        result = {
            "raw_term": raw_term,
            "corrected_term": corrected,
            "leaf": leaf,
            "classification": classification,
            "detail": detail,
            "page_hits": len(page_hits),
        }
        results.append(result)

        extra = ""
        if classification == "RECOVERED_FROM_DJVU":
            extra = f" [{detail['match_type']}, src={detail.get('source_headword','')}]"
        elif classification == "RECOVERED_FROM_LP":
            extra = f" [LP: {detail['lp_term']}, {detail['lp_def_length']} chars]"
        elif classification == "ALREADY_IN_OVERLAY":
            extra = f" [{detail['overlay_id']}: {detail['overlay_term']}]"
        elif classification == "PARTIAL_DJVU":
            extra = f" [{len(page_hits)} page hits]"

        ocr_note = f" (corrected from '{raw_term}')" if corrected != raw_term else ""
        print(f"  {leaf:4d} {corrected:42s} -> {classification}{extra}{ocr_note}")

    # Summary
    from collections import Counter
    counts = Counter(r["classification"] for r in results)
    print(f"\n=== Summary ===")
    for cls in ["RECOVERED_FROM_DJVU", "RECOVERED_FROM_LP", "ALREADY_IN_OVERLAY", "PARTIAL_DJVU", "NOT_RECOVERABLE"]:
        print(f"  {cls}: {counts.get(cls, 0)}")

    # Save results
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump({"summary": dict(counts), "results": results}, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {REPORT_JSON}")

    # Apply recoveries
    recovered_djvu = [r for r in results if r["classification"] == "RECOVERED_FROM_DJVU"]
    recovered_lp = [r for r in results if r["classification"] == "RECOVERED_FROM_LP"]

    # Find max ID
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

    # Check for duplicates before adding
    overlay_terms_upper = {e["term"].upper() for e in overlay}
    applied = 0

    if recovered_djvu:
        print(f"\n=== Applying {len(recovered_djvu)} DjVu recoveries ===")
        for r in recovered_djvu:
            term = r["corrected_term"]
            if term.upper() in overlay_terms_upper:
                print(f"  SKIP (already in overlay): {term}")
                continue
            d = r["detail"]
            new_id = f"BLD2-{next_id:05d}"
            next_id += 1
            new_entry = {
                "id": new_id,
                "term": term,
                "body": d.get("body", ""),
                "entry_type": "recovered_main",
                "source_index": d.get("source_index"),
                "source_pages": d.get("leaves", []),
            }
            overlay.append(new_entry)
            overlay_terms_upper.add(term.upper())
            print(f"  NEW: {new_id} {term}")
            applied += 1

    if recovered_lp:
        print(f"\n=== Applying {len(recovered_lp)} LP recoveries ===")
        for r in recovered_lp:
            term = r["corrected_term"]
            if term.upper() in overlay_terms_upper:
                print(f"  SKIP (already in overlay): {term}")
                continue
            d = r["detail"]
            new_id = f"BLD2-{next_id:05d}"
            next_id += 1
            new_entry = {
                "id": new_id,
                "term": term,
                "body": "",
                "entry_type": "recovered_main",
                "source_pages": [],
            }
            overlay.append(new_entry)
            overlay_terms_upper.add(term.upper())

            # Add body correction
            body_corrections[term] = {
                "source_leaf": None,
                "reason": f"Imported from LexPredict (CC-BY-SA 4.0). Original LP headword: {d['lp_term']}",
                "_source": "lexpredict_cc-by-sa-4.0",
                "body": d["lp_definition"],
            }
            print(f"  NEW: {new_id} {term} (LP: {d['lp_term']}, {d['lp_def_length']} chars)")
            applied += 1

    if applied > 0:
        with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
            json.dump(overlay, f, indent=2, ensure_ascii=False)
        print(f"\nSaved overlay: {len(overlay)} entries")

        with open(BODY_CORR_PATH, "w", encoding="utf-8") as f:
            json.dump(body_corrections, f, indent=2, ensure_ascii=False)
        print(f"Saved body corrections")

    # Write markdown report
    md = [
        "# Running Header Gap Recovery",
        "",
        f"Attempted recovery of {len(gaps)} genuine gaps from running header analysis.",
        "",
        "## Summary",
        "",
        "| Classification | Count | Description |",
        "|---------------|-------|-------------|",
        f"| RECOVERED_FROM_DJVU | {counts.get('RECOVERED_FROM_DJVU', 0)} | Found in DjVu source candidates |",
        f"| RECOVERED_FROM_LP | {counts.get('RECOVERED_FROM_LP', 0)} | Found in LexPredict dataset |",
        f"| ALREADY_IN_OVERLAY | {counts.get('ALREADY_IN_OVERLAY', 0)} | Already in overlay under garbled headword |",
        f"| PARTIAL_DJVU | {counts.get('PARTIAL_DJVU', 0)} | In page text but no clean extraction |",
        f"| NOT_RECOVERABLE | {counts.get('NOT_RECOVERABLE', 0)} | Not found in any source |",
        "",
        f"**{applied}** entries applied to overlay.",
        "",
        "---",
        "",
    ]

    for cls, title in [
        ("RECOVERED_FROM_DJVU", "Recovered from DjVu"),
        ("RECOVERED_FROM_LP", "Recovered from LexPredict"),
        ("ALREADY_IN_OVERLAY", "Already in Overlay"),
        ("PARTIAL_DJVU", "Partial DjVu Match"),
        ("NOT_RECOVERABLE", "Not Recoverable"),
    ]:
        entries = [r for r in results if r["classification"] == cls]
        if not entries:
            continue
        md.append(f"## {title} ({len(entries)} entries)")
        md.append("")
        md.append("| Leaf | Term | Detail |")
        md.append("|------|------|--------|")
        for r in entries:
            term = r["corrected_term"]
            d = r["detail"]
            if cls == "RECOVERED_FROM_DJVU":
                info = f"{d.get('match_type', '?')}, src_hw={d.get('source_headword', '?')}"
            elif cls == "RECOVERED_FROM_LP":
                info = f"LP: {d.get('lp_term', '?')}, {d.get('lp_def_length', '?')} chars"
            elif cls == "ALREADY_IN_OVERLAY":
                info = f"{d.get('overlay_id', '?')}: {d.get('overlay_term', '?')} ({d.get('overlay_type', '?')})"
            elif cls == "PARTIAL_DJVU":
                info = f"{r.get('page_hits', 0)} page hits"
            else:
                info = d.get("note", "?")
            if r["raw_term"] != term:
                term = f"{term} (was: {r['raw_term']})"
            md.append(f"| {r['leaf']} | {term} | {info} |")
        md.extend(["", "---", ""])

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Wrote: {REPORT_MD}")

    print(f"\n=== Recovery Complete: {applied} entries applied ===")


if __name__ == "__main__":
    main()
