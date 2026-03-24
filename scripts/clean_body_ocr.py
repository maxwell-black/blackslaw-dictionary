#!/usr/bin/env python3
"""
clean_body_ocr.py — Fix systematic OCR character errors in entry bodies.

Safe fixes applied:
- " @ " -> " a " (standalone @ with spaces)
- "@" -> "a" when at word boundary before lowercase letter
- "a@ " -> "a " (spurious @ after a)
- "@b " -> "ab " at word boundary
- "&@ " -> "a " and " @& " -> " a " (garbled ampersand+at for 'a')
- "(@ " -> "(a " (@ after opening paren)
- "4nd" -> "and", "4ll" -> "all", "4n " -> "an ", "4s " -> "as ", "4t " -> "at "
- Isolated 'a' on its own line from @->a on page breaks
- Double spaces -> single space
"""
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent


def clean_body(body):
    """Apply OCR fixes to a single body string."""
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

    # @ fixes (order matters — specific patterns before general)
    counted_sub(r'a@\s', 'a ', 'a@->a')
    counted_sub(r'@b\b', 'ab', '@b->ab')
    # &@ and @& are garbled OCR for 'a' (ampersand+at or at+ampersand)
    counted_sub(r'&@\s', 'a ', '&@->a')
    counted_sub(r'\s@&\s', ' a ', '@&->a')
    counted_sub(r'\s@\s', ' a ', ' @ -> a')
    # @ after opening paren: "(@ word" -> "(a word"
    counted_sub(r'\(@\s', '(a ', '(@->a')
    # @ as standalone "a" before a word: space-@-word -> space-a-space-word
    counted_sub(r'(?<=\s)@(?=[a-z])', 'a ', '@->a (before lowercase)')
    counted_sub(r'^@(?=[a-z])', 'a ', '@->a (start of text)')

    # 4-for-a fixes — only when NOT preceded by a digit or § (to avoid "§ 4" or "14nd")
    counted_sub(r'(?<![0-9§])4nd\b', 'and', '4nd->and')
    counted_sub(r'(?<![0-9§])4ll\b', 'all', '4ll->all')
    counted_sub(r'(?<![0-9§])4n\s', 'an ', '4n->an')
    counted_sub(r'(?<![0-9§])4s\s', 'as ', '4s->as')
    counted_sub(r'(?<![0-9§])4t\s', 'at ', '4t->at')

    # Post-@ reflow cleanup: fix isolated 'a' left between paragraph breaks
    # when @ was on its own line between \n\n breaks, @->a leaves \n a \n
    counted_sub(r'\n a \n', ' a ', 'isolated-a-line')

    # Collapse double spaces
    counted_sub(r'  +', ' ', 'double spaces')

    return text, counts


def main():
    corpus_path = REPO / "blacks_entries.json"
    test_mode = len(sys.argv) > 1 and sys.argv[1] == "--test"

    with corpus_path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    if test_mode:
        test_terms = ["A QUO", "MORTGAGE", "BAIL", "ABSTRACT"]
        by_term = {e["term"]: e for e in entries}
        print("=== OCR CLEANUP TEST MODE ===\n")
        for term in test_terms:
            e = by_term.get(term)
            if not e:
                print(f"--- {term}: NOT FOUND ---\n")
                continue
            old = e["body"] or ""
            new, counts = clean_body(old)
            if counts:
                print(f"--- {term} ---")
                print(f"  Fixes: {counts}")
                # Show context around changes
                for i, (oc, nc) in enumerate(zip(old.split(), new.split())):
                    if oc != nc:
                        start = max(0, i - 3)
                        end = min(len(old.split()), i + 4)
                        print(f"  BEFORE: ...{' '.join(old.split()[start:end])}...")
                        print(f"  AFTER:  ...{' '.join(new.split()[start:end])}...")
                print()
            else:
                print(f"--- {term}: no fixes needed ---\n")
        return

    # Full corpus
    total_counts = {}
    changed = 0
    for entry in entries:
        old = entry.get("body") or ""
        new, counts = clean_body(old)
        if new != old:
            entry["body"] = new
            changed += 1
            for k, v in counts.items():
                total_counts[k] = total_counts.get(k, 0) + v

    print(f"Fixed {changed} / {len(entries)} entries")
    print(f"\nPattern counts:")
    for pattern, count in sorted(total_counts.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")

    with corpus_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWritten to {corpus_path}")


if __name__ == "__main__":
    main()
