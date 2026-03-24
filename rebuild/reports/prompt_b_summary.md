# Prompt B — Corpus & Overlay Fixes Summary

## Operations Performed

### Op 0: Validation Blockers (commit 713d937)
- THEODOSIANUS (BLD2-12553): body "|" → fragment_artifact (scan artifact, no recoverable text)
- Y.) (BLD2-13601): body ".)" → fragment_artifact (garbled page furniture)

### Op 1: Boundary/Fragment Cleanup (commit e1a0641)
10 entries suppressed as fragment_artifact:
- GQ, R A, R.G, R.P: abbreviation table / page number scan artifacts
- PROCURATORES, OMITT, IMPERTIN, EXH, LAU: truncated headword fragments
- CUILIBET: garbled segmentation spillover

### Op 2: OCR Artifact Cleanup (commit a3affdd)
Enhanced clean_body_ocr.py with additional safe patterns:
- `&@` → `a` (10 fixes), `@&` → `a` (3 fixes), `(@` → `(a` (2 fixes)
- Isolated `a` on own line from @→a cleanup (2 fixes: COMMON, ESTOVERS)
- Total per-run OCR fixes: 168 entries (was 155)

### Op 3: Body-Oracle Pass (commit 4fb448d)
Analyzed 1,773 legacy_retained entries:
- **91 duplicate suppressions** → legacy_duplicate (compound headword fragments where the headword was just the first word of a compound term, e.g., ALE for ALE SILVER)
- **2 headword corrections** → headword_corrected:
  - BURG → BURGH (body echoes "BURGH. A term anciently applied...")
  - STATU → STATUS (body echoes "STATUS. The status of a person...")
- Detailed results: rebuild/reports/body_oracle_results.json

### Op 4: Residual Structural Fixes (commit a3affdd)
- COMMON: Fixed reflow artifact `\n a \n` → ` a ` via clean_body_ocr.py pattern
- ESTOVERS: Fixed via body_corrections.json:
  - Reflow artifact: joined `a \nmensa` → `a mensa`
  - OCR: `ct` → `et` (Latin "a mensa et thoro")
  - Scan artifact: removed `|` column separator
  - OCR: `out.of` → `out of`, `furniture. of` → `furniture of`

### Build Report Enhancement (commit a3affdd)
Enhanced generate_live_corpus_v3.py to include:
- previous_live_count, new_live_count, delta
- counts_by_entry_type for both included AND excluded types
- changes_this_build diff list
- Human-readable summary paragraph

## Count Summary

| Metric | Before Prompt B | After Prompt B | Delta |
|--------|----------------|----------------|-------|
| Live entries | 13,003 | 12,900 | -103 |
| Overlay total | 13,641 | 13,641 | 0 |
| fragment_artifact | 237 | 249 | +12 |
| legacy_duplicate | 81 | 172 | +91 |
| headword_corrected | 9 | 11 | +2 |
| body_corrections | 1 | 2 | +1 |

Delta explained: -103 = -91 (duplicate suppressions) - 12 (fragment suppressions) + 2 (headword corrections, net -2 legacy_retained +2 headword_corrected, but the corrected entries were already counted in legacy_retained, so net change is 0 for corrections). Wait — corrections don't change count since they move from legacy_unresolved→headword_corrected (both promotable/live). The -103 comes from -91 duplicates suppressed, -12 fragments suppressed = -103.

## Residual Issue Counts

| Issue Class | Prompt A Count | After Prompt B | Notes |
|-------------|---------------|----------------|-------|
| Boundary issues | 159 | 150 | 9 suppressed; remainder are legitimate variant/Latin headword echoes |
| OCR artifacts | 285 | 121 | 95 remaining @, 26 digit-in-word; context-dependent, need manual review |
| Near-duplicates | 97 | ~6 | 91 suppressed via body-oracle; remainder have dissimilar bodies |
| Near-empty bodies | 153 | 73 | Reduced by fragment/duplicate suppression |
| Unresolved xrefs | 161 | 142 | Some resolved by body-oracle headword corrections |
| Reflow artifacts | 2 | 0 | Both fixed (COMMON, ESTOVERS) |
| Suspicious headwords | 17 | ~15 | 2 corrected (BURG→BURGH, STATU→STATUS) |

## Commits

1. `713d937` — Op 0: suppress 2 validation blockers
2. `4fb448d` — Op 3: body-oracle pass (91 duplicates, 2 corrections)
3. `e1a0641` — Op 1: suppress 10 fragment artifacts
4. `a3affdd` — Op 2+4: OCR cleanup, reflow fixes, build report upgrade
