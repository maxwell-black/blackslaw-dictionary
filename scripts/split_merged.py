#!/usr/bin/env python3
"""
split_merged.py - Split entries containing multiple headwords into separate entries.

This script identifies entries where the body contains embedded headwords
(indicating merged content) and splits them into separate entries.
"""

import json
import re
import sys
from pathlib import Path

def find_embedded_headwords(body, main_term):
    """Find all embedded headwords in a body text."""
    # Pattern: 2+ newlines followed by all-caps word(s) followed by period or newline
    pattern = r'\n\n([A-Z][A-Z\s\'\-]{2,})(?:\.|\n)'
    matches = list(re.finditer(pattern, body))
    
    headwords = []
    for m in matches:
        word = m.group(1).strip()
        # Validate: 1-5 words, all caps, reasonable length
        words = word.split()
        if 1 <= len(words) <= 5 and len(word) > 3:
            # Skip if it's the same as main term
            if word.replace(' ', '').replace("'", '').replace('-', '') !=                main_term.replace(' ', '').replace("'", '').replace('-', ''):
                headwords.append((m.start(), m.end(), word))
    
    return headwords

def split_entry(entry):
    """Split a merged entry into separate entries."""
    term = entry['term']
    body = entry['body']
    
    headwords = find_embedded_headwords(body, term)
    
    if len(headwords) <= 1:
        return [entry]  # No splitting needed
    
    new_entries = []
    
    # First entry: original term, content up to first embedded headword
    first_split = headwords[0][0]
    new_entries.append({
        'term': term,
        'body': body[:first_split].strip()
    })
    
    # Subsequent entries: each embedded headword becomes a new entry
    for i, (start, end, headword) in enumerate(headwords):
        if i == len(headwords) - 1:
            # Last headword: content from here to end
            content = body[start:].strip()
        else:
            # Content from this headword to next
            next_start = headwords[i + 1][0]
            content = body[start:next_start].strip()
        
        # Clean up the headword - remove any trailing description
        headword_clean = headword.split('\n')[0].strip()
        
        new_entries.append({
            'term': headword_clean,
            'body': content
        })
    
    return new_entries

def main():
    input_file = Path('blacks_entries.json')
    output_file = Path('blacks_entries_split.json')
    
    print(f"Loading {input_file}...")
    with open(input_file, 'r') as f:
        entries = json.load(f)
    
    print(f"Processing {len(entries)} entries...")
    
    new_entries = []
    split_count = 0
    total_new = 0
    
    for entry in entries:
        split = split_entry(entry)
        if len(split) > 1:
            split_count += 1
            total_new += len(split)
        new_entries.extend(split)
    
    print(f"\nResults:")
    print(f"  Original entries: {len(entries)}")
    print(f"  Split entries: {split_count}")
    print(f"  New total entries: {len(new_entries)}")
    print(f"  New entries created: {len(new_entries) - len(entries)}")
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(new_entries, f, indent=2)
    
    print(f"\nSaved to {output_file}")
    
    # Write summary
    summary = {
        'original_count': len(entries),
        'split_entries': split_count,
        'new_count': len(new_entries),
        'entries_created': len(new_entries) - len(entries)
    }
    
    with open('split_summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    print("Summary saved to split_summary.json")

if __name__ == '__main__':
    main()
