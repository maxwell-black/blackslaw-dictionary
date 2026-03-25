# Running Header Gap Recovery

Attempted recovery of 23 genuine gaps from running header analysis.

## Summary

| Classification | Count | Description |
|---------------|-------|-------------|
| RECOVERED_FROM_DJVU | 7 | Found in DjVu source candidates |
| PARTIAL_DJVU | 13 | In page text but no clean extraction |
| NOT_RECOVERABLE | 3 | Not found in any source |

**6** entries applied to overlay (7 DjVu matches, minus 1 already present as SUSPICIOUS CHARACTER).

---

## Recovered from DjVu (7 entries)

| Leaf | Term | Detail |
|------|------|--------|
| 299 | COURT OF THE CORONER | exact, src_hw=COURT OF THE CORONER |
| 331 | DE ARTE ET PARTE (was: DE ARTE. ET PARTE) | exact, src_hw=DE ARTE ET PARTE |
| 461 | EX ABUNDANTI | exact, src_hw=EX ABUNDANTI |
| 699 | KING'S CHAMBERS | exact, src_hw=KING'S CHAMBERS |
| 1031 | REPOSITION OF THE FOREST | exact, src_hw=REPOSITION OF THE FOREST |
| 1133 | SUITORS' FUND IN CHANCERY | exact, src_hw=SUITORS' FUND IN CHANCERY |
| 1141 | SUSPICIOUS CHARACTER (was: SUSPICIOUS CHARACTER. IN THE) | exact, src_hw=SUSPICIOUS CHARACTER |

---

## Partial DjVu Match (13 entries)

| Leaf | Term | Detail |
|------|------|--------|
| 300 | COURT OF GREAT SESSIONS | 1 page hits |
| 302 | COURT OF PRIVATE LAND | 2 page hits |
| 332 | DE BONIS TESTATORIS | 1 page hits |
| 334 | DE DEBITORE IN PARTES | 2 page hits |
| 336 | DE FIDE ET OFFICIO JUDICIS (was: DH-FIDE ET OFFICIO JUDICIS) | 1 page hits |
| 456 | ET HOC PETIT QUOD INQUIRATUR | 1 page hits |
| 613 | IN EO QUOD PLUS SIT | 1 page hits |
| 619 | IN RE PROPRIA INIQUUM | 1 page hits |
| 621 | IN VERBIS, NON VERBA (was: EIN VERBIS, NON VERBA) | 1 page hits |
| 690 | JUS JURANDI FORMA | 1 page hits |
| 835 | NON DEBET ACTORI LICERE | 1 page hits |
| 996 | QUOD IN JURE SCRIPTO | 1 page hits |
| 1193 | UBI NON EST PRINCIPALIS | 1 page hits |

---

## Not Recoverable (3 entries)

| Leaf | Term | Detail |
|------|------|--------|
| 333 | DE COMBUSTIONE DOMORUM (was: DE COMBUSTIONE DOMORUM. OF) | LP definition was garbage (2 chars: "of"). Not in DjVu source candidates. |
| 342 | DE SUPERONERATIONE PASTURAE (was: DF SUPERONERATIONE PASTURZ) | Not found in DjVu, LP, or overlay |
| 480 | EXPUNGE | DjVu fuzzy match was ESCUAGE (wrong word). Not in LP. Page text shows it on leaf 480 but no clean extraction. |

---
