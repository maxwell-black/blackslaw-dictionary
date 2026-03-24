"""Cross-reference verification script for Prompt C Operation 1.
Scans all live corpus entries, finds cross-reference patterns,
checks resolution against the headword set, and reports results."""

import json, re, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load headword index
with open(os.path.join(ROOT, 'assets', 'headwords.json')) as f:
    headwords = json.load(f)
headword_set = set(h.upper() for h in headwords)

XREF_EXCLUDE = {
    'A','AN','AS','AT','BE','BY','DO','GO','HE','IF','IN','IS','IT',
    'ME','MY','NO','OF','ON','OR','SO','TO','UP','WE','THE','AND',
    'BUT','FOR','NOR','NOT','YET','ALL','ANY','ARE','HIS','HER','HAS',
    'HAD','WAS','DID','CAN','MAY','ITS','OUR','OWN','USE','WAY','OUT',
    'SUPRA','INFRA','ANTE','POST','ALSO','THOSE','TITLES','THAT',
}

def slugify(term):
    import unicodedata
    s = term.strip().lower()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[\u0300-\u036f]', '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s

def try_resolve(raw_term):
    """Try progressive word shortening to find a headword match."""
    cleaned = raw_term.strip().rstrip(',;: ')
    if not cleaned or len(cleaned) < 2:
        return None
    upper = cleaned.upper()
    if upper in XREF_EXCLUDE:
        return None
    words = cleaned.split()
    for length in range(len(words), 0, -1):
        candidate = ' '.join(words[:length]).upper()
        if len(candidate) < 2:
            continue
        if candidate in XREF_EXCLUDE:
            continue
        if candidate in headword_set:
            return candidate
    return None

def try_resolve_backref(raw_term, prefer_right=True):
    """Try contiguous subsequences for back-reference resolution.
    prefer_right=True iterates right-to-left (for q.v.)
    prefer_right=False iterates left-to-right (for which see)"""
    cleaned = raw_term.strip().rstrip(',;:. ')
    if not cleaned:
        return None
    words = cleaned.split()
    for length in range(len(words), 0, -1):
        if prefer_right:
            positions = range(len(words) - length, -1, -1)
        else:
            positions = range(0, len(words) - length + 1)
        for start in positions:
            candidate = ' '.join(words[start:start+length]).upper()
            if len(candidate) < 2:
                continue
            if candidate in XREF_EXCLUDE:
                continue
            if candidate in headword_set:
                return candidate
    return None

# Scan all entries
results = {
    'patterns': {},
    'summary': {},
    'sample_resolved': [],
    'sample_unresolved': [],
    'sample_qv_resolved': [],
    'sample_qv_unresolved': [],
    'sample_whichsee_resolved': [],
}

total_forward = 0
resolved_forward = 0
unresolved_forward = 0
total_qv = 0
resolved_qv = 0
total_ws = 0
resolved_ws = 0

for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    filepath = os.path.join(ROOT, 'data', f'entries_{letter.lower()}.json')
    if not os.path.exists(filepath):
        continue
    with open(filepath) as f:
        entries = json.load(f)
    for entry in entries:
        body = entry.get('body', '') or ''

        # Pattern 1: Forward references (See/see/Vide/Same as + UPPERCASE)
        for m in re.finditer(r'\b(See also|see also|See|see|Vide|vide|Same as|same as)\s+([A-Z][A-Z \-,;\'\u2019]{0,80})', body):
            prefix = m.group(1)
            captured = m.group(2).rstrip(',;: ')
            total_forward += 1

            # Handle semicolon-separated
            if ';' in captured:
                parts = [p.strip() for p in captured.split(';') if p.strip()]
                for part in parts:
                    match = try_resolve(part)
                    if match:
                        resolved_forward += 1
                        if len(results['sample_resolved']) < 15:
                            results['sample_resolved'].append({
                                'entry': entry['term'],
                                'pattern': f'{prefix} {part}',
                                'resolved_to': match
                            })
                    else:
                        unresolved_forward += 1
                        if len(results['sample_unresolved']) < 15:
                            results['sample_unresolved'].append({
                                'entry': entry['term'],
                                'pattern': f'{prefix} {part}',
                                'reason': 'no headword match'
                            })
            else:
                match = try_resolve(captured)
                if match:
                    resolved_forward += 1
                    if len(results['sample_resolved']) < 15:
                        results['sample_resolved'].append({
                            'entry': entry['term'],
                            'pattern': f'{prefix} {captured}',
                            'resolved_to': match
                        })
                else:
                    unresolved_forward += 1
                    if len(results['sample_unresolved']) < 15:
                        results['sample_unresolved'].append({
                            'entry': entry['term'],
                            'pattern': f'{prefix} {captured}',
                            'reason': 'no headword match'
                        })

        # Pattern 2: q.v. back-references (prefer_right=True)
        for m in re.finditer(r'\b([A-Za-z][\w\'-]*(?:\s+[A-Za-z][\w\'-]*){0,3}),?\s*\(q\.\s*v\.\)', body):
            preceding = m.group(1)
            total_qv += 1
            match = try_resolve_backref(preceding, prefer_right=True)
            if match:
                resolved_qv += 1
                if len(results['sample_qv_resolved']) < 10:
                    results['sample_qv_resolved'].append({
                        'entry': entry['term'],
                        'pattern': f'{preceding} (q.v.)',
                        'resolved_to': match
                    })
            else:
                if len(results['sample_qv_unresolved']) < 10:
                    results['sample_qv_unresolved'].append({
                        'entry': entry['term'],
                        'pattern': f'{preceding} (q.v.)',
                        'reason': 'no headword match'
                    })

        # Pattern 3: "which see" back-references (prefer_right=True)
        for m in re.finditer(r'\b([A-Za-z][\w\'-]*(?:\s+[A-Za-z][\w\'-]*){0,4}),?\s+which see\b', body, re.I):
            preceding = m.group(1)
            total_ws += 1
            match = try_resolve_backref(preceding, prefer_right=True)
            if match:
                resolved_ws += 1
                if len(results['sample_whichsee_resolved']) < 10:
                    results['sample_whichsee_resolved'].append({
                        'entry': entry['term'],
                        'pattern': f'{preceding}, which see',
                        'resolved_to': match
                    })

results['summary'] = {
    'headword_count': len(headword_set),
    'forward_references': {
        'total_patterns': total_forward,
        'resolved': resolved_forward,
        'unresolved': unresolved_forward,
        'resolution_rate': f'{resolved_forward/max(total_forward,1)*100:.1f}%'
    },
    'qv_references': {
        'total_patterns': total_qv,
        'resolved': resolved_qv,
        'unresolved': total_qv - resolved_qv,
        'resolution_rate': f'{resolved_qv/max(total_qv,1)*100:.1f}%'
    },
    'which_see_references': {
        'total_patterns': total_ws,
        'resolved': resolved_ws,
        'unresolved': total_ws - resolved_ws,
        'resolution_rate': f'{resolved_ws/max(total_ws,1)*100:.1f}%'
    },
    'total_all_patterns': total_forward + total_qv + total_ws,
    'total_resolved': resolved_forward + resolved_qv + resolved_ws,
    'overall_resolution_rate': f'{(resolved_forward+resolved_qv+resolved_ws)/max(total_forward+total_qv+total_ws,1)*100:.1f}%'
}

# Write report
output_path = os.path.join(ROOT, 'rebuild', 'reports', 'xref_verification.json')
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"Cross-reference verification complete.")
print(f"  Forward refs: {resolved_forward}/{total_forward} resolved ({results['summary']['forward_references']['resolution_rate']})")
print(f"  q.v. refs: {resolved_qv}/{total_qv} resolved ({results['summary']['qv_references']['resolution_rate']})")
print(f"  which-see refs: {resolved_ws}/{total_ws} resolved ({results['summary']['which_see_references']['resolution_rate']})")
print(f"  Overall: {resolved_forward+resolved_qv+resolved_ws}/{total_forward+total_qv+total_ws} ({results['summary']['overall_resolution_rate']})")
print(f"  Report: {output_path}")
