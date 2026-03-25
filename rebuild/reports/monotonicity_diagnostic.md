# Monotonicity Break Diagnostic

## Diagnosis: **small_jump_noise**

3190 of 3854 breaks are jumps of 1-10 pages. Likely a combination of two-column interleaving and minor source_pages assignment imprecision. Not individually actionable.

## Statistics

- Total breaks: 3854
- Page type: leaf_numbers (A section starts at page 10)
- Median backward jump: 9 pages
- Mean backward jump: 10.1 pages

## Jump Size Distribution

| Range | Count |
|-------|-------|
| 1-5 pages | 0 |
| 6-10 pages | 3190 |
| 11-20 pages | 655 |
| 21-50 pages | 2 |
| 51-100 pages | 2 |
| 100+ pages | 5 |

## Breaks by Letter

| Letter | Breaks |
|--------|--------|
| A | 299 |
| B | 230 |
| C | 411 |
| D | 153 |
| E | 202 |
| F | 290 |
| G | 196 |
| H | 359 |
| I | 221 |
| J | 44 |
| L | 91 |
| M | 236 |
| N | 39 |
| O | 24 |
| P | 181 |
| Q | 17 |
| R | 251 |
| S | 263 |
| T | 101 |
| U | 82 |
| V | 91 |
| W | 62 |
| Z | 11 |

## Large Breaks (>50 pages) — Investigate These

| Headword | Pages | After | After Pages | Jump |
|----------|-------|-------|-------------|------|
| LR | 691 | LOTHERWITE | 750 | -59 |
| MZC-BURGH | 755 | MUNDBYRD | 808 | -53 |
| SE | 589 | SCUTAGE | 1061, 1062 | -473 |
| ZEDILITUM EDICTUM | 45 | ZANJERO | 1249 | -1204 |
| ZEFESN | 45 | ZANJERO | 1249 | -1204 |
| ZEGROTO | 45 | ZANJERO | 1249 | -1204 |
| ZEGYLDE | 45 | ZANJERO | 1249 | -1204 |

## Recommendation

Raise the monotonicity backward-jump threshold to at least 10 pages to filter out two-column interleaving noise. Only investigate breaks with backward jumps > 50 pages as potential misplacements.