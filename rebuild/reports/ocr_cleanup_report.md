# OCR Artifact Cleanup Report

Applied conservative OCR fixes to 349 of 12934 entries.

## Fix Summary

| Pattern | Count | Description |
|---------|-------|-------------|
| hyphen_rejoin | 139 | Rejoin hyphenated line breaks |
|  @ -> a | 108 | @ with spaces -> a |
| a@->a | 30 | a@ -> a |
| @->a_mid_word | 21 | @ between letters -> a |
| @->a_before_lc | 16 | @ before lowercase -> a |
| tbe->the | 11 | b/h swap: tbe -> the |
| &@->a | 10 | &@->a |
| witb->with | 9 | b/h swap: witb -> with |
| ber->her | 8 | b/h swap: ber -> her |
| bim->him | 5 | b/h swap: bim -> him |
| 4s->as | 3 | 4s->as |
| bave->have | 3 | b/h swap: bave -> have |
| tbat->that | 3 | b/h swap: tbat -> that |
| @&->a | 3 | @&->a |
| @b->ab | 2 | @b->ab |
| 4nd->and | 2 | Digit swap: 4nd -> and |
| (@->a | 2 | (@ -> (a |
| isolated_a_line | 2 | isolated_a_line |
| 4t->at | 2 | 4t->at |
| beld->held | 1 | beld->held |
| 4n->an | 1 | 4n->an |
| bolding->holding | 1 | bolding->holding |
| Tbe->The | 1 | Tbe->The |

---

## Changed Entries (349 entries)

| Term | Fixes Applied |
|------|--------------|
| A AVER |  @ -> a(1) |
| A ME |  @ -> a(1) |
| A PALATIO |  @ -> a(1) |
| A PRENDRE |  @ -> a(1) |
| A QUO | a@->a(1),  @ -> a(2), @->a_before_lc(1) |
| A RENDRE |  @ -> a(1) |
| A RESPONSIS |  @ -> a(1) |
| A RETRO |  @ -> a(1) |
| AB |  @ -> a(2) |
| AB INITIO | @b->ab(1) |
| AB INVITO | @b->ab(1) |
| AB IRATO | @->a_before_lc(1) |
| ABANDONMENT | hyphen_rejoin(1) |
| ABATEMENT | @->a_before_lc(1) |
| ABJURE |  @ -> a(1) |
| ABSQUE CONSIDERATIONE CURIAE |  @ -> a(1) |
| ABSQUE IMPETITIONE VASTI | hyphen_rejoin(1) |
| ACCOMENDA |  @ -> a(1) |
| ACCORD | 4nd->and(1) |
| ACCOUNT | a@->a(1) |
| ACQUIT |  @ -> a(1) |
| ACTE | hyphen_rejoin(1) |
| ACTIO | &@->a(1) |
| AD INQUIRENDUM |  @ -> a(1) |
| ADHIBERE | hyphen_rejoin(1) |
| ADJUDICATION | hyphen_rejoin(1) |
| ADMINISTRATOR | witb->with(1) |
| ADULTEROUS | witb->with(1) |
| AEQUITAS | @->a_before_lc(1) |
| AEQUUS | @->a_before_lc(1) |
| AESS | @->a_before_lc(1) |
| AFFIRMANCE | hyphen_rejoin(1) |
| AFFRECTAMENTUM |  @ -> a(1) |
| AGISTMENT | witb->with(1) |
| AIR-WAY | witb->with(1) |
| ALBUM | witb->with(1) |
| ALCOHOLISM | hyphen_rejoin(1) |
| ALIMONY | tbe->the(1) |
| AMENDMENT | hyphen_rejoin(1) |
| ANCIENT | hyphen_rejoin(1) |
| ANECIUS | @->a_before_lc(1) |
| ANGUISH | hyphen_rejoin(1) |
| ANNUAL | a@->a(1) |
| APPOINTMENT | hyphen_rejoin(1) |
| ARCHIVES | hyphen_rejoin(1) |
| ARETRO |  @ -> a(1) |
| ARRIERE VASSAL | @->a_mid_word(1) |
| ARRIVE | hyphen_rejoin(1) |
| ARTICLED CLERK | hyphen_rejoin(1) |
| ASSEMBLY | hyphen_rejoin(1) |
| ... | (299 more entries) |
