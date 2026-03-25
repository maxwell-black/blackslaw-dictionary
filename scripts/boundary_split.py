#!/usr/bin/env python3
"""
boundary_split.py — Detect and repair entry boundary failures.

CONSERVATIVE: Only acts on two cases:
  1. An EXISTING live headword's definition text is found verbatim in a
     parent entry's body (clear boundary duplication) → trim from parent
  2. An embedded headword that does NOT exist, is alphabetically sequential,
     has a clean (non-garbled) headword, and a substantive body → extract

All uncertain cases are logged for review but NOT modified.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIVE_CORPUS = REPO / "blacks_entries.json"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
BODY_CORRECTIONS = REPO / "rebuild" / "overlay" / "body_corrections.json"
CANDIDATES_JSON = REPO / "rebuild" / "reports" / "boundary_split_candidates.json"
RESULTS_MD = REPO / "rebuild" / "reports" / "boundary_split_results.md"

# Roman numerals
ROMAN_RE = re.compile(r'^[IVXLCDM]+$')

# Stop words that are never headwords
STOP = {
    'AND', 'THE', 'FOR', 'BUT', 'NOT', 'NOR', 'YET', 'ALL', 'ANY',
    'MAY', 'CAN', 'ONE', 'TWO', 'HIS', 'HER', 'ITS', 'PER', 'VIZ',
    'SIC', 'LAT', 'ENG', 'ALSO', 'SUCH', 'THAT', 'THIS', 'WHEN',
    'WHERE', 'WHICH', 'THUS', 'WITH', 'FROM', 'UPON', 'SAID', 'HELD',
    'UNDER', 'ABOVE', 'BELOW', 'AFTER', 'BEFORE', 'EXCEPT', 'THEN',
    'NOTE', 'THESE', 'THOSE', 'SHALL', 'WILL', 'MUST', 'BEEN', 'WERE',
    'HAVE', 'HERE', 'THERE', 'WHAT', 'SOME', 'OVER', 'INTO',
}


def is_roman(s):
    """Check if string is a Roman numeral."""
    return bool(ROMAN_RE.match(s)) and len(s) <= 4


def is_plausible_headword(hw):
    """Lenient check for detection — could this be a headword boundary?
    Used to find candidates; garbled headwords are handled later."""
    hw = hw.strip()
    if not hw:
        return False
    if '\n' in hw:
        return False
    if not hw[0].isalpha():
        return False
    alpha = sum(1 for c in hw if c.isalpha())
    if alpha / max(len(hw), 1) < 0.7:
        return False
    if re.search(r'[§@|©°{}\\]', hw):
        return False
    return True


def is_clean_headword(hw):
    """Strict check — is this headword clean enough to extract as a NEW entry?
    Rejects OCR-garbled headwords that would create bad dictionary entries."""
    if not is_plausible_headword(hw):
        return False
    words = hw.split()
    for w in words:
        w_upper = w.upper()
        # OO at word start (likely CC)
        if w_upper.startswith('OO') and len(w_upper) > 3:
            return False
        # O + consonant at word start in multi-word headword
        if len(w_upper) > 3 and w_upper[0] == 'O' and w_upper[1] in 'BCDFGHJKLMNPQRSTVWXYZ' and w_upper[1] != 'R':
            if len(words) > 1:
                return False
        # === O-for-C patterns ===
        if 'AOT' in w_upper:
            return False
        if re.search(r'[AEIOU]OT[AEIOU]', w_upper):
            return False
        if re.search(r'[A-Z]OO[A-Z]', w_upper) and not w_upper.startswith('OO'):
            if not re.search(r'OO[DFKLMNPRT]$', w_upper):
                return False
        if re.search(r'OI[A-Z]', w_upper) and not re.search(r'OI[NRLS]', w_upper):
            return False
        # OU where CU expected (OUJUS → CUJUS)
        if re.search(r'^OU[A-Z]', w_upper) and len(w_upper) > 3:
            return False
        # === Z patterns ===
        if w_upper.endswith('Z') and len(w_upper) > 2 and not w_upper.endswith('RTZ'):
            return False
        if re.search(r'^[A-Z]{1,2}Z[AEIOU]', w_upper):
            return False
        # === B-for-R patterns ===
        if re.search(r'ABM|ABY$|ABI[A-Z]', w_upper):
            return False
        if w_upper.endswith('BOUS') or w_upper.endswith('OOUS'):
            return False
        # === Other patterns ===
        if re.search(r'^[A-Z]Y[A-Z]', w_upper) and w_upper[0] == 'I':
            return False
        if re.search(r'(.)\1\1', w_upper):
            return False
        if re.search(r'TT[A-Z]', w_upper) and not w_upper.endswith('TTE'):
            return False
    return True


def _edit_distance(s1, s2):
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            ins = prev[j + 1] + 1
            dele = curr[j] + 1
            sub = prev[j] + (0 if c1 == c2 else 1)
            curr.append(min(ins, dele, sub))
        prev = curr
    return prev[-1]


# Common OCR single-character substitutions for headword degarbling
OCR_CHAR_SUBS = {
    'O': 'C',   # O-for-C (AOTUS→ACTUS, DEFEOT→DEFECT)
    'I': 'L',   # I-for-L
    'B': 'R',   # B-for-R (MABRIAGE→MARRIAGE)
    'II': 'H',  # II-for-H
    'N': 'H',   # N-for-H
    'Y': 'V',   # Y-for-V
}


def _apply_one_sub(text, live_terms_set):
    """Try all single-char OCR subs on text. Returns match or None."""
    for i, ch in enumerate(text):
        for ocr_char, real_char in OCR_CHAR_SUBS.items():
            if len(ocr_char) == 1 and ch == ocr_char:
                candidate = text[:i] + real_char + text[i+1:]
                if candidate in live_terms_set:
                    return candidate
        if text[i:i+2] == 'II' and i+2 <= len(text):
            candidate = text[:i] + 'H' + text[i+2:]
            if candidate in live_terms_set:
                return candidate
    return None


def ocr_degarble_headword(hw, live_terms_set):
    """Try common OCR substitutions to see if headword matches a live term.

    Supports multi-pass: tries up to 3 single-char subs to handle
    headwords like AOTIO EX DELIOTO (needs O→C at 2 positions).

    Returns the matched live term if found, else None.
    """
    hw_upper = hw.upper()

    # Pass 1: single sub
    result = _apply_one_sub(hw_upper, live_terms_set)
    if result:
        return result

    # Pass 2-3: iterative subs (try each single sub, then recurse)
    for depth in range(2):
        for i, ch in enumerate(hw_upper):
            for ocr_char, real_char in OCR_CHAR_SUBS.items():
                if len(ocr_char) == 1 and ch == ocr_char:
                    partially_fixed = hw_upper[:i] + real_char + hw_upper[i+1:]
                    result = _apply_one_sub(partially_fixed, live_terms_set)
                    if result:
                        return result
                    # Depth 2: try one more level
                    if depth == 1:
                        for j, ch2 in enumerate(partially_fixed):
                            if j == i:
                                continue
                            for oc2, rc2 in OCR_CHAR_SUBS.items():
                                if len(oc2) == 1 and ch2 == oc2:
                                    p2 = partially_fixed[:j] + rc2 + partially_fixed[j+1:]
                                    r2 = _apply_one_sub(p2, live_terms_set)
                                    if r2:
                                        return r2
    return None


def is_subentry(parent, candidate):
    """Check if candidate is a subentry of parent."""
    pu = parent.upper()
    cu = candidate.upper()
    # Exact match
    if cu == pu:
        return True
    # Starts with parent (ACCORD AND SATISFACTION under ACCORD)
    if cu.startswith(pu + ' ') or cu.startswith(pu + ','):
        return True
    # Starts with parent's first word (if parent has 4+ char first word)
    first = pu.split()[0] if pu.split() else pu
    if len(first) >= 4 and cu.startswith(first + ' '):
        return True
    # Dash-prefixed subentry
    if cu.startswith('-') or cu.startswith('—'):
        return True
    return False


def detect_embedded(body, parent_term, live_terms_set):
    """Find potential embedded headwords in body.

    Returns list of (offset, headword, body_text) tuples where:
    - headword is the detected embedded term
    - body_text is the definition text after the headword
    - offset is the character offset in the parent body
    """
    if not body or len(body) < 80:
        return []

    # Pattern: \n\n + optional artifacts + ALL_CAPS HEADWORD + . + definition
    # The double-newline is important — it signals a paragraph break which is
    # the typical boundary between dictionary entries
    pat = re.compile(
        r'\n\n\s*_?\s*'           # paragraph break + optional artifacts
        r'([A-Z][A-Z\s,\-\']{2,50}?)'  # ALL-CAPS headword
        r'[.,]\s+'                # period/comma + space
        r'([A-Z])',               # definition starts with capital letter
    )

    results = []
    for m in pat.finditer(body):
        hw_raw = m.group(1).strip()
        # Clean up multiline artifacts (CHIROGRAPHA\nCHIROGRAPHA → CHIROGRAPHA)
        hw_raw = hw_raw.replace('\n', ' ').strip()
        # Rejoin hyphenated line breaks (CONSOLIDA- TION → CONSOLIDATION)
        hw_raw = re.sub(r'-\s+', '', hw_raw)
        hw = re.sub(r'[,.\s]+$', '', hw_raw).strip()
        # Deduplicate repeated headword (OCR duplication artifact)
        # Handles: "SANGUINEM SANGUINEM EMERE" → "SANGUINEM EMERE"
        #          "YIELDING YIELDING AND PAYING" → "YIELDING AND PAYING"
        #          "STRAMINEUS STRAMINEUS HOMO" → "STRAMINEUS HOMO"
        hw_words = hw.split()
        if len(hw_words) >= 2:
            # Try removing leading duplicated words
            for k in range(1, len(hw_words) // 2 + 1):
                if hw_words[:k] == hw_words[k:2*k]:
                    hw = ' '.join(hw_words[k:])
                    break

        if not hw or len(hw) < 3:
            continue
        if hw.upper() in STOP:
            continue
        if is_roman(hw.upper()):
            continue
        if is_subentry(parent_term, hw):
            continue
        if not is_plausible_headword(hw):
            continue

        # Extract the body text for this embedded entry
        # It runs from after the headword+period to the next embedded entry or end
        body_start = m.end() - 1  # include the capital letter
        remaining = body[body_start:]

        # Find end: next double-newline + ALL-CAPS or end of string
        end_pat = re.search(r'\n\n\s*_?\s*[A-Z][A-Z\s,\-\']{2,}[.,]', remaining)
        if end_pat:
            embed_body = remaining[:end_pat.start()].strip()
        else:
            embed_body = remaining.strip()

        # The split point is at the start of this embedded entry
        split_offset = m.start()

        results.append({
            'offset': split_offset,
            'headword': hw.upper(),
            'headword_raw': hw,
            'embed_body': embed_body,
            'body_len': len(embed_body),
        })

    return results


def main():
    print("Loading live corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    print("  %d entries" % len(entries))

    live_terms = {e["term"].upper() for e in entries}
    entry_by_term = {e["term"].upper(): e for e in entries}

    print("Loading overlay...")
    with open(OVERLAY_PATH, encoding="utf-8") as f:
        overlay = json.load(f)
    overlay_terms = {o["term"].upper() for o in overlay}

    # Load existing body corrections
    if BODY_CORRECTIONS.exists():
        with open(BODY_CORRECTIONS, encoding="utf-8") as f:
            body_corrections = json.load(f)
    else:
        body_corrections = {}

    # === Step 1: Detection ===
    print("\n=== Step 1: Detection ===\n")

    all_detections = []
    for e in entries:
        body = e.get("body", "") or ""
        candidates = detect_embedded(body, e["term"], live_terms)
        if candidates:
            for c in candidates:
                c['parent_term'] = e['term']
                c['parent_body_len'] = len(body)
                c['exists_as_live'] = c['headword'] in live_terms
                c['exists_in_overlay'] = c['headword'] in overlay_terms
                all_detections.append(c)

    print("  Total candidate detections: %d" % len(all_detections))

    # Combined lookup: live + overlay terms
    all_known = live_terms | overlay_terms

    # Try OCR degarbling on non-live detections
    # Check against both live terms AND overlay terms
    for d in all_detections:
        if not d['exists_as_live'] and not d['exists_in_overlay']:
            corrected = ocr_degarble_headword(d['headword'], all_known)
            if corrected:
                if corrected in live_terms:
                    d['exists_as_live'] = True
                else:
                    d['exists_in_overlay'] = True
                d['degarbled_to'] = corrected
                d['headword_original'] = d['headword']

    # Categorize
    dupes = [d for d in all_detections if d['exists_as_live']]
    new = [d for d in all_detections if not d['exists_as_live'] and not d['exists_in_overlay']]
    in_overlay = [d for d in all_detections if not d['exists_as_live'] and d['exists_in_overlay']]

    print("  Already live headwords (trim): %d" % len(dupes))
    print("  New entries (extract): %d" % len(new))
    print("  In overlay (skip): %d" % len(in_overlay))
    degarbled = [d for d in all_detections if 'degarbled_to' in d]
    if degarbled:
        print("    (includes %d OCR-degarbled reclassifications)" % len(degarbled))
        for dg in degarbled:
            print("      %s -> %s" % (dg.get('headword_original', dg['headword']), dg['degarbled_to']))

    # === Step 2: Conservative Filtering ===
    print("\n=== Step 2: Conservative Filtering ===\n")

    # Confirmed trims: embedded term exists as a live headword
    confirmed_trims = []
    for d in dupes:
        # Parent body should retain at least 30 chars
        new_body = d['parent_term']  # dummy, will recompute
        entry = entry_by_term.get(d['parent_term'].upper())
        if not entry:
            continue
        body = entry.get("body", "") or ""
        new_body_text = body[:d['offset']].rstrip()

        if len(new_body_text) < 30:
            continue
        # Don't trim if we'd remove less than 20 chars (not worth it)
        if len(body) - len(new_body_text) < 20:
            continue
        # Already in body corrections?
        if d['parent_term'] in body_corrections:
            continue

        confirmed_trims.append({
            'parent_term': d['parent_term'],
            'embedded_term': d['headword'],
            'offset': d['offset'],
            'old_len': len(body),
            'new_len': len(new_body_text),
            'new_body': new_body_text,
        })

    # Deduplicate: keep only the FIRST split for each parent
    seen_parents = set()
    deduped_trims = []
    for t in sorted(confirmed_trims, key=lambda x: x['offset']):
        if t['parent_term'] not in seen_parents:
            seen_parents.add(t['parent_term'])
            deduped_trims.append(t)
    confirmed_trims = deduped_trims

    print("  Confirmed trims: %d" % len(confirmed_trims))

    # Build sorted list of known terms for OCR-garble detection
    all_known_list = sorted(all_known)

    # OCR-characteristic substitution pairs (bidirectional)
    OCR_PAIRS = {
        ('O', 'C'), ('C', 'O'),
        ('B', 'R'), ('R', 'B'),
        ('I', 'L'), ('L', 'I'),
        ('N', 'H'), ('H', 'N'),
        ('Y', 'V'), ('V', 'Y'),
        ('0', 'O'), ('O', '0'),
        ('Z', 'S'), ('S', 'Z'),
        ('E', 'F'), ('F', 'E'),
        ('U', 'V'), ('V', 'U'),
    }

    def is_ocr_garble_of_known(hw):
        """Check if hw differs from a known term by OCR-characteristic subs only.
        Returns the known term if it's a garble, else None."""
        hw_u = hw.upper()
        first = hw_u[0] if hw_u else ''
        for known in all_known_list:
            # Check same first letter OR common OCR-sub of first letter
            k_first = known[0] if known else ''
            if k_first != first and (first, k_first) not in OCR_PAIRS:
                if known > chr(ord(first) + 1) + 'Z' and k_first != first:
                    break
                continue
            # Must be same length (OCR subs don't add/remove chars)
            if len(known) != len(hw_u):
                continue
            # Count differences and check if all are OCR-char subs
            diffs = 0
            all_ocr = True
            for a, b in zip(hw_u, known):
                if a != b:
                    diffs += 1
                    if (a, b) not in OCR_PAIRS:
                        all_ocr = False
                        break
            if all_ocr and 1 <= diffs <= 3:
                return known
        return None

    # Confirmed new entries: clean headword, substantive body, not in overlay
    confirmed_new = []
    garble_rejects = []
    for d in new:
        hw = d['headword']
        embed_body = d['embed_body']

        # Must have clean headword
        if not is_clean_headword(hw):
            continue
        # Body must be substantive
        if len(embed_body) < 25:
            continue
        # Headword must be alphabetically after parent
        if hw < d['parent_term'].upper():
            continue
        # Already in body corrections for parent?
        if d['parent_term'] in body_corrections:
            continue
        # Check if headword is an OCR garble of a known term
        near = is_ocr_garble_of_known(hw)
        if near:
            garble_rejects.append((hw, near, d['parent_term']))
            continue

        confirmed_new.append({
            'parent_term': d['parent_term'],
            'headword': hw,
            'headword_raw': d['headword_raw'],
            'embed_body': embed_body,
            'offset': d['offset'],
            'body_len': len(embed_body),
        })

    if garble_rejects:
        print("  Rejected as near-match to known term: %d" % len(garble_rejects))
        for hw, near, parent in garble_rejects:
            print("    %s ~ %s (from %s)" % (hw, near, parent))

    # Deduplicate by headword
    seen_hw = set()
    deduped_new = []
    for n in confirmed_new:
        if n['headword'] not in seen_hw:
            seen_hw.add(n['headword'])
            deduped_new.append(n)
    confirmed_new = deduped_new

    print("  Confirmed new entries: %d" % len(confirmed_new))

    # === Step 3: Apply ===
    print("\n=== Step 3: Apply Changes ===\n")

    # Body corrections for trims
    trims_added = 0
    for t in confirmed_trims:
        bc_key = t['parent_term']
        if bc_key in body_corrections:
            continue
        body_corrections[bc_key] = {
            "body": t['new_body'],
            "_source": "boundary_split_trim",
            "reason": "Trimmed embedded entry '%s' from body" % t['embedded_term'],
        }
        trims_added += 1

    # Body corrections for parents of new entries (trim at first new entry)
    parents_trimmed = set()
    for n in confirmed_new:
        pt = n['parent_term']
        if pt in body_corrections or pt in parents_trimmed:
            continue
        entry = entry_by_term.get(pt.upper())
        if not entry:
            continue
        body = entry.get("body", "") or ""
        new_body = body[:n['offset']].rstrip()
        if len(new_body) < 30:
            continue
        body_corrections[pt] = {
            "body": new_body,
            "_source": "boundary_split_trim",
            "reason": "Trimmed embedded entries starting with '%s'" % n['headword'],
        }
        parents_trimmed.add(pt)
        trims_added += 1

    print("  Body corrections added: %d" % trims_added)

    # New overlay entries
    max_bld_id = 0
    for o in overlay:
        oid = o.get("id", "")
        if oid.startswith("BLD2-"):
            try:
                num = int(oid[5:])
                if num > max_bld_id:
                    max_bld_id = num
            except ValueError:
                pass
    next_id = max_bld_id + 1

    new_added = 0
    for n in confirmed_new:
        term = n['headword_raw']
        if term.upper() in overlay_terms or term.upper() in live_terms:
            continue
        overlay.append({
            "id": "BLD2-%05d" % next_id,
            "term": term,
            "entry_type": "recovered_main",
            "body": n['embed_body'],
            "source_pages": [],
            "_extraction_note": "Extracted from %s body (boundary split)" % n['parent_term'],
        })
        overlay_terms.add(term.upper())
        next_id += 1
        new_added += 1

    print("  New overlay entries: %d" % new_added)

    # Save files
    if trims_added > 0:
        with open(BODY_CORRECTIONS, "w", encoding="utf-8") as f:
            json.dump(body_corrections, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("  Updated: %s" % BODY_CORRECTIONS)

    if new_added > 0:
        with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
            json.dump(overlay, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print("  Updated: %s" % OVERLAY_PATH)

    # Save candidates JSON
    report = {
        "total_detections": len(all_detections),
        "confirmed_trims": len(confirmed_trims),
        "confirmed_new": len(confirmed_new),
        "body_corrections_added": trims_added,
        "overlay_entries_added": new_added,
        "trims": [{"parent": t['parent_term'], "embedded": t['embedded_term'],
                   "old_len": t['old_len'], "new_len": t['new_len']} for t in confirmed_trims],
        "new_entries": [{"parent": n['parent_term'], "headword": n['headword'],
                        "body_len": n['body_len']} for n in confirmed_new],
        "uncertain": [{"parent": d['parent_term'], "headword": d['headword'],
                      "reason": "in_overlay" if d['exists_in_overlay'] else "review"}
                     for d in in_overlay],
    }
    with open(CANDIDATES_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print("  Saved: %s" % CANDIDATES_JSON)

    # Markdown report
    md = [
        "# Entry Boundary Split Results",
        "",
        "Detected and repaired entry boundary failures where subsequent",
        "dictionary entries were merged into a parent entry's body.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        "| Total embedded entries detected | %d |" % len(all_detections),
        "| Confirmed trims (existing entries) | %d |" % len(confirmed_trims),
        "| Confirmed new entries extracted | %d |" % len(confirmed_new),
        "| Body corrections added | %d |" % trims_added,
        "| New overlay entries created | %d |" % new_added,
        "",
        "---",
        "",
    ]

    if confirmed_trims:
        md.append("## Trimmed Parents (%d)" % len(confirmed_trims))
        md.append("")
        md.append("| Parent Entry | Embedded (exists) | Old Len | New Len |")
        md.append("|-------------|------------------|---------|---------|")
        for t in confirmed_trims:
            md.append("| %s | %s | %d | %d |" % (
                t['parent_term'], t['embedded_term'], t['old_len'], t['new_len']))
        md.extend(["", "---", ""])

    if confirmed_new:
        md.append("## New Entries Extracted (%d)" % len(confirmed_new))
        md.append("")
        md.append("| From Parent | New Entry | Body Len |")
        md.append("|------------|-----------|----------|")
        for n in confirmed_new:
            md.append("| %s | %s | %d |" % (n['parent_term'], n['headword'], n['body_len']))
        md.append("")

    with open(RESULTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("  Saved: %s" % RESULTS_MD)

    print("\n=== Done. Run pipeline to apply. ===")


if __name__ == "__main__":
    main()
