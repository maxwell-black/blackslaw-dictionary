# Validation Hardening Summary

`scripts/validate_rebuild.py` rewritten with structured hard-fail and warning-level checks.

## Hard-Fail Invariants (exit 1)

- Malformed JSON / unexpected structure
- Missing required fields (`term`, `body`, `source_pages`)
- Duplicate terms in live corpus
- Empty, whitespace-only, or punctuation-only bodies
- Manifest/split count mismatches (with `--full`)
- Overlay accounting failures (with `--full`)
- Unexplained count deltas from previous build (with `--full`)
- Split file content disagreeing with live corpus (with `--full`)

## Warning-Level Checks (report only)

| Check | Current Count |
|-------|---------------|
| Headword/body boundary | 159 |
| Unresolved cross-references | 161 |
| OCR artifacts (@, digit-in-word) | 285 |
| source_pages out of range | 8 |
| Residual reflow | 2 |
| Garbled body starts | 1 |

## Count-Delta Infrastructure

- After each successful validation, the live count is saved to `rebuild/out/.prev_live_count`
- On next validation with `--full`, if the count changed and the build report doesn't account for it, validation fails
- This prevents silent entry loss or gain between builds

## Current Hard Failures (2)

| Term | Body | Reason |
|------|------|--------|
| THEODOSIANUS | `\|` | punctuation-only |
| Y.) | `.` | punctuation-only |

These are real data quality issues to fix in a future data run (Prompt B scope).

## Usage

```bash
# Basic validation (structure + bodies + duplicates)
python scripts/validate_rebuild.py blacks_entries.json

# Full validation (adds overlay/split/delta checks)
python scripts/validate_rebuild.py blacks_entries.json --full

# Validate live candidate before promotion
python scripts/validate_rebuild.py rebuild/out/blacks_entries.live_candidate.json --full
```
