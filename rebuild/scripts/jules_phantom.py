#!/usr/bin/env python3
import json
import re
import argparse
from pathlib import Path
from datetime import date

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent.parent
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
REBUILT_PATH = REPO / "rebuild" / "out" / "blacks_entries.rebuilt.json"
LIVE_PATH = REPO / "blacks_entries.json"
REPORTS_DIR = REPO / "rebuild" / "reports"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Do not write changes to files")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    with open(OVERLAY_PATH, "r", encoding="utf-8") as f:
        overlay = json.load(f)

    with open(LIVE_PATH, "r", encoding="utf-8") as f:
        live = json.load(f)

    live_by_term = {entry["term"]: entry for entry in live}

    candidates = []

    # We should refine heuristics. The prompt says:
    # 1. Phantom entries
    # Entries whose body is unrelated to the term. Canonical: GATES containing stray court cross-reference text.
    # Heuristics:
    # - Body contains court citations ("State v. X, 123 N.W. 456") disproportionate to body length
    # - No definitional language ("is", "means", "denotes", "signifies", "a ___ who")
    # - Body length < 80 chars AND body starts with "See" or "Cf." with nothing substantive after

    court_cite_re = re.compile(r"([A-Z][a-z]+(?:.+?)?)\s+v\.\s+[A-Z]", re.IGNORECASE)
    def_words_re = re.compile(r"\b(is|means|denotes|signifies|a\s+.*?\s+who)\b", re.IGNORECASE)

    def count_court_cites(body):
        return len(court_cite_re.findall(body))

    for entry in overlay:
        term = entry["term"]
        if term not in live_by_term:
            continue

        body = live_by_term[term].get("body", "")
        body_len = len(body)

        is_phantom = False
        reason = ""

        cites_count = count_court_cites(body)
        has_def = bool(def_words_re.search(body))

        starts_see_cf = body.startswith("See ") or body.startswith("Cf. ")
        is_short_see = False
        if body_len < 80 and starts_see_cf:
            # Check if there is "nothing substantive after"
            # It usually is just "See <Target>." or "See <Target>, <Target>."
            substantive_check = re.sub(r"^(See|Cf\.)\s+([A-Za-z0-9\s,\.\-'\"]+)[.;]?\s*$", "", body, flags=re.IGNORECASE)
            if len(substantive_check.strip()) < 10:
                is_short_see = True

        if is_short_see:
            # Wait, the prompt says "Canonical: GATES containing stray court cross-reference text"
            # Is "See X" considered a phantom entry? No, it's considered a mis-typed cross-reference or phantom.
            pass

        # Let's adjust heuristics

        if body_len < 80 and starts_see_cf:
            substantive = re.sub(r"^(See|Cf\.)\s+[A-Z\s,]+[.;]\s*", "", body, flags=re.IGNORECASE)
            if not substantive.strip():
                is_phantom = True
                reason = "short_see"
        elif cites_count > 0 and not has_def:
            # Disproportionate? If > 0 and no def, it's pretty disproportionate.
            if body_len < 400 or cites_count >= 2:
                is_phantom = True
                reason = "court_cites_no_def"

        if is_phantom:
            candidates.append({
                "id": entry["id"],
                "term": term,
                "body": body,
                "reason": reason
            })

    print(f"Found {len(candidates)} phantom candidates.")
    with open(REPORTS_DIR / "jules_phantom_candidates.jsonl", "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")

if __name__ == "__main__":
    main()
