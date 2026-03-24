"""Search verification script for Prompt C Operation 4.
Simulates the app.js search logic and tests 10 queries."""

import json, re, os, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def normalize_for_search(text):
    s = (text or '').lower()
    s = unicodedata.normalize('NFKD', s)
    s = re.sub(r'[\u0300-\u036f]', '', s)
    s = s.replace('\u2019', "'").replace('\u2018', "'")
    s = re.sub(r'[^a-z0-9]+', ' ', s).strip()
    return s

def score_entry(entry, query):
    term = normalize_for_search(entry.get('term', ''))
    body = normalize_for_search(entry.get('body', ''))
    if not term or not query:
        return -1
    if term == query:
        return 100
    if term.startswith(query + ' ') or term.startswith(query):
        return 80
    if query in term:
        return 60
    if query in body:
        return 20
    return -1

# Load all entries
all_entries = []
for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
    filepath = os.path.join(ROOT, 'data', f'entries_{letter.lower()}.json')
    with open(filepath) as f:
        all_entries.extend(json.load(f))

print(f"Loaded {len(all_entries)} entries")

# Test queries
test_cases = [
    {
        'query': 'mortgage',
        'expected_top': 'MORTGAGE',
        'description': 'Exact headword match'
    },
    {
        'query': 'habeas corpus',
        'expected_top': 'HABEAS CORPUS',
        'description': 'Multi-word exact match'
    },
    {
        'query': 'mort',
        'expected_top': None,
        'expected_contains': ['MORTGAGE', 'MORTGAGEE', 'MORTMAIN'],
        'description': 'Prefix matching'
    },
    {
        'query': 'negligence',
        'expected_top': 'NEGLIGENCE',
        'description': 'Exact match, long entry'
    },
    {
        'query': 'TRUST',
        'expected_top': 'TRUST',
        'description': 'Case-insensitive exact match'
    },
    {
        'query': 'bail',
        'expected_top': 'BAIL',
        'description': 'Short common term'
    },
    {
        'query': 'a priori',
        'expected_top': 'A PRIORI',
        'description': 'Latin phrase'
    },
    {
        'query': 'co heir',
        'expected_top': 'CO-HEIR',
        'expected_contains': ['CO-HEIR'],
        'description': 'Hyphenated term (CO-HEIR normalizes to "co heir")'
    },
    {
        'query': 'larcenous',
        'expected_top': 'LARCENOUS',
        'description': 'Exact match (note: LARCENY not a headword — corpus gap)'
    },
    {
        'query': 'quitclaim',
        'expected_top': None,
        'expected_contains': ['QUITCLAIM'],
        'description': 'Compound term'
    }
]

results = []
for tc in test_cases:
    query = normalize_for_search(tc['query'])
    ranked = []
    for entry in all_entries:
        s = score_entry(entry, query)
        if s >= 0:
            ranked.append((s, entry['term']))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    top_results = [r[1] for r in ranked[:10]]

    passed = True
    notes = []
    if tc.get('expected_top'):
        if top_results and top_results[0] == tc['expected_top']:
            notes.append(f'Top result correct: {tc["expected_top"]}')
        else:
            passed = False
            notes.append(f'Expected top: {tc["expected_top"]}, got: {top_results[0] if top_results else "none"}')
    if tc.get('expected_contains'):
        for exp in tc['expected_contains']:
            if exp in top_results:
                notes.append(f'Contains {exp}: yes')
            else:
                # Check if it exists anywhere in results
                all_result_terms = [r[1] for r in ranked]
                if exp in all_result_terms:
                    notes.append(f'Contains {exp}: yes (beyond top 10)')
                else:
                    passed = False
                    notes.append(f'Contains {exp}: NO — not in results')

    result = {
        'query': tc['query'],
        'description': tc['description'],
        'total_results': len(ranked),
        'top_5': top_results[:5],
        'pass': passed,
        'notes': notes
    }
    results.append(result)
    status = 'PASS' if passed else 'FAIL'
    print(f"  {status}: '{tc['query']}' — {tc['description']} — {len(ranked)} results, top: {top_results[:3]}")

output = {
    'total_entries': len(all_entries),
    'test_cases': results,
    'all_passed': all(r['pass'] for r in results),
    'search_features': {
        'exact_match': True,
        'prefix_match': True,
        'substring_match': True,
        'case_insensitive': True,
        'multi_word': True,
        'body_search': True,
        'result_limit': 80,
        'ranking': 'exact(100) > prefix(80) > substring(60) > body(20), alpha tiebreak'
    }
}

output_path = os.path.join(ROOT, 'rebuild', 'reports', 'search_verification.json')
with open(output_path, 'w') as f:
    json.dump(output, f, indent=2)
print(f"\nReport: {output_path}")
