#!/usr/bin/env python3
"""
reflow_bodies.py — Join column-width line breaks in entry bodies.

Rules:
- \n\n (double newline) = paragraph break -> preserve
- Single \n = column-width line break -> join with space
- EXCEPT preserve \n before lines starting with em-dash or numbered list markers
- Hyphenated line breaks: "word-\nlower" -> "wordlower" (remove hyphen+newline)
  BUT keep hyphen for compound words: "self-\ndefense" -> "self-defense"
- Collapse multiple spaces to single space after joining
"""
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

# Common compound-word prefixes where hyphen should be preserved
COMPOUND_PREFIXES = {
    "self", "non", "anti", "pre", "post", "co", "re", "sub", "semi",
    "over", "under", "cross", "counter", "ex", "inter", "intra",
    "multi", "out", "super", "trans", "ultra", "well", "ill", "half",
    "quasi", "pseudo", "vice", "mid", "fore", "after", "by", "mis",
    "un", "dis", "de", "bi", "tri",
}


def is_compound_hyphen(word_before):
    """Check if the word before a hyphen is a compound-word prefix."""
    w = word_before.lower().split()[-1] if word_before else ""
    return w in COMPOUND_PREFIXES


def reflow_paragraph(text):
    """Reflow a single paragraph (no double-newlines within)."""
    lines = text.split("\n")
    result = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if NEXT line should be preserved as a separate line
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            # Preserve line break before em-dash sub-entries or numbered lists
            if re.match(r"^\s*[\u2014\u2013—–-]{1,2}\s*[A-Z]", next_line) or \
               re.match(r"^\s*(\d+[\.\)]\s|[\(\[]\d+[\)\]]\s|[\(\[][a-z][\)\]]\s)", next_line):
                result.append(line)
                i += 1
                continue

        # Handle hyphenated line breaks
        if i + 1 < len(lines) and line.rstrip().endswith("-"):
            next_line = lines[i + 1]
            stripped = line.rstrip()
            # Get the word fragment before the hyphen
            word_before = stripped[:-1].split()[-1] if stripped[:-1].strip() else ""

            if next_line and next_line[0:1].islower():
                if is_compound_hyphen(word_before):
                    # Keep hyphen, remove line break: "self-\ndefense" -> "self-defense"
                    result.append(stripped)
                else:
                    # Remove hyphen and join: "judg-\nment" -> "judgment"
                    result.append(stripped[:-1])
                i += 1
                # Prepend next line content to following iteration
                if i < len(lines):
                    lines[i] = next_line
                continue

        result.append(line)
        i += 1

    # Join all lines with space
    joined = " ".join(result)
    # Collapse multiple spaces
    joined = re.sub(r"  +", " ", joined)
    return joined.strip()


def reflow_body(body):
    """Reflow an entire entry body, preserving paragraph breaks."""
    if not body:
        return body

    # Split on paragraph breaks (double newline)
    paragraphs = re.split(r"\n\n+", body)

    # Reflow each paragraph
    reflowed = [reflow_paragraph(p) for p in paragraphs]

    return "\n\n".join(reflowed)


def main():
    corpus_path = REPO / "blacks_entries.json"
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        test_mode = True
    else:
        test_mode = False

    with corpus_path.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    test_terms = ["A POSTERIORI", "A QUO", "BAIL", "BADGE", "ABSTRACT", "MORTGAGE"]
    by_term = {e["term"]: e for e in entries}

    if test_mode:
        print("=== REFLOW TEST MODE ===\n")
        for term in test_terms:
            e = by_term.get(term)
            if not e:
                print(f"--- {term}: NOT FOUND ---\n")
                continue
            old = e["body"] or ""
            new = reflow_body(old)
            print(f"--- {term} ---")
            print(f"BEFORE:\n{old[:500]}")
            print(f"\nAFTER:\n{new[:500]}")
            print()
        return

    # Full corpus reflow
    changed = 0
    for entry in entries:
        old = entry.get("body") or ""
        new = reflow_body(old)
        if new != old:
            entry["body"] = new
            changed += 1

    print(f"Reflowed {changed} / {len(entries)} entries")

    with corpus_path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Written to {corpus_path}")


if __name__ == "__main__":
    main()
