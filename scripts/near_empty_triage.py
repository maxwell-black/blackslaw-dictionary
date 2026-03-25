#!/usr/bin/env python3
"""
near_empty_triage.py — Triage entries with body < 20 characters.

For each near-empty entry:
  (a) If legitimate short definition or valid cross-ref → reviewed_ok
  (b) If DjVu has longer body → add to body_corrections.json
  (c) If LP has longer definition → stage as LP recovery
  (d) If cross-ref target doesn't exist → flag as unresolved
  (e) If body is clearly truncated → flag for manual review

Writes:
  - rebuild/reports/near_empty_triage.md
  - rebuild/reports/near_empty_triage.json
  - Updates rebuild/overlay/body_corrections.json (for DjVu recoveries)
"""

import json
import re
from pathlib import Path
from collections import Counter

REPO = Path(__file__).resolve().parent.parent
LIVE_CORPUS = REPO / "blacks_entries.json"
SOURCE_CANDIDATES = REPO / "rebuild" / "out" / "source_candidates.jsonl"
SOURCE_PAGES = REPO / "rebuild" / "out" / "source_pages.jsonl"
LP_PATH = REPO / "rebuild" / "external" / "lexpredict" / "blacks_second_edition_terms.json"
BODY_CORRECTIONS = REPO / "rebuild" / "overlay" / "body_corrections.json"
REPORT_JSON = REPO / "rebuild" / "reports" / "near_empty_triage.json"
REPORT_MD = REPO / "rebuild" / "reports" / "near_empty_triage.md"

NEAR_EMPTY_THRESHOLD = 20  # Match corpus_audit.py


def normalize(s):
    """Normalize term for comparison."""
    return re.sub(r'[^A-Z ]', '', s.upper()).strip()


def extract_see_target(body):
    """Extract cross-reference target from 'See XXX' body."""
    body = body.strip()
    # Remove leading garbage
    body = re.sub(r'^[^A-Za-z]*', '', body)
    m = re.match(r'See\s+(.+)', body, re.IGNORECASE)
    if m:
        target = m.group(1).strip()
        # Clean up OCR artifacts in target
        target = re.sub(r'[.,;:\s]+$', '', target)
        target = re.sub(r'\n', ' ', target)
        return target
    return None


def is_see_reference(body):
    """Check if body is a cross-reference starting with 'See'."""
    body = body.strip()
    body = re.sub(r'^[^A-Za-z]*', '', body)
    return body.lower().startswith('see ')


def is_legitimate_short_def(body, term):
    """Check if body is a legitimate short definition."""
    body = body.strip()
    if not body:
        return False
    # Single word/phrase definitions (e.g., "brewer.", "A dairy.", "The pillory.")
    # These are common in legal dictionaries for simple translations
    if re.match(r'^(Lat\.\s+|L\.\s+Fr\.\s+)?[A-Z].*[.)]$', body) and len(body) >= 7:
        return True
    # Definitions with attribution (e.g., "Murder. Cowell.", "A founder, (q. v.)")
    if re.search(r'\b(Cowell|Blount|Jacob|Spelman|Johnson|Du Cange)\b', body):
        return True
    # Short Latin/French translations
    if re.match(r'^(Lat\.|L\. Fr\.)\s+', body):
        return True
    # (q. v.) or (g. v.) references
    if '(q. v.)' in body or '(g. v.)' in body or '(q.v.)' in body:
        return True
    return False


def load_source_candidates():
    """Load source_candidates.jsonl into dict by normalized term."""
    candidates = {}
    if not SOURCE_CANDIDATES.exists():
        return candidates
    with open(SOURCE_CANDIDATES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                term = rec.get("norm_headword") or rec.get("source_headword") or rec.get("term", "")
                norm = normalize(term)
                if norm:
                    if norm not in candidates or len(rec.get("body", "")) > len(candidates[norm].get("body", "")):
                        candidates[norm] = rec
            except json.JSONDecodeError:
                pass
    return candidates


def load_source_pages():
    """Load source_pages.jsonl."""
    pages = []
    if not SOURCE_PAGES.exists():
        return pages
    with open(SOURCE_PAGES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return pages


def search_source_pages(pages, term, source_page_nums):
    """Search source pages for a longer body for this term."""
    if not source_page_nums:
        return None
    target_leaves = set()
    for sp in source_page_nums:
        try:
            target_leaves.add(int(sp))
        except (ValueError, TypeError):
            pass
    if not target_leaves:
        return None

    best_body = None
    best_len = 0

    for page in pages:
        leaf = page.get("leaf", 0)
        if leaf not in target_leaves:
            continue
        text = page.get("text", "")
        if not text:
            lines = page.get("lines", [])
            text = "\n".join(lines)

        # Search for the term in the page text
        norm_term = term.upper()
        text_upper = text.upper()
        idx = text_upper.find(norm_term)
        if idx >= 0:
            # Extract body starting after the term
            body_start = idx + len(norm_term)
            remaining = text[body_start:].strip()
            # Take up to next headword (ALL CAPS line) or end
            lines = remaining.split('\n')
            body_lines = []
            for i, line in enumerate(lines):
                if i > 0 and line.strip() and line.strip() == line.strip().upper() and len(line.strip()) > 3:
                    # Looks like next headword
                    break
                body_lines.append(line)
            body = '\n'.join(body_lines).strip()
            # Clean leading punctuation
            body = re.sub(r'^[.,;:\-—\s]+', '', body).strip()
            if len(body) > best_len:
                best_body = body
                best_len = len(body)

    return best_body if best_len > 20 else None


def load_lp_data():
    """Load LexPredict dataset."""
    if not LP_PATH.exists():
        return {}
    with open(LP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    lp = {}
    terms = data.get("term", {})
    defs = data.get("definition", {})
    for idx in terms:
        term = terms[idx]
        defn = defs.get(idx, "")
        norm = normalize(term)
        if norm and defn:
            if norm not in lp or len(defn) > len(lp[norm]["definition"]):
                lp[norm] = {"term": term, "definition": defn}
    return lp


def main():
    print("Loading live corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"  {len(entries)} entries")

    # Build headword index for cross-ref validation
    headwords = set(e["term"].upper() for e in entries)

    # Find near-empty entries
    near_empty = []
    for e in entries:
        body = (e.get("body") or "").strip()
        if len(body) < NEAR_EMPTY_THRESHOLD:
            near_empty.append(e)
    print(f"  {len(near_empty)} near-empty entries (body < {NEAR_EMPTY_THRESHOLD} chars)")

    # Load sources
    print("Loading source candidates...")
    src_candidates = load_source_candidates()
    print(f"  {len(src_candidates)} source candidates")

    print("Loading source pages...")
    src_pages = load_source_pages()
    print(f"  {len(src_pages)} source pages")

    print("Loading LexPredict data...")
    lp_data = load_lp_data()
    print(f"  {len(lp_data)} LP terms")

    # Load existing body corrections
    if BODY_CORRECTIONS.exists():
        with open(BODY_CORRECTIONS, encoding="utf-8") as f:
            body_corrections = json.load(f)
    else:
        body_corrections = {}
    original_corrections_count = len(body_corrections)

    # Triage each entry
    results = {
        "reviewed_ok": [],          # Legitimate short definition
        "see_ref_valid": [],        # Valid cross-reference
        "see_ref_unresolved": [],   # Cross-ref target not found
        "see_ref_truncated": [],    # Truncated cross-reference
        "djvu_recovered": [],       # Longer body found in DjVu
        "lp_recovered": [],         # Longer body found in LP
        "truncated_body": [],       # Body clearly truncated, no recovery found
        "empty_stub": [],           # Body is essentially empty
    }

    for entry in near_empty:
        term = entry["term"]
        body = (entry.get("body") or "").strip()
        source_pages = entry.get("source_pages", [])
        norm = normalize(term)
        body_len = len(body)

        # Skip if already in body_corrections
        if term in body_corrections:
            results["reviewed_ok"].append({
                "term": term, "body": body, "body_len": body_len,
                "reason": "already in body_corrections",
            })
            continue

        # 1. Check if it's a cross-reference
        if is_see_reference(body):
            target = extract_see_target(body)

            # Check if body is truncated (ends with hyphen or mid-word)
            if body.rstrip().endswith('-') or (target and len(target) < 3):
                # Truncated cross-reference — try to find the full one
                djvu_body = None
                if norm in src_candidates:
                    cand_body = src_candidates[norm].get("body", "")
                    if len(cand_body) > body_len:
                        djvu_body = cand_body

                if not djvu_body:
                    djvu_body = search_source_pages(src_pages, term, source_pages)

                lp_def = lp_data.get(norm, {}).get("definition", "")

                if djvu_body and len(djvu_body) > body_len:
                    body_corrections[term] = {
                        "body": djvu_body,
                        "_source": "djvu_recovery_near_empty"
                    }
                    results["djvu_recovered"].append({
                        "term": term, "old_body": body, "new_body": djvu_body[:100],
                        "new_len": len(djvu_body),
                    })
                elif lp_def and len(lp_def) > body_len:
                    body_corrections[term] = {
                        "body": lp_def,
                        "_source": "lexpredict_cc-by-sa-4.0"
                    }
                    results["lp_recovered"].append({
                        "term": term, "old_body": body, "new_body": lp_def[:100],
                        "new_len": len(lp_def),
                    })
                else:
                    results["see_ref_truncated"].append({
                        "term": term, "body": body, "body_len": body_len,
                    })
                continue

            # Full cross-reference — validate target
            if target:
                # Try to match target against headwords
                target_upper = target.upper()
                # Clean OCR from target
                target_clean = re.sub(r'[^A-Z ,\-]', '', target_upper).strip()

                # Direct match
                if target_clean in headwords:
                    results["see_ref_valid"].append({
                        "term": term, "body": body, "target": target_clean,
                    })
                    continue

                # Try partial match (first word or two)
                first_word = target_clean.split()[0] if target_clean.split() else ""
                partial_matches = [h for h in headwords if h.startswith(first_word) and len(first_word) >= 3]
                if partial_matches:
                    results["see_ref_valid"].append({
                        "term": term, "body": body,
                        "target": target_clean,
                        "matched_to": partial_matches[0],
                    })
                    continue

                # Unresolved
                results["see_ref_unresolved"].append({
                    "term": term, "body": body, "target": target,
                })
            else:
                # Just "See" with nothing
                results["see_ref_truncated"].append({
                    "term": term, "body": body, "body_len": body_len,
                })
            continue

        # 2. Check if it's a legitimate short definition
        if is_legitimate_short_def(body, term):
            results["reviewed_ok"].append({
                "term": term, "body": body, "body_len": body_len,
                "reason": "legitimate short definition",
            })
            continue

        # 3. Check for truncated body (starts mid-word, short fragment)
        is_truncated = False
        if body and body[0].islower():
            is_truncated = True
        elif body_len < 7 and not body.endswith('.'):
            is_truncated = True
        elif body and not body[0].isupper() and not body[0].isdigit():
            is_truncated = True

        # 4. Try DjVu recovery for anything not a valid short def
        djvu_body = None
        if norm in src_candidates:
            cand_body = src_candidates[norm].get("body", "")
            if len(cand_body) > body_len + 10:
                djvu_body = cand_body

        if not djvu_body:
            djvu_body = search_source_pages(src_pages, term, source_pages)

        if djvu_body and len(djvu_body) > body_len + 10:
            body_corrections[term] = {
                "body": djvu_body,
                "_source": "djvu_recovery_near_empty"
            }
            results["djvu_recovered"].append({
                "term": term, "old_body": body, "new_body": djvu_body[:100],
                "new_len": len(djvu_body),
            })
            continue

        # 5. Try LP recovery
        lp_def = lp_data.get(norm, {}).get("definition", "")
        if lp_def and len(lp_def) > body_len + 10:
            body_corrections[term] = {
                "body": lp_def,
                "_source": "lexpredict_cc-by-sa-4.0"
            }
            results["lp_recovered"].append({
                "term": term, "old_body": body, "new_body": lp_def[:100],
                "new_len": len(lp_def),
            })
            continue

        # 6. Classify remainder
        if is_truncated:
            results["truncated_body"].append({
                "term": term, "body": body, "body_len": body_len,
            })
        elif body_len < 5:
            results["empty_stub"].append({
                "term": term, "body": body, "body_len": body_len,
            })
        else:
            # Short but possibly complete
            results["reviewed_ok"].append({
                "term": term, "body": body, "body_len": body_len,
                "reason": "short but complete definition",
            })

    # Print summary
    print(f"\n{'='*60}")
    print("NEAR-EMPTY BODY TRIAGE RESULTS")
    print(f"{'='*60}")
    for cat, items in results.items():
        print(f"  {cat:25s}: {len(items)}")
    print(f"{'='*60}")

    # Save body corrections if we added any
    new_corrections = len(body_corrections) - original_corrections_count
    if new_corrections > 0:
        with open(BODY_CORRECTIONS, "w", encoding="utf-8") as f:
            json.dump(body_corrections, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\nAdded {new_corrections} body corrections -> {BODY_CORRECTIONS}")

    # Write JSON report
    report = {
        "total_near_empty": len(near_empty),
        "threshold": NEAR_EMPTY_THRESHOLD,
        "summary": {cat: len(items) for cat, items in results.items()},
        "new_body_corrections": new_corrections,
        "details": results,
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Saved: {REPORT_JSON}")

    # Write Markdown report
    md = [
        "# Near-Empty Body Triage Report",
        "",
        f"Triaged {len(near_empty)} entries with body < {NEAR_EMPTY_THRESHOLD} characters.",
        "",
        "## Summary",
        "",
        "| Category | Count | Description |",
        "|----------|-------|-------------|",
        f"| Reviewed OK | {len(results['reviewed_ok'])} | Legitimate short definitions |",
        f"| See-ref valid | {len(results['see_ref_valid'])} | Cross-references to live headwords |",
        f"| See-ref unresolved | {len(results['see_ref_unresolved'])} | Cross-ref targets not found |",
        f"| See-ref truncated | {len(results['see_ref_truncated'])} | Truncated cross-references |",
        f"| DjVu recovered | {len(results['djvu_recovered'])} | Longer body found in DjVu source |",
        f"| LP recovered | {len(results['lp_recovered'])} | Longer body from LexPredict |",
        f"| Truncated body | {len(results['truncated_body'])} | Clearly truncated, no recovery |",
        f"| Empty stub | {len(results['empty_stub'])} | Near-empty stub |",
        "",
        "---",
        "",
    ]

    # DjVu recovered
    if results["djvu_recovered"]:
        md.append(f"## DjVu Recovered ({len(results['djvu_recovered'])} entries)")
        md.append("")
        md.append("| Term | Old Body | New Length |")
        md.append("|------|----------|-----------|")
        for r in results["djvu_recovered"]:
            old = r["old_body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {old} | {r['new_len']} chars |")
        md.extend(["", "---", ""])

    # LP recovered
    if results["lp_recovered"]:
        md.append(f"## LP Recovered ({len(results['lp_recovered'])} entries)")
        md.append("")
        md.append("| Term | Old Body | New Length |")
        md.append("|------|----------|-----------|")
        for r in results["lp_recovered"]:
            old = r["old_body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {old} | {r['new_len']} chars |")
        md.extend(["", "---", ""])

    # Unresolved cross-refs
    if results["see_ref_unresolved"]:
        md.append(f"## Unresolved Cross-References ({len(results['see_ref_unresolved'])} entries)")
        md.append("")
        md.append("| Term | Body | Target |")
        md.append("|------|------|--------|")
        for r in results["see_ref_unresolved"]:
            body = r["body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {body} | {r.get('target','')} |")
        md.extend(["", "---", ""])

    # Truncated cross-refs
    if results["see_ref_truncated"]:
        md.append(f"## Truncated Cross-References ({len(results['see_ref_truncated'])} entries)")
        md.append("")
        md.append("| Term | Body |")
        md.append("|------|------|")
        for r in results["see_ref_truncated"]:
            body = r["body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {body} |")
        md.extend(["", "---", ""])

    # Truncated bodies
    if results["truncated_body"]:
        md.append(f"## Truncated Bodies ({len(results['truncated_body'])} entries)")
        md.append("")
        md.append("| Term | Body | Length |")
        md.append("|------|------|--------|")
        for r in results["truncated_body"]:
            body = r["body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {body} | {r['body_len']} |")
        md.extend(["", "---", ""])

    # Empty stubs
    if results["empty_stub"]:
        md.append(f"## Empty Stubs ({len(results['empty_stub'])} entries)")
        md.append("")
        md.append("| Term | Body | Length |")
        md.append("|------|------|--------|")
        for r in results["empty_stub"]:
            body = r["body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {body} | {r['body_len']} |")
        md.extend(["", "---", ""])

    # Valid see-refs (abbreviated)
    if results["see_ref_valid"]:
        md.append(f"## Valid Cross-References ({len(results['see_ref_valid'])} entries)")
        md.append("")
        md.append("| Term | Body | Resolved To |")
        md.append("|------|------|-------------|")
        for r in results["see_ref_valid"][:30]:
            body = r["body"].replace("|", "/").replace("\n", " ")
            target = r.get("matched_to", r.get("target", ""))
            md.append(f"| {r['term']} | {body} | {target} |")
        if len(results["see_ref_valid"]) > 30:
            md.append(f"| ... | ({len(results['see_ref_valid']) - 30} more) | |")
        md.extend(["", "---", ""])

    # Reviewed OK (abbreviated)
    if results["reviewed_ok"]:
        md.append(f"## Reviewed OK ({len(results['reviewed_ok'])} entries)")
        md.append("")
        md.append("| Term | Body | Reason |")
        md.append("|------|------|--------|")
        for r in results["reviewed_ok"][:30]:
            body = r["body"].replace("|", "/").replace("\n", " ")
            md.append(f"| {r['term']} | {body} | {r.get('reason','')} |")
        if len(results["reviewed_ok"]) > 30:
            md.append(f"| ... | ({len(results['reviewed_ok']) - 30} more) | |")
        md.append("")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Saved: {REPORT_MD}")


if __name__ == "__main__":
    main()
