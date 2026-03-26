#!/usr/bin/env python3
"""
resolve_flags.py — Resolve flagged items from Sonnet corpus review.

Processes headword flags and other flags, applying corrections where clear
and skipping ambiguous cases. Generates flag_resolution.md report.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
BODY_CORRECTIONS = REPO / "rebuild" / "overlay" / "body_corrections.json"

# Known archaic/Latin/French terms that should NOT be changed
ARCHAIC_TERMS = {
    "connexion", "shew", "shewn", "colour", "honour", "favour", "judgement",
    "gaol", "waggon", "despatch", "enrol", "wilful", "amongst", "whilst",
    "counsellor", "traveller", "catalogue", "programme", "cheque", "grey",
    "mediaeval", "foetus", "skilful", "fulfil", "instalment",
}


def normalize(term):
    return re.sub(r'[^A-Z0-9 ]', '', term.upper()).strip()


def load_flags():
    """Load all flags from per-letter flag files."""
    hw_flags = []
    other_flags = []
    for letter in "abcdefghijklmnopqrstuvwxyz":
        f = REPO / "rebuild" / "reports" / f"sonnet_flags_{letter}.json"
        if not f.exists():
            continue
        flags = json.load(open(f, encoding="utf-8"))
        for fl in flags:
            fl["_letter"] = letter.upper()
            if fl.get("type") == "headword_review":
                hw_flags.append(fl)
            else:
                other_flags.append(fl)
    return hw_flags, other_flags


def resolve_headword_flags(hw_flags, overlay_by_term, live_terms):
    """Resolve headword flags."""
    results = []

    for flag in hw_flags:
        current = flag.get("term", "")
        suggested = flag.get("suggested", "")
        reason = flag.get("reason", "")
        norm_current = normalize(current)
        norm_suggested = normalize(suggested)

        # Skip if no suggestion
        if not suggested:
            results.append({
                "term": current, "suggested": suggested, "action": "skip",
                "reason": "No suggested correction"
            })
            continue

        # Skip if current and suggested normalize to the same thing
        if norm_current == norm_suggested:
            results.append({
                "term": current, "suggested": suggested, "action": "skip",
                "reason": "Current and suggested normalize identically"
            })
            continue

        # Check if suggested headword already exists as a live entry
        suggested_exists = norm_suggested in live_terms

        if suggested_exists:
            # Suppress as duplicate
            if norm_current in overlay_by_term:
                entry = overlay_by_term[norm_current]
                entry["entry_type"] = "legacy_duplicate"
                results.append({
                    "term": current, "suggested": suggested, "action": "suppress",
                    "reason": f"'{suggested}' already exists as live entry; suppressed '{current}' as legacy_duplicate"
                })
            else:
                results.append({
                    "term": current, "suggested": suggested, "action": "skip",
                    "reason": f"'{suggested}' exists but '{current}' not found in overlay"
                })
        else:
            # Check if the correction looks reasonable
            # Reject if the change is too dramatic (completely different word)
            if len(norm_current) > 3 and len(norm_suggested) > 3:
                # Check first letter matches (basic sanity)
                first_match = norm_current[0] == norm_suggested[0] if norm_current and norm_suggested else False

                if not first_match and not _is_ocr_garble(norm_current, norm_suggested):
                    results.append({
                        "term": current, "suggested": suggested, "action": "skip",
                        "reason": f"First letter mismatch and not clear OCR garble"
                    })
                    continue

            # Apply headword correction
            if norm_current in overlay_by_term:
                entry = overlay_by_term[norm_current]
                entry["term"] = suggested
                entry["entry_type"] = "headword_corrected"
                results.append({
                    "term": current, "suggested": suggested, "action": "correct",
                    "reason": f"Headword corrected: '{current}' -> '{suggested}'"
                })
            else:
                results.append({
                    "term": current, "suggested": suggested, "action": "skip",
                    "reason": f"'{current}' not found in overlay"
                })

    return results


def _is_ocr_garble(s1, s2):
    """Check if two strings differ by common OCR character swaps."""
    ocr_pairs = {
        ('O', 'C'), ('C', 'O'), ('O', '0'), ('0', 'O'),
        ('I', 'L'), ('L', 'I'), ('B', 'R'), ('R', 'B'),
        ('Z', 'S'), ('S', 'Z'), ('Y', 'V'), ('V', 'Y'),
        ('8', 'S'), ('S', '8'), ('H', 'N'), ('N', 'H'),
    }
    if abs(len(s1) - len(s2)) > 3:
        return False
    # Simple character-level comparison
    diffs = 0
    for c1, c2 in zip(s1, s2):
        if c1 != c2:
            if (c1, c2) not in ocr_pairs:
                diffs += 1
            if diffs > 3:
                return False
    return True


def resolve_other_flags(other_flags, entry_bodies, body_corrections):
    """Resolve non-headword flags."""
    results = []

    for flag in other_flags:
        term = flag.get("term", "")
        issue = flag.get("issue", "")

        # Categorize the issue
        issue_lower = issue.lower()

        # Skip ambiguous/complex issues
        if any(kw in issue_lower for kw in [
            "unclear", "unsure", "may be", "might be", "possible",
            "appears to be a duplicate", "not sure", "uncertain",
            "could be", "could also",
        ]):
            results.append({
                "term": term, "issue": issue[:100], "action": "skip",
                "reason": "Ambiguous flag"
            })
            continue

        # Skip flags about Latin/archaic terms
        if any(kw in issue_lower for kw in [
            "latin", "law french", "archaic", "mediaeval", "connexion",
        ]):
            results.append({
                "term": term, "issue": issue[:100], "action": "skip",
                "reason": "Latin/archaic term — not an error"
            })
            continue

        # OCR damage flags — check for specific fix suggestions
        if "ocr" in issue_lower and ("'" in issue or '"' in issue):
            # Try to extract old->new from the issue text
            m = re.search(r"'([^']+)'\s*(?:should be|->|=>|is.*error for)\s*'([^']+)'", issue)
            if m:
                old_text, new_text = m.group(1), m.group(2)
                body = entry_bodies.get(term, "")
                if body and old_text in body:
                    new_body = body.replace(old_text, new_text, 1)
                    body_corrections[term] = {"body": new_body, "_source": "flag_resolution"}
                    results.append({
                        "term": term, "issue": issue[:100], "action": "fix_ocr",
                        "reason": f"Applied: '{old_text}' -> '{new_text}'"
                    })
                    continue

        # Headword truncation flags
        if "truncat" in issue_lower or "incomplete" in issue_lower:
            results.append({
                "term": term, "issue": issue[:100], "action": "skip",
                "reason": "Headword truncation — requires manual review"
            })
            continue

        # Garbled/garbage entry flags
        if "garbage" in issue_lower or "garbled" in issue_lower or "ocr garbage" in issue_lower:
            results.append({
                "term": term, "issue": issue[:100], "action": "skip",
                "reason": "Garbled entry — requires manual review"
            })
            continue

        # Merged content / boundary flags
        if "merged" in issue_lower or "embedded" in issue_lower or "belongs to" in issue_lower:
            results.append({
                "term": term, "issue": issue[:100], "action": "skip",
                "reason": "Boundary/merge issue — requires manual review"
            })
            continue

        # Default: skip
        results.append({
            "term": term, "issue": issue[:100], "action": "skip",
            "reason": "Could not auto-resolve"
        })

    return results


def generate_report(hw_results, other_results):
    """Generate flag_resolution.md report."""
    lines = [
        "# Flag Resolution Report",
        "",
        "## Summary",
        "",
    ]

    # Count actions
    hw_actions = {}
    for r in hw_results:
        a = r["action"]
        hw_actions[a] = hw_actions.get(a, 0) + 1

    other_actions = {}
    for r in other_results:
        a = r["action"]
        other_actions[a] = other_actions.get(a, 0) + 1

    lines.append("### Headword Flags")
    lines.append("")
    lines.append(f"| Action | Count |")
    lines.append(f"|--------|-------|")
    for action, count in sorted(hw_actions.items()):
        lines.append(f"| {action} | {count} |")
    lines.append(f"| **Total** | **{len(hw_results)}** |")

    lines.append("")
    lines.append("### Other Flags")
    lines.append("")
    lines.append(f"| Action | Count |")
    lines.append(f"|--------|-------|")
    for action, count in sorted(other_actions.items()):
        lines.append(f"| {action} | {count} |")
    lines.append(f"| **Total** | **{len(other_results)}** |")

    # Detailed results
    lines.extend(["", "## Headword Flag Details", ""])
    lines.append("| Current | Suggested | Action | Reason |")
    lines.append("|---------|-----------|--------|--------|")
    for r in hw_results:
        reason = r["reason"][:80].replace("|", "/")
        lines.append(f'| {r["term"]} | {r.get("suggested","")} | {r["action"]} | {reason} |')

    lines.extend(["", "## Other Flag Details", ""])
    lines.append("| Entry | Action | Reason |")
    lines.append("|-------|--------|--------|")
    for r in other_results:
        reason = r["reason"][:80].replace("|", "/")
        lines.append(f'| {r["term"]} | {r["action"]} | {reason} |')

    return "\n".join(lines)


def main():
    print("Loading flags...")
    hw_flags, other_flags = load_flags()
    print(f"  Headword flags: {len(hw_flags)}")
    print(f"  Other flags: {len(other_flags)}")

    print("Loading overlay...")
    with open(OVERLAY_PATH, encoding="utf-8") as f:
        overlay = json.load(f)

    # Build lookup
    overlay_by_term = {}
    for entry in overlay:
        key = normalize(entry["term"])
        overlay_by_term[key] = entry

    # Build set of live entry terms
    live_types = {
        "verified_main", "provisional_main", "recovered_main",
        "headword_corrected", "alias_variant", "reversed_polarity",
        "unmatched_keep", "subentry", "legacy_retained",
    }
    live_terms = set()
    for entry in overlay:
        if entry.get("entry_type") in live_types:
            live_terms.add(normalize(entry["term"]))

    print(f"  {len(live_terms)} live terms in overlay")

    # Load entry bodies
    with open(REPO / "blacks_entries.json", encoding="utf-8") as f:
        entries = json.load(f)
    entry_bodies = {e["term"]: e.get("body", "") for e in entries}

    # Load body corrections
    with open(BODY_CORRECTIONS, encoding="utf-8") as f:
        body_corrections = json.load(f)

    # Resolve headword flags
    print("\nResolving headword flags...")
    hw_results = resolve_headword_flags(hw_flags, overlay_by_term, live_terms)
    hw_actions = {}
    for r in hw_results:
        hw_actions[r["action"]] = hw_actions.get(r["action"], 0) + 1
    for action, count in sorted(hw_actions.items()):
        print(f"  {action}: {count}")

    # Resolve other flags
    print("\nResolving other flags...")
    other_results = resolve_other_flags(other_flags, entry_bodies, body_corrections)
    other_actions = {}
    for r in other_results:
        other_actions[r["action"]] = other_actions.get(r["action"], 0) + 1
    for action, count in sorted(other_actions.items()):
        print(f"  {action}: {count}")

    # Save overlay
    with open(OVERLAY_PATH, "w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nSaved overlay: {OVERLAY_PATH}")

    # Save body corrections
    with open(BODY_CORRECTIONS, "w", encoding="utf-8") as f:
        json.dump(body_corrections, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Saved body corrections: {BODY_CORRECTIONS}")

    # Generate report
    report = generate_report(hw_results, other_results)
    report_path = REPO / "rebuild" / "reports" / "flag_resolution.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Saved report: {report_path}")


if __name__ == "__main__":
    main()
