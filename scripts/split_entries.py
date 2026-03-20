#!/usr/bin/env python3
"""
split_entries.py - Split blacks_entries.json into letter-based chunks for lazy loading.

Usage:
    python3 scripts/split_entries.py

This creates:
    - data/manifest.json (metadata about each chunk)
    - data/entries_a.json through data/entries_z.json (letter-based chunks)
"""

import json
import os
from pathlib import Path

def split_entries():
    # Load all entries
    with open("blacks_entries.json", "r") as f:
        entries = json.load(f)
    
    print(f"Splitting {len(entries)} entries...")
    
    # Create data directory
    os.makedirs("data", exist_ok=True)
    
    # Group entries by first letter
    letter_groups = {}
    for entry in entries:
        first_letter = entry['term'][0].upper() if entry['term'] else 'A'
        if first_letter not in letter_groups:
            letter_groups[first_letter] = []
        letter_groups[first_letter].append(entry)
    
    # Create manifest and write letter files
    manifest = {}
    for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
        letter_entries = letter_groups.get(letter, [])
        if letter_entries:
            filename = f"entries_{letter.lower()}.json"
            filepath = f"data/{filename}"
            
            # Write letter file
            with open(filepath, "w") as f:
                json.dump(letter_entries, f)
            
            manifest[letter] = {
                "file": f"data/{filename}",
                "count": len(letter_entries)
            }
            print(f"  {letter}: {len(letter_entries):>4} entries")
    
    # Write manifest
    with open("data/manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\n✅ Created {len(manifest)} letter files in data/")
    print(f"   manifest.json updated")

if __name__ == '__main__':
    split_entries()
