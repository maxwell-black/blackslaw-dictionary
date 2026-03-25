#!/usr/bin/env python3
"""
haiku_ocr_cleanup.py — Use Claude Haiku to fix OCR artifacts in entry bodies.

Sends damaged entries to Haiku for correction, accepts changes only if
the edit distance is within 15% of the original body length.

Requires: ANTHROPIC_API_KEY environment variable
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = Path(__file__).resolve().parent.parent
LIVE_CORPUS = REPO / "blacks_entries.json"
REPORT_JSON = REPO / "rebuild" / "reports" / "haiku_cleanup_report.json"
REPORT_MD = REPO / "rebuild" / "reports" / "haiku_cleanup_report.md"

MAX_CHANGE_RATIO = 0.15  # Accept up to 15% change
MAX_WORKERS = 8
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are an OCR error correction tool for Black's Law Dictionary (2nd Edition, 1910).

Fix ONLY clear OCR scanning errors in the text below. Common OCR errors include:
- Garbled characters: accented letters where plain letters belong (é→e, ü→u, etc.)
- Character substitutions: @ for 'a', | for 'l' or 'I', € for 'e'
- Mixed case errors: random capitals mid-word from scanning
- Broken words from bad scanning
- Garbled punctuation

DO NOT:
- Change any legal terminology, Latin phrases, or archaic spellings
- Rewrite or improve the text
- Change formatting, line breaks, or paragraph structure
- Add or remove words
- Fix grammar or style
- Change citation formats

Return ONLY the corrected text, nothing else. If no corrections are needed, return the text unchanged."""


def has_ocr_damage(body):
    """Check if body likely has OCR damage."""
    if not body or len(body) < 20:
        return False
    checks = [
        re.search(r'[\u00e0-\u00ff]', body),  # accented chars
        '@' in body,
        re.search(r'[bcdfghjklmnpqrstvwxz]{5,}', body, re.I),
        re.search(r'[a-z][A-Z][a-z]', body),
        '\u20ac' in body,
        '|' in body,
        re.search(r'[A-Z]\.\s*8\b', body),
    ]
    return any(checks)


def edit_distance(s1, s2):
    """Fast edit distance for change ratio calculation."""
    if abs(len(s1) - len(s2)) > len(s1) * MAX_CHANGE_RATIO + 10:
        return len(s1)  # Too different, skip full computation
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


def fix_entry(client, term, body):
    """Send a single entry to Haiku for OCR correction."""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max(len(body) * 2, 1000),
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": body}],
        )
        return term, resp.content[0].text, None
    except Exception as e:
        return term, None, str(e)


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Try reading from env file
        env_file = Path(r"C:\Users\maxwe\OneDrive\Desktop\anthropic_key.env")
        if env_file.exists():
            text = env_file.read_text().strip()
            # Parse PowerShell format: $env:ANTHROPIC_API_KEY = "..."
            m = re.search(r'"([^"]+)"', text)
            if m:
                api_key = m.group(1)
                os.environ["ANTHROPIC_API_KEY"] = api_key

    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY found")
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic()

    print("Loading corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"  {len(entries)} entries")

    # Find damaged entries
    damaged = []
    for e in entries:
        body = e.get("body", "") or ""
        if has_ocr_damage(body):
            damaged.append(e)

    print(f"  {len(damaged)} entries with likely OCR damage")
    if not damaged:
        print("Nothing to fix.")
        return

    # Process in batches with thread pool
    print(f"\nProcessing with {MAX_WORKERS} workers...")
    results = []
    accepted = 0
    rejected_ratio = 0
    rejected_identical = 0
    errors = 0

    entry_map = {e["term"]: e for e in entries}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for e in damaged:
            future = executor.submit(fix_entry, client, e["term"], e["body"])
            futures[future] = e["term"]

        done = 0
        for future in as_completed(futures):
            done += 1
            term, fixed_body, error = future.result()

            if done % 50 == 0:
                print(f"  ...{done}/{len(damaged)} (accepted={accepted})")

            if error:
                errors += 1
                results.append({"term": term, "status": "error", "error": error})
                continue

            if fixed_body is None:
                errors += 1
                continue

            original = entry_map[term]["body"]

            # Strip any leading/trailing whitespace the model might add
            fixed_body = fixed_body.strip()

            if fixed_body == original:
                rejected_identical += 1
                results.append({"term": term, "status": "unchanged"})
                continue

            # Check change ratio
            dist = edit_distance(original, fixed_body)
            ratio = dist / max(len(original), 1)

            if ratio > MAX_CHANGE_RATIO:
                rejected_ratio += 1
                results.append({
                    "term": term,
                    "status": "rejected_ratio",
                    "ratio": round(ratio, 3),
                    "edit_distance": dist,
                })
                continue

            # Accept the fix
            entry_map[term]["body"] = fixed_body
            accepted += 1
            results.append({
                "term": term,
                "status": "accepted",
                "ratio": round(ratio, 3),
                "edit_distance": dist,
                "original_len": len(original),
                "fixed_len": len(fixed_body),
            })

    print(f"\n=== Results ===")
    print(f"  Processed: {len(damaged)}")
    print(f"  Accepted:  {accepted}")
    print(f"  Unchanged: {rejected_identical}")
    print(f"  Rejected (>15% change): {rejected_ratio}")
    print(f"  Errors:    {errors}")

    if accepted > 0:
        # Save updated corpus
        with open(LIVE_CORPUS, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"\n  Saved: {LIVE_CORPUS}")

    # Save report
    report = {
        "total_entries": len(entries),
        "damaged_entries": len(damaged),
        "accepted": accepted,
        "unchanged": rejected_identical,
        "rejected_ratio": rejected_ratio,
        "errors": errors,
        "max_change_ratio": MAX_CHANGE_RATIO,
        "model": MODEL,
        "results": results,
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {REPORT_JSON}")

    # Markdown report
    md = [
        "# Haiku OCR Cleanup Report",
        "",
        f"Model: {MODEL}",
        f"Max change ratio: {MAX_CHANGE_RATIO:.0%}",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Entries processed | {len(damaged)} |",
        f"| Accepted | {accepted} |",
        f"| Unchanged | {rejected_identical} |",
        f"| Rejected (>{MAX_CHANGE_RATIO:.0%} change) | {rejected_ratio} |",
        f"| Errors | {errors} |",
        "",
    ]

    accepted_results = [r for r in results if r["status"] == "accepted"]
    if accepted_results:
        md.append("## Accepted Fixes")
        md.append("")
        md.append("| Entry | Edit Distance | Change Ratio |")
        md.append("|-------|--------------|-------------|")
        for r in accepted_results[:100]:
            md.append(f"| {r['term']} | {r['edit_distance']} | {r['ratio']:.1%} |")
        if len(accepted_results) > 100:
            md.append(f"| ... | ({len(accepted_results) - 100} more) | |")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"  Saved: {REPORT_MD}")


if __name__ == "__main__":
    main()
