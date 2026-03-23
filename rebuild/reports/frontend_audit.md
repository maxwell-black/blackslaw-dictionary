# Frontend Code Audit (Static Analysis)

Audit of `assets/app.js`, `assets/style.css`, `index.html` — code inspection only, no browser testing.

## First Load / Welcome State

- **Status**: Fixed (Phase 4). `currentLetter = null`, no `.active` class on A button in HTML.
- Welcome state shows on load; letter buttons are neutral until clicked.
- **No issues found.**

## Letter Navigation

- `switchLetter()` correctly guards against re-selecting same letter.
- `highlightCurrentLetter()` uses `dataset.letter === currentLetter` toggle.
- Sidebar built from manifest keys.
- **No logic bugs found.**

## Search

- `normalizeForSearch()`: NFKD normalize, strip diacritics, lowercase, collapse non-alphanumeric.
- `scoreEntry()` ranking: exact=100, startsWith=80, includes=60, body=20. Reasonable tiered scoring.
- `ensureAllLoaded()` fires on first search to load all letters in parallel.
- Clearing search box restores browse mode or welcome state.
- **No issues found.**

## Deep-Link / Hash Behavior

- `hashchange` listener calls `handleDeepLink()` -> `scrollToEntry()`.
- On init, hash is parsed: extracts first char, loads that letter, renders, then scrolls after 100ms timeout.
- `jumpToEntry()` sets `window.location.hash` and scrolls with highlight animation.
- **Potential issue (browser-verify)**: If the hash doesn't match any entry (e.g., typo), the code silently does nothing — no 404 or feedback. Low severity.
- **Potential issue (browser-verify)**: `slugify()` uses NFKD normalization which might produce different slugs for some accented Latin/French terms than the original term. Cross-reference links might not match if the source term has accents.

## Cross-Reference Linking

- `linkCrossReferences()` regex: `/\b(See also|See|Vide)\s+([A-Z][A-Z\s,\-]{1,40}[A-Z])\b/g`
- **Does NOT check if target exists** as a live headword before creating the link. Clicking a dead xref scrolls nowhere.
- **Minimum 3-char match**: The regex requires `[A-Z\s,\-]{1,40}[A-Z]` which means at minimum 3 uppercase characters. This misses "See AD" or "See AT" (2-char terms).
- **Trailing comma stripping**: `cleanTerm.replace(/,\s*$/, '')` handles trailing commas but not trailing periods or semicolons.
- **Greedy capture**: The regex captures up to 40 chars of uppercase/space/comma/hyphen, which may over-capture into surrounding text.
- **Missing patterns**: Does not match "see" (lowercase), "See the title TERM", or "(q. v.)" / "(q.v.)" patterns despite the comment claiming it does.

## Source Page Links

- URL template: `https://archive.org/details/blacks-law-dictionary-2nd-edition-1910/page/n{leaf}/mode/1up`
- Leaf calculation: `var leaf = printed + 11;` — correct offset verified in prior work.
- Non-numeric page values handled with `isNaN()` guard (renders as plain text).
- **No off-by-one risk found** in the current implementation.

## Long-Entry Rendering

- `formatEntryBody()` splits on `\n{2,}` for paragraphs (correct: preserves `\n\n` paragraph breaks).
- Within each paragraph, `\n` is replaced with space (correct: joins reflow artifacts).
- Each paragraph wrapped in `<p>` tags.
- `escapeHtml()` uses DOM `textContent` -> `innerHTML` (safe against XSS).
- `stripDuplicateLeadingHeadword()` removes echo of headword at body start, preserving sense markers (v., n., adj., etc.).
- **No rendering issues found.**

## Items Requiring Browser Verification (for Prompt C)

1. Hash navigation with accented/special-character terms
2. Cross-reference links to non-existent targets (visual feedback)
3. Search performance with all 13,003 entries loaded
4. Mobile sidebar open/close on various screen sizes
5. Dark mode toggle persistence across page reloads
6. Font size adjustment at min/max boundaries
7. Very long entries (1000+ char bodies) — paragraph rendering
8. Source page links opening correctly in new tab
