# Browser Verification Checklist — Prompt C

Items requiring a human with a browser. Test at both desktop (1200px+) and mobile (375px) widths.

## First Load
- [ ] Page shows welcome state: "Select a letter from the sidebar to begin browsing"
- [ ] No letter is preselected/highlighted in the letter rail
- [ ] Loading spinner appears briefly, then welcome state replaces it
- [ ] Search input is visible and has placeholder "Search 12,900 entries…"
- [ ] No JS errors in console on initial load

## Letter Navigation
- [ ] Click "A" — entries for A appear, "A" button highlighted in letter rail
- [ ] Click "M" — entries for M appear, "A" is deselected, "M" is highlighted
- [ ] Content scrolls to top when switching letters
- [ ] Loading indicator shows briefly while letter data fetches (on first load of each letter)
- [ ] Click "X" — only 3 entries shown, renders cleanly without excess whitespace

## Search
- [ ] Type "mortgage" — MORTGAGE appears as first result
- [ ] Type "habeas" — HABEAS CORPUS appears in results
- [ ] Type "MORT" — prefix results include MORTGAGE, MORTGAGEE, etc.
- [ ] Type "a priori" — A PRIORI appears as first result
- [ ] Search is case-insensitive (try "Bail" and "BAIL" and "bail")
- [ ] Press Enter in search — first result is highlighted/scrolled to
- [ ] Press Escape — search clears, returns to current letter view
- [ ] Type "a" — result count shows a number, results are capped at 80, truncation notice visible
- [ ] Clear search — returns to letter browse or welcome state

## Cross-references
- [ ] Navigate to letter A, find entry for ABANDON — "See ABANDONMENT" should be a clickable link
- [ ] Click the ABANDONMENT link — navigates to letter A, scrolls to ABANDONMENT entry, briefly highlights it
- [ ] Find an entry with "See DIVORCE" — link navigates across letter boundary (A→D)
- [ ] Find an entry with "(q. v.)" — preceding term should be linked if it's a valid headword
- [ ] Find an entry with unresolvable cross-ref (e.g., "See ABJURBATION") — should appear in small-caps but NOT be a clickable link
- [ ] No broken links: clicking any xref should navigate to an existing entry

## IA Source Links
- [ ] Navigate to MORTGAGE — source page links "793, 794" should appear below headword
- [ ] Click a source page link — opens archive.org in new tab at correct page
- [ ] Source links are visually subtle (small font, muted color, don't compete with definition)
- [ ] Navigate to TRUST — source pages "1175, 1176, 1177" shown and link correctly

## Deep Linking
- [ ] Navigate directly to `#mortgage` — MORTGAGE entry loads, letter M selected
- [ ] Navigate to `#nonexistent-term` — shows letter view (no blank page or JS error)
- [ ] After clicking an entry's cross-reference, the URL hash updates
- [ ] Browser back/forward works after hash navigation

## Entry Rendering
- [ ] NEGLIGENCE (long entry, 9500+ chars): paragraphs are visually separated, no wall of text
- [ ] BAIL (16 em-dash subentries): subentry headwords (—Bail absolute., —Bail-bond., etc.) are bold
- [ ] BADGE: "BADGE OF FRAUD" subentry paragraph starts on new paragraph, readable
- [ ] ABSTRACT: body renders correctly (manually reconstructed entry)
- [ ] Short entries (e.g., AEGYLDE, 138 chars): clean, no excess whitespace
- [ ] No `<br>` tags visible in any rendered entry text
- [ ] No raw HTML or corpus text injected unsanitized

## Typography
- [ ] Body text is comfortable to read at normal zoom
- [ ] Line-height feels open, not cramped (~1.55)
- [ ] Entry headwords are bold and slightly larger than body text
- [ ] Entries are visually separated by subtle border lines
- [ ] Source-page metadata is small and muted
- [ ] Content doesn't stretch beyond ~720px on wide screens

## Mobile (resize to ~375px)
- [ ] Text doesn't overflow the viewport (no horizontal scrolling)
- [ ] Letter rail becomes horizontal top bar, scrollable
- [ ] Hamburger menu button appears — opens sidebar with letter counts
- [ ] Touch targets (letter buttons, search, links) are adequate size
- [ ] Entry text has adequate margin from screen edges (16px)
- [ ] Cross-reference links and source-page links are tappable

## Dark Mode
- [ ] Click moon icon — switches to dark mode
- [ ] Text is readable with good contrast in dark mode
- [ ] Cross-reference links visible in dark mode
- [ ] Search box has visible background (not transparent)
- [ ] Toggle back — returns to light mode
- [ ] Setting persists across page reload

## Print (Ctrl+P)
- [ ] Navigation, search, letter rail are hidden
- [ ] Only entry content visible
- [ ] Text is serif, black on white
- [ ] No background colors in print

## Suppressed Entries
- [ ] Search for "I N" — should NOT appear as a headword result
- [ ] Search for "THEODOSIANUS" — should NOT appear
- [ ] Navigate letter Y — "Y.)" should NOT appear as an entry

## Console
- [ ] Open DevTools console, navigate through several letters and entries
- [ ] Verify no JS errors logged
- [ ] Verify no 404s for data/asset fetches
