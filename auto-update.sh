#!/bin/bash
# Auto-update Black's Law Dictionary entries from OCR progress

set -e

# Check if checkpoint has more entries than current
python3 << 'PYEOF'
import json
import os

# Load corrected entries
try:
    with open(os.path.expanduser('~/blacks-law/blacks_entries_corrected.json'), 'r') as f:
        corrected = json.load(f)
except Exception as e:
    print(f"Could not load corrected entries: {e}")
    exit(0)

# Load current entries
try:
    with open(os.path.expanduser('~/blackslaw-dictionary/blacks_entries.json'), 'r') as f:
        current = json.load(f)
except:
    current = []

if len(corrected) > len(current):
    print(f"Updating: {len(current)} -> {len(corrected)} entries")
    with open(os.path.expanduser('~/blackslaw-dictionary/blacks_entries.json'), 'w') as f:
        json.dump(corrected, f, indent=2)
    
    # Commit and push if authenticated
    os.chdir(os.path.expanduser('~/blackslaw-dictionary'))
    os.system('git add blacks_entries.json')
    os.system(f'git commit -m "Update entries: {len(corrected)} corrected ({len(corrected)/12178*100:.1f}%)"')
    os.system('git push 2>/dev/null || echo "Push failed - may need auth"')
else:
    print(f"No update needed: {len(current)} entries")
PYEOF
