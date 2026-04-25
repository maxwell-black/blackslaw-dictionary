#!/usr/bin/env python3
import json
import re
import hashlib
from pathlib import Path

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
BLACKS_ENTRIES = REPO / "blacks_entries.json"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
BODY_CORR_PATH = REPO / "rebuild" / "overlay" / "body_corrections.json"
REVIEW_QUEUE_PATH = REPO / "review_queue.json"
REPORT_PATH = REPO / "JULES_CLEANUP_REPORT_2.md"

# Regexes
RE_FIRST_TOKEN = re.compile(r'^[\s"—\.\']*([A-Z0-9\.\']+)(?:[\s—\.,]|$)')
RE_SUBENTRY = re.compile(r'—([A-Z][A-Za-z\s\.,\']{1,50}?)\.\s+[A-Z]')
# "shall be" or "is to be" and citation: ends with something like . [1-9A-Za-z...].
RE_MAXIM = re.compile(r'([A-Za-z\s,]+)\.\s+([A-Za-z\s,\'\[\]]+(?:shall be|is to be)[A-Za-z\s,\[\]]*)\.\s+([A-Za-z0-9\s,\.]+)\.?$')

# Exclude prefixes like Mc, Mac, O', Le
RE_MIXED_CASE = re.compile(r'\b(?!(?:Mc|Mac|O\'|Le)[A-Z])[A-Za-z]*[a-z]+[A-Z]+[A-Za-z]*\b')

HIGH_CONFIDENCE_REPLACEMENTS = {
    "Oustomary": "Customary",
    "Eaglish": "English",
    "BI..": "Bl.",
    "4. e.,": "i. e.,",
    "Blackstoue": "Blackstone",
    "Oompare": "Compare"
}

def levenshtein(s1, s2):
    if len(s1) < len(s2): return levenshtein(s2, s1)
    if len(s2) == 0: return len(s1)
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]

def get_hash(evidence):
    return hashlib.md5(str(evidence).encode('utf-8')).hexdigest()

def main():
    print("Loading data...")
    with BLACKS_ENTRIES.open("r", encoding="utf-8") as f:
        blacks = json.load(f)
    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)
    with BODY_CORR_PATH.open("r", encoding="utf-8") as f:
        body_corr = json.load(f)

    term_to_id = {}
    for o in overlay:
        if o["term"] not in term_to_id:
            term_to_id[o["term"]] = []
        term_to_id[o["term"]].append(o["id"])

    # Load review queue
    review_queue = []
    seen_queue_keys = set()
    if REVIEW_QUEUE_PATH.exists():
        with REVIEW_QUEUE_PATH.open("r", encoding="utf-8") as f:
            review_queue = json.load(f)
            for item in review_queue:
                key = (item["id"], item["category"], item.get("evidence_hash", ""))
                seen_queue_keys.add(key)

    def add_to_queue(item):
        ev_hash = get_hash(item["evidence"])
        item["evidence_hash"] = ev_hash
        key = (item["id"], item["category"], ev_hash)
        if key not in seen_queue_keys:
            review_queue.append(item)
            seen_queue_keys.add(key)

    # Maps for tracking updates
    counts = {
        "case_a_applied": 0,
        "case_b_flagged": 0,
        "case_c_flagged": 0,
        "subentry_mismatch_flagged": 0,
        "embedded_maxim_flagged": 0,
        "high_conf_ocr_applied": 0,
        "medium_conf_ocr_flagged": 0
    }

    # Helper for overlay lookups
    overlay_dict = {o["id"]: o for o in overlay}

    for entry in blacks:
        term = entry["term"]
        body = entry["body"]

        ids = term_to_id.get(term)
        if not ids:
            continue
        entry_id = ids[0]

        # 1. Headword/body alignment
        match = RE_FIRST_TOKEN.search(body)
        if match:
            first_token = match.group(1).rstrip('.')
            headword_clean = term.strip().rstrip('.')

            # Only consider it a token if it's all uppercase or mostly uppercase (e.g. acronyms, B.R.)
            # Need to avoid "The" or other standard sentence starters.
            # Black's headwords in body are all caps.
            if first_token.isupper() and len(first_token) > 0:
                if len(headword_clean) < len(first_token) and first_token.startswith(headword_clean):
                    # Case A: prefix
                    # High confidence retype
                    counts["case_a_applied"] += 1
                    ov = overlay_dict.get(entry_id)
                    if ov:
                        ov["term"] = first_token
                elif len(headword_clean) == len(first_token) and headword_clean != first_token:
                    # Case C: Levenshtein <= 1
                    if levenshtein(headword_clean, first_token) <= 1:
                        counts["case_c_flagged"] += 1
                        add_to_queue({
                            "id": entry_id,
                            "headword": term,
                            "category": "ocr_slip_candidate",
                            "confidence": 0.8,
                            "evidence": f"Headword: {term}, First token: {first_token}",
                            "proposed_action": "review_for_ocr_slip"
                        })
                elif len(headword_clean) >= 2 and len(first_token) >= 2 and not first_token.startswith(headword_clean[:2]) and not headword_clean.startswith(first_token[:2]):
                     # Case B: Unrelated
                     # Only flag if not heavily overlapping
                     if levenshtein(headword_clean, first_token) > 2:
                         counts["case_b_flagged"] += 1
                         add_to_queue({
                             "id": entry_id,
                             "headword": term,
                             "category": "boundary_failure_candidate",
                             "confidence": 0.9,
                             "evidence": f"Headword: {term}, First token: {first_token}, Body preview: {body[:300]}",
                             "proposed_action": "review_for_boundary_failure"
                         })

        # 2. Sub-entry parent mismatch
        subentries = RE_SUBENTRY.findall(body)
        if len(subentries) > 1:
            stems = [s.split()[0].upper() for s in subentries if s]
            if stems:
                common_stem = stems[0]
                all_match = all(s.startswith(common_stem[:4]) for s in stems if len(s) > 4 and len(common_stem) > 4)
                if all_match and len(common_stem) > 4:
                    if not term.upper().startswith(common_stem[:4]):
                        counts["subentry_mismatch_flagged"] += 1
                        add_to_queue({
                            "id": entry_id,
                            "headword": term,
                            "category": "subentry_parent_mismatch",
                            "confidence": 0.8,
                            "evidence": f"Parent: {term}, Common stem: {common_stem}, Subentries: {subentries}",
                            "proposed_action": "review_for_migration"
                        })

        # 3. Embedded maxim detection
        # Try to find maxims at the very end of the body
        sentences = [s.strip() for s in body.replace('\n', ' ').split('. ') if s.strip()]
        if len(sentences) >= 3:
            end_text = ". ".join(sentences[-3:]) + "."
            match_maxim = RE_MAXIM.search(end_text)
            if match_maxim:
                latin = match_maxim.group(1).strip()
                english = match_maxim.group(2).strip()
                counts["embedded_maxim_flagged"] += 1
                add_to_queue({
                    "id": entry_id,
                    "subitem": "embedded_maxim_candidate",
                    "headword": term,
                    "category": "embedded_maxim_candidate",
                    "confidence": 0.7,
                    "evidence": f"Latin: {latin}. English: {english}.",
                    "proposed_action": "extract_to_new_entry"
                })

        # 4. OCR Residual sweep
        # High confidence
        new_body = body
        for old, new in HIGH_CONFIDENCE_REPLACEMENTS.items():
            if old in new_body:
                new_body = new_body.replace(old, new)

        if new_body != body:
            counts["high_conf_ocr_applied"] += 1
            if term in body_corr:
                # Merge logic
                bc_entry = body_corr[term]
                if isinstance(bc_entry, dict):
                    # Base body for next replacement is the corrected one if already exist
                    curr_corr_body = bc_entry.get("body", entry["body"])
                    for old, new in HIGH_CONFIDENCE_REPLACEMENTS.items():
                        if old in curr_corr_body:
                            curr_corr_body = curr_corr_body.replace(old, new)
                    bc_entry["body"] = curr_corr_body
                    if "reason" in bc_entry:
                        if "auto-applied high-confidence OCR fix" not in bc_entry["reason"]:
                            bc_entry["reason"] += " | auto-applied high-confidence OCR fix"
                    else:
                        bc_entry["reason"] = "auto-applied high-confidence OCR fix"
                else:
                    print(f"Warning: Unexpected body_corrections format for {term}")
            else:
                body_corr[term] = {
                    "body": new_body,
                    "reason": "auto-applied high-confidence OCR fix",
                    "_source": "heph_cleanup_pass_2"
                }

        # Medium confidence (mixed case, stray < or ))
        words = body.split()
        for i, w in enumerate(words):
            is_match = False

            # Check mixed case
            if RE_MIXED_CASE.search(w):
                is_match = True

            # Check <
            if '<' in w:
                is_match = True

            # Check )
            if ')' in w and '(' not in w:
                # only if inside an alphabetic word
                clean_w = w.strip('.,;:"\'()')
                if ')' in clean_w and any(c.isalpha() for c in clean_w):
                    is_match = True

            if is_match:
                start_idx = max(0, i - 2)
                end_idx = min(len(words), i + 3)
                context = " ".join(words[start_idx:end_idx])

                counts["medium_conf_ocr_flagged"] += 1
                add_to_queue({
                    "id": entry_id,
                    "headword": term,
                    "category": "medium_confidence_ocr",
                    "confidence": 0.5,
                    "evidence": f"Word: {w}, Context: {context}",
                    "proposed_action": "review_for_correction"
                })

    print("Writing updates...")
    with OVERLAY_PATH.open("w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with BODY_CORR_PATH.open("w", encoding="utf-8") as f:
        json.dump(body_corr, f, indent=2, ensure_ascii=False)
        f.write("\n")

    with REVIEW_QUEUE_PATH.open("w", encoding="utf-8") as f:
        json.dump(review_queue, f, indent=2, ensure_ascii=False)
        f.write("\n")

    report = f"""# Jules Cleanup Report 2

## Methodology Notes
- **Headword/body alignment:** Extracted first ALL-CAPS token from the body. Case A (headword is strict prefix) was applied directly to `editorial_overlay.json` by updating the `term` field. Case B (morphologically unrelated) and Case C (Levenshtein distance 1) were logged to `review_queue.json`.
- **Sub-entry parent mismatch:** Detected sub-entries using the `—[Subterm].` pattern. If multiple sub-entries shared a stem not matching the parent headword, the entry was flagged in `review_queue.json`.
- **Embedded maxim detection:** Searched the end of entry bodies for Latin phrases followed by English translations containing "shall be" or "is to be", plus a citation. Flagged candidates.
- **OCR residual sweep:** High-confidence replacements (`Oustomary`, etc.) were directly applied and added to `body_corrections.json`. Medium-confidence patterns (mixed case, stray `<` or `)`) were logged with 5 words of context to the review queue.
- **Pipeline Constraints:** Invariants were preserved. `blacks_entries.json` was treated as strictly read-only. Retypes for Case A were applied via the overlay, and body text edits were isolated to `body_corrections.json`.

## Counts
- Case A (prefix retype) applied: {counts['case_a_applied']}
- Case B (boundary failure) flagged: {counts['case_b_flagged']}
- Case C (OCR slip) flagged: {counts['case_c_flagged']}
- Sub-entry parent mismatches flagged: {counts['subentry_mismatch_flagged']}
- Embedded maxims flagged: {counts['embedded_maxim_flagged']}
- High-confidence OCR fixes applied: {counts['high_conf_ocr_applied']}
- Medium-confidence OCR issues flagged: {counts['medium_conf_ocr_flagged']}
"""
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        f.write(report)

    print("Done!")

if __name__ == "__main__":
    main()
