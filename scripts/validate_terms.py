#!/usr/bin/env python3
"""
validate_terms.py - Validate blacks_entries.json headwords against reference wordlist.
Flag terms that don't match and suggest corrections.
"""

import json
from difflib import get_close_matches
from pathlib import Path

def main():
    print("Loading reference wordlist...")
    with open('scripts/reference_terms.txt') as f:
        reference = set(line.strip().upper() for line in f if line.strip())
    
    print(f"  Loaded {len(reference)} reference terms")
    
    print("\nLoading entries...")
    with open('blacks_entries.json') as f:
        entries = json.load(f)
    
    print(f"  Loaded {len(entries)} entries")
    
    flagged = []
    
    print("\nValidating terms...")
    for i, entry in enumerate(entries):
        term = entry['term'].strip().rstrip('.,;:')
        
        # Skip abbreviations (e.g. A.D., U.S.)
        if len(term) <= 3:
            continue
        
        # Skip if exact match
        if term.upper() in reference:
            continue
        
        # Get fuzzy suggestions
        suggestions = get_close_matches(
            term.upper(),
            reference,
            n=3,
            cutoff=0.7
        )
        
        # Get body first line for context
        body_first = entry['body'].strip().split('\n')[0] if entry['body'] else ''
        
        flagged.append({
            'index': i,
            'term': term,
            'suggestions': suggestions,
            'body_start': body_first[:120]
        })
        
        if len(flagged) % 500 == 0:
            print(f"  Processed {i}/{len(entries)}, flagged {len(flagged)} so far...")
    
    print(f"\n✅ Flagged {len(flagged)} of {len(entries)} terms ({len(flagged)/len(entries)*100:.1f}%)")
    
    # Write JSON report
    with open('scripts/validation_report.json', 'w') as f:
        json.dump(flagged, f, indent=2)
    
    # Write human-readable summary
    with open('scripts/validation_report.txt', 'w') as f:
        f.write(f"OCR Validation Report\n")
        f.write(f"=====================\n\n")
        f.write(f"Total entries: {len(entries)}\n")
        f.write(f"Flagged terms: {len(flagged)}\n")
        f.write(f"Clean terms: {len(entries) - len(flagged)}\n\n")
        f.write(f"Flagged Terms:\n")
        f.write(f"-------------\n\n")
        
        for item in flagged:
            f.write(f"[{item['index']}] {item['term']}\n")
            if item['suggestions']:
                f.write(f"  -> suggestions: {', '.join(item['suggestions'])}\n")
            f.write(f"  body: {item['body_start']}\n\n")
    
    print(f"\nReports written:")
    print(f"  - scripts/validation_report.json (machine-readable)")
    print(f"  - scripts/validation_report.txt (human-readable)")
    
    # Show some examples
    print(f"\nSample flagged terms:")
    for item in flagged[:10]:
        print(f"  [{item['index']}] {item['term']}")
        if item['suggestions']:
            print(f"      -> {', '.join(item['suggestions'])}")

if __name__ == '__main__':
    main()
