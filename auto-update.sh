#!/bin/bash
# Auto-update Black's Law Dictionary entries from OCR progress

set -e

cd ~/blacks-law

# Check if checkpoint has more entries than current
python3 << 'PYEOF'
import json
import os

# Load checkpoint
try:
    with open('blacks_correction_checkpoint.json', 'r') as f:
        checkpoint = json.load(f)
    corrected = checkpoint.get('corrected', [])
except:
    print("Could not load checkpoint")
    exit(0)

# Load current entries
try:
    with open('../blackslaw-dictionary/blacks_entries.json', 'r') as f:
        current = json.load(f)
except:
    current = []

if len(corrected) > len(current):
    print(f"Updating: {len(current)} -> {len(corrected)} entries")
    with open('../blackslaw-dictionary/blacks_entries.json', 'w') as f:
        json.dump(corrected, f, indent=2)
    
    # Commit and push if authenticated
    os.chdir('../blackslaw-dictionary')
    os.system('git add blacks_entries.json')
    os.system(f'git commit -m "Update entries: {len(corrected)} corrected ({len(corrected)/12178*100:.1f}%)"')
    os.system('git push 2>/dev/null || echo "Push failed - may need auth"')
else:
    print(f"No update needed: {len(current)} entries")
PYEOF
