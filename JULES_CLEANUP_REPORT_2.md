# Jules Cleanup Report 2

## Methodology Notes
- **Headword/body alignment:** Extracted first ALL-CAPS token from the body. Case A (headword is strict prefix) was applied directly to `editorial_overlay.json` by updating the `term` field. Case B (morphologically unrelated) and Case C (Levenshtein distance 1) were logged to `review_queue.json`.
- **Sub-entry parent mismatch:** Detected sub-entries using the `—[Subterm].` pattern. If multiple sub-entries shared a stem not matching the parent headword, the entry was flagged in `review_queue.json`.
- **Embedded maxim detection:** Searched the end of entry bodies for Latin phrases followed by English translations containing "shall be" or "is to be", plus a citation. Flagged candidates.
- **OCR residual sweep:** High-confidence replacements (`Oustomary`, etc.) were directly applied and added to `body_corrections.json`. Medium-confidence patterns (mixed case, stray `<` or `)`) were logged with 5 words of context to the review queue.
- **Pipeline Constraints:** Invariants were preserved. `blacks_entries.json` was treated as strictly read-only. Retypes for Case A were applied via the overlay, and body text edits were isolated to `body_corrections.json`.

## Counts
- Case A (prefix retype) applied: 1
- Case B (boundary failure) flagged: 80
- Case C (OCR slip) flagged: 42
- Sub-entry parent mismatches flagged: 25
- Embedded maxims flagged: 6
- High-confidence OCR fixes applied: 30
- Medium-confidence OCR issues flagged: 784
