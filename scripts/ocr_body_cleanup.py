#!/usr/bin/env python3
"""
ocr_body_cleanup.py — OCR artifact cleanup for entry bodies.

Applies unambiguous fixes:
  1. @ -> a (extends existing patterns from clean_body_ocr.py)
  2. h/b swaps: tbe->the, witb->with, tbat->that, bave->have, bim->him,
     tbeir->their, wbo->who, etc.
  3. Hyphenated line breaks: "word-\nletter" -> "wordletter"
  4. 4-for-a fixes (already in clean_body_ocr.py, extended here)
  5. 8-for-S in abbreviation context (U. 8. -> U. S.)
  6. Standalone "aud" -> "and"
  7. Pipe character removal
  8. g. v.) -> q. v.) and parenthesis alignment
  9. Euro sign fixes (i. €. -> i. e.)
  10. Additional h/b swaps (otber->other, etc.)

Does NOT fix:
  - 'bis' (could be Latin "bis" meaning "twice")
  - Archaic spellings, Latin, Law French, or rare legal terms
  - Single-character artifacts that need DjVu context

Writes:
  - Updated blacks_entries.json (bodies cleaned)
  - rebuild/reports/ocr_cleanup_report.json (tracking all changes)
  - rebuild/reports/ocr_cleanup_report.md (human-readable summary)
"""

import json
import re
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

LIVE_CORPUS = REPO / "blacks_entries.json"
REPORT_JSON = REPO / "rebuild" / "reports" / "ocr_cleanup_report.json"
REPORT_MD = REPO / "rebuild" / "reports" / "ocr_cleanup_report.md"


# ── @ fixes (from clean_body_ocr.py, comprehensive) ──────────────────────────
AT_FIXES = [
    (r'a@\s', 'a ', 'a@->a'),
    (r'@b\b', 'ab', '@b->ab'),
    (r'&@\s', 'a ', '&@->a'),
    (r'\s@&\s', ' a ', '@&->a'),
    (r'\s@\s', ' a ', ' @ -> a'),
    (r'\(@\s', '(a ', '(@->a'),
    (r'(?<=\s)@(?=[a-z])', 'a ', '@->a_before_lc'),
    (r'^@(?=[a-z])', 'a ', '@->a_start'),
    # @ after comma/semicolon before space
    (r'(?<=[,;])\s@\s', ' a ', '@->a_after_punct'),
    # @ between two lowercase letters: "c@se" -> "case"
    (r'(?<=[a-z])@(?=[a-z])', 'a', '@->a_mid_word'),
]

# ── 4-for-a fixes ────────────────────────────────────────────────────────────
DIGIT_FIXES = [
    (r'(?<![0-9§])4nd\b', 'and', '4nd->and'),
    (r'(?<![0-9§])4ll\b', 'all', '4ll->all'),
    (r'(?<![0-9§])4n\s', 'an ', '4n->an'),
    (r'(?<![0-9§])4s\s', 'as ', '4s->as'),
    (r'(?<![0-9§])4t\s', 'at ', '4t->at'),
    (r'(?<![0-9§])4re\b', 'are', '4re->are'),
    (r'(?<![0-9§])4ct\b', 'act', '4ct->act'),
]

# ── h/b OCR swaps (h misread as b or vice versa) ─────────────────────────────
# Only fix when the result is an unambiguous common English word.
# Each tuple: (pattern, replacement, label, flags)
# IMPORTANT: 'bis' is NOT fixed because it's also Latin for "twice"
HB_FIXES = [
    # b -> h (common: b misread where h should be)
    (r'\btbe\b', 'the', 'tbe->the'),
    (r'\bTbe\b', 'The', 'Tbe->The'),
    (r'\btbat\b', 'that', 'tbat->that'),
    (r'\bTbat\b', 'That', 'Tbat->That'),
    (r'\btbis\b', 'this', 'tbis->this'),
    (r'\bTbis\b', 'This', 'Tbis->This'),
    (r'\btbeir\b', 'their', 'tbeir->their'),
    (r'\btben\b', 'then', 'tben->then'),
    (r'\btbere\b', 'there', 'tbere->there'),
    (r'\btbey\b', 'they', 'tbey->they'),
    (r'\btbing\b', 'thing', 'tbing->thing'),
    (r'\btbings\b', 'things', 'tbings->things'),
    (r'\btbrough\b', 'through', 'tbrough->through'),
    (r'\btbus\b', 'thus', 'tbus->thus'),
    (r'\bwitb\b', 'with', 'witb->with'),
    (r'\bWitb\b', 'With', 'Witb->With'),
    (r'\bwbich\b', 'which', 'wbich->which'),
    (r'\bWbich\b', 'Which', 'Wbich->Which'),
    (r'\bwben\b', 'when', 'wben->when'),
    (r'\bWben\b', 'When', 'Wben->When'),
    (r'\bwbere\b', 'where', 'wbere->where'),
    (r'\bwbo\b', 'who', 'wbo->who'),
    (r'\bwbat\b', 'what', 'wbat->what'),
    (r'\bwbile\b', 'while', 'wbile->while'),
    (r'\bwbose\b', 'whose', 'wbose->whose'),
    (r'\bwbole\b', 'whole', 'wbole->whole'),
    (r'\bwbitber\b', 'whither', 'wbitber->whither'),
    (r'\bbave\b', 'have', 'bave->have'),
    (r'\bBave\b', 'Have', 'Bave->Have'),
    # 'bas' excluded — could be French/Latin
    # 'bad' excluded — real English word
    (r'\bbim\b', 'him', 'bim->him'),
    (r'\bber\b', 'her', 'ber->her'),
    (r'\bbeld\b', 'held', 'beld->held'),
    (r'\bbolding\b', 'holding', 'bolding->holding'),
    (r'\bbouse\b', 'house', 'bouse->house'),
    (r'\bbowever\b', 'however', 'bowever->however'),
    (r'\bBowever\b', 'However', 'Bowever->However'),
    (r'\bbusband\b', 'husband', 'busband->husband'),
    # h -> b (less common)
    (r'\bhe\b', None, None),  # DO NOT fix 'he' - it's always correct
    # Additional h/b swaps
    (r'\botber\b', 'other', 'otber->other'),
    (r'\bOtber\b', 'Other', 'Otber->Other'),
    (r'\botbers\b', 'others', 'otbers->others'),
    (r'\banotber\b', 'another', 'anotber->another'),
    (r'\brigbt\b', 'right', 'rigbt->right'),
    (r'\bRigbt\b', 'Right', 'Rigbt->Right'),
]

# Remove None entries (DO NOT FIX markers)
HB_FIXES = [(p, r, l) for p, r, l in HB_FIXES if r is not None]

# ── 8-for-S in abbreviation context ──────────────────────────────────────────
# "U. 8." -> "U. S.", "D. 8." -> "D. S.", etc. (X. 8. -> X. S.)
EIGHT_S_PATTERN = re.compile(r'([A-Z])\.\s*8\.')

# ── Standalone "aud" -> "and" ──────────────────────────────────────────────
# Only when standalone word (not part of fraud, laud, etc.)
AUD_PATTERN = re.compile(r'\baud\b')

# ── Pipe character removal ────────────────────────────────────────────────
PIPE_PATTERN = re.compile(r'\s\|\s')

# ── g. v.) -> q. v.) fix (OCR garble of q->g) ──────────────────────────────
GV_PATTERN = re.compile(r'g\.\s*v\.\)')

# ── Missing open paren on q. v.) ──────────────────────────────────────────
QV_NOPAREN = re.compile(r'(?<!\()q\.\s*v\.\)')

# ── Euro sign fixes ──────────────────────────────────────────────────────
EURO_FIXES = [
    (re.compile(r'i\.\s*\u20ac\.'), 'i. e.', 'euro->ie'),
    (re.compile(r'\u20ac\.\s*g\.'), 'e. g.', 'euro->eg'),
    (re.compile(r'\u20ac'), 'e', 'euro->e'),
]

# ── Specific word fixes ──────────────────────────────────────────────────
WORD_FIXES = [
    (r'\bexaniples\b', 'examples', 'exaniples->examples'),
]

# ── Hyphenated line break fixes ──────────────────────────────────────────────
# Pattern: "word-\nletter" where the hyphen is a line-break hyphen, not a real hyphen
# Only rejoin when next line starts with lowercase (continuation)
HYPH_PATTERN = re.compile(r'(\w)-\n([a-z])')
# Also handle "word- letter" (hyphen + space + lowercase)
HYPH_SPACE_PATTERN = re.compile(r'(\w)-\s+([a-z])')


def clean_body_extended(body):
    """Apply comprehensive OCR fixes to a single body string."""
    if not body:
        return body, {}

    counts = {}
    text = body

    def counted_sub(pattern, replacement, label, flags=0):
        nonlocal text
        new_text, n = re.subn(pattern, replacement, text, flags=flags)
        if n > 0:
            counts[label] = counts.get(label, 0) + n
            text = new_text

    # 1. @ fixes
    for pattern, repl, label in AT_FIXES:
        counted_sub(pattern, repl, label)

    # 2. Digit fixes
    for pattern, repl, label in DIGIT_FIXES:
        counted_sub(pattern, repl, label)

    # 3. h/b swaps — case-sensitive
    for pattern, repl, label in HB_FIXES:
        counted_sub(pattern, repl, label)

    # 4. Hyphenated line breaks
    # "word-\nletter" -> "wordletter" (rejoin hyphenated words)
    new_text = HYPH_PATTERN.sub(r'\1\2', text)
    if new_text != text:
        n_hyph = len(HYPH_PATTERN.findall(text))
        counts['hyphen_rejoin'] = n_hyph
        text = new_text

    # 4b. Hyphenated space breaks: "word- letter" -> "wordletter"
    new_text = HYPH_SPACE_PATTERN.sub(r'\1\2', text)
    if new_text != text:
        n_hyph2 = len(HYPH_SPACE_PATTERN.findall(text))
        counts['hyphen_space_rejoin'] = n_hyph2
        text = new_text

    # 5. 8-for-S in abbreviation context
    new_text = EIGHT_S_PATTERN.sub(r'\1. S.', text)
    if new_text != text:
        counts['8->S_abbrev'] = len(EIGHT_S_PATTERN.findall(text))
        text = new_text

    # 6. Standalone "aud" -> "and"
    new_text = AUD_PATTERN.sub('and', text)
    if new_text != text:
        counts['aud->and'] = len(AUD_PATTERN.findall(text))
        text = new_text

    # 7. Pipe character removal
    new_text = PIPE_PATTERN.sub(' ', text)
    if new_text != text:
        counts['pipe_remove'] = len(PIPE_PATTERN.findall(text))
        text = new_text

    # 8. g. v.) -> q. v.) (OCR garble of q->g)
    new_text = GV_PATTERN.sub('q. v.)', text)
    if new_text != text:
        counts['gv->qv'] = len(GV_PATTERN.findall(text))
        text = new_text

    # 9. Missing open paren on q. v.)
    new_text = QV_NOPAREN.sub('(q. v.)', text)
    if new_text != text:
        counts['qv_paren_fix'] = len(QV_NOPAREN.findall(text))
        text = new_text

    # 10. Euro sign fixes
    for pat, repl, label in EURO_FIXES:
        new_text = pat.sub(repl, text)
        if new_text != text:
            counts[label] = len(pat.findall(text))
            text = new_text

    # 11. Specific word fixes
    for pattern, repl, label in WORD_FIXES:
        counted_sub(pattern, repl, label)

    # 12. Post-cleanup: collapse double spaces
    new_text = re.sub(r'  +', ' ', text)
    if new_text != text:
        counts['double_space'] = text.count('  ')
        text = new_text

    # 13. Post-@ reflow: isolated 'a' on its own line
    new_text = re.sub(r'\n a \n', ' a ', text)
    if new_text != text:
        counts['isolated_a_line'] = 1
        text = new_text

    return text, counts


def main():
    print("Loading corpus...")
    with open(LIVE_CORPUS, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"  {len(entries)} entries")

    total_counts = Counter()
    changed_entries = []
    change_details = []

    for entry in entries:
        old_body = entry.get("body") or ""
        if not old_body:
            continue

        new_body, counts = clean_body_extended(old_body)

        if new_body != old_body:
            entry["body"] = new_body
            changed_entries.append(entry["term"])
            total_counts.update(counts)
            change_details.append({
                "term": entry["term"],
                "fixes": dict(counts),
                "chars_changed": sum(counts.values()),
            })

    print(f"\nFixed {len(changed_entries)} / {len(entries)} entries")
    print(f"\nPattern counts:")
    for pattern, count in total_counts.most_common():
        print(f"  {pattern}: {count}")

    # Save corpus
    with open(LIVE_CORPUS, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nSaved: {LIVE_CORPUS}")

    # Write reports
    report = {
        "total_entries": len(entries),
        "entries_changed": len(changed_entries),
        "pattern_counts": dict(total_counts),
        "changes": change_details,
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Saved: {REPORT_JSON}")

    # Markdown report
    md = [
        "# OCR Artifact Cleanup Report",
        "",
        f"Applied conservative OCR fixes to {len(changed_entries)} of {len(entries)} entries.",
        "",
        "## Fix Summary",
        "",
        "| Pattern | Count | Description |",
        "|---------|-------|-------------|",
    ]

    descriptions = {
        ' @ -> a': '@ with spaces -> a',
        '@->a_mid_word': '@ between letters -> a',
        '@->a_before_lc': '@ before lowercase -> a',
        'a@->a': 'a@ -> a',
        '(@->a': '(@ -> (a',
        'tbe->the': 'b/h swap: tbe -> the',
        'witb->with': 'b/h swap: witb -> with',
        'tbat->that': 'b/h swap: tbat -> that',
        'bim->him': 'b/h swap: bim -> him',
        'bave->have': 'b/h swap: bave -> have',
        'ber->her': 'b/h swap: ber -> her',
        'hyphen_rejoin': 'Rejoin hyphenated line breaks',
        '4nd->and': 'Digit swap: 4nd -> and',
        'double_space': 'Collapse double spaces',
    }

    for pattern, count in total_counts.most_common():
        desc = descriptions.get(pattern, pattern)
        md.append(f"| {pattern} | {count} | {desc} |")

    md.extend(["", "---", ""])
    md.append(f"## Changed Entries ({len(changed_entries)} entries)")
    md.append("")
    md.append("| Term | Fixes Applied |")
    md.append("|------|--------------|")
    for d in change_details[:50]:  # Show first 50
        fixes_str = ", ".join(f"{k}({v})" for k, v in d["fixes"].items())
        md.append(f"| {d['term']} | {fixes_str} |")
    if len(change_details) > 50:
        md.append(f"| ... | ({len(change_details) - 50} more entries) |")
    md.append("")

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Saved: {REPORT_MD}")


if __name__ == "__main__":
    main()
