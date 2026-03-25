#!/usr/bin/env python3
"""Generate AI review summary report from all per-letter Sonnet review results."""

import json
from pathlib import Path

repo = Path(__file__).resolve().parent.parent

lines = [
    "# AI Corpus Review Summary - Sonnet 4.6",
    "",
    "Opus orchestrator + Sonnet subagent review of all 12,981 entries.",
    "Quality gate: Opus rejected corrections to archaic/Latin/Law French terms.",
    "",
    "## Per-Letter Results",
    "",
    "| Letter | Entries | OCR Fixes | Trims | Headwords | Flags | Total |",
    "|--------|---------|-----------|-------|-----------|-------|-------|",
]

grand = {"entries": 0, "ocr_fix": 0, "trim": 0, "headword": 0, "flag": 0, "total": 0}
all_flags = []

for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    f = repo / "rebuild" / "reports" / f"sonnet_review_{letter.lower()}.json"
    if not f.exists():
        continue
    data = json.load(open(f, encoding="utf-8"))
    n = data["entries_reviewed"]
    bt = data.get("by_type", {})
    total = len(data["corrections"])
    ocr = bt.get("ocr_fix", 0)
    trim = bt.get("trim", 0)
    hw = bt.get("headword", 0)
    fl = bt.get("flag", 0)
    lines.append(f"| {letter} | {n} | {ocr} | {trim} | {hw} | {fl} | {total} |")
    grand["entries"] += n
    grand["ocr_fix"] += ocr
    grand["trim"] += trim
    grand["headword"] += hw
    grand["flag"] += fl
    grand["total"] += total

    ff = repo / "rebuild" / "reports" / f"sonnet_flags_{letter.lower()}.json"
    if ff.exists():
        flags = json.load(open(ff, encoding="utf-8"))
        all_flags.extend(flags)

lines.append(
    f'| **TOTAL** | **{grand["entries"]}** | **{grand["ocr_fix"]}** | '
    f'**{grand["trim"]}** | **{grand["headword"]}** | **{grand["flag"]}** | '
    f'**{grand["total"]}** |'
)

hw_flags = [f for f in all_flags if f.get("type") == "headword_review"]
other_flags = [f for f in all_flags if f.get("type") != "headword_review"]

lines.extend([
    "",
    "## Quality Gate",
    "",
    "- Archaic false positives rejected: ~15 (connexion, gaol, shewn, etc.)",
    f"- Headword corrections deferred to flags: {grand['headword']}",
    f"- Items flagged for manual review: {len(all_flags)}",
    "",
    "## Flagged Items (Manual Review Needed)",
    "",
])

if hw_flags:
    lines.append("### Headword Corrections (deferred)")
    lines.append("")
    lines.append("| Current | Suggested | Reason |")
    lines.append("|---------|-----------|--------|")
    for f in hw_flags[:50]:
        reason = f.get("reason", "")[:80].replace("|", "/")
        lines.append(f'| {f.get("term","")} | {f.get("suggested","")} | {reason} |')
    if len(hw_flags) > 50:
        lines.append(f"| ... | ({len(hw_flags)-50} more) | |")
    lines.append("")

if other_flags:
    lines.append("### Other Flags")
    lines.append("")
    lines.append("| Entry | Issue |")
    lines.append("|-------|-------|")
    for f in other_flags[:50]:
        issue = f.get("issue", "")[:100].replace("|", "/")
        lines.append(f'| {f.get("term","")} | {issue} |')
    if len(other_flags) > 50:
        lines.append(f"| ... | ({len(other_flags)-50} more) |")

with open(repo / "rebuild" / "reports" / "ai_review_summary.md", "w", encoding="utf-8") as out:
    out.write("\n".join(lines))

print(f"Saved ai_review_summary.md")
print(f"Total flags: {len(all_flags)} ({len(hw_flags)} headword, {len(other_flags)} other)")
