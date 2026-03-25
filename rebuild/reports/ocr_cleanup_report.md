# OCR Artifact Cleanup Report

Applied conservative OCR fixes to 1080 of 12981 entries.

## Fix Summary

| Pattern | Count | Description |
|---------|-------|-------------|
| hyphen_space_rejoin | 331 | hyphen_space_rejoin |
| 8->S_abbrev | 239 | 8->S_abbrev |
| pipe_remove | 211 | pipe_remove |
| hyphen_rejoin | 136 | Rejoin hyphenated line breaks |
| gv->qv | 115 | gv->qv |
|  @ -> a | 105 | @ with spaces -> a |
| qv_paren_fix | 49 | qv_paren_fix |
| euro->e | 41 | euro->e |
| a@->a | 29 | a@ -> a |
| @->a_mid_word | 20 | @ between letters -> a |
| aud->and | 18 | aud->and |
| @->a_before_lc | 16 | @ before lowercase -> a |
| &@->a | 10 | &@->a |
| witb->with | 9 | b/h swap: witb -> with |
| tbe->the | 9 | b/h swap: tbe -> the |
| ber->her | 8 | b/h swap: ber -> her |
| euro->eg | 6 | euro->eg |
| bim->him | 5 | b/h swap: bim -> him |
| euro->ie | 4 | euro->ie |
| 4s->as | 3 | 4s->as |
| bave->have | 3 | b/h swap: bave -> have |
| tbat->that | 3 | b/h swap: tbat -> that |
| @&->a | 3 | @&->a |
| @b->ab | 2 | @b->ab |
| 4nd->and | 2 | Digit swap: 4nd -> and |
| (@->a | 2 | (@ -> (a |
| isolated_a_line | 2 | isolated_a_line |
| otbers->others | 1 | otbers->others |
| exaniples->examples | 1 | exaniples->examples |
| 4t->at | 1 | 4t->at |
| beld->held | 1 | beld->held |
| 4n->an | 1 | 4n->an |
| anotber->another | 1 | anotber->another |
| rigbt->right | 1 | rigbt->right |
| bolding->holding | 1 | bolding->holding |
| Tbe->The | 1 | Tbe->The |

---

## Changed Entries (1080 entries)

| Term | Fixes Applied |
|------|--------------|
| A AVER |  @ -> a(1) |
| A ME |  @ -> a(1) |
| A PALATIO |  @ -> a(1) |
| A PRENDRE |  @ -> a(1) |
| A QUO | a@->a(1),  @ -> a(2), @->a_before_lc(1) |
| A RENDRE |  @ -> a(1), aud->and(1) |
| A RESPONSIS |  @ -> a(1) |
| A RETRO |  @ -> a(1) |
| A VINCULO | hyphen_space_rejoin(1), pipe_remove(1) |
| AB |  @ -> a(2) |
| AB EPISTOLIS | hyphen_space_rejoin(1) |
| AB INITIO | @b->ab(1) |
| AB INVITO | @b->ab(1) |
| AB IRATO | @->a_before_lc(1) |
| ABANDONMENT | hyphen_rejoin(1), hyphen_space_rejoin(1), aud->and(1), pipe_remove(1), euro->ie(1) |
| ABATEMENT | @->a_before_lc(1), pipe_remove(1) |
| ABJURE |  @ -> a(1) |
| ABRIDGMENT | hyphen_space_rejoin(1) |
| ABROGATION | hyphen_space_rejoin(1), pipe_remove(1) |
| ABSQUE CONSIDERATIONE CURIAE |  @ -> a(1) |
| ABSQUE IMPETITIONE VASTI | hyphen_rejoin(1) |
| ABUTTALS | gv->qv(1), qv_paren_fix(1) |
| ACCIDENT | 8->S_abbrev(1) |
| ACCOMENDA |  @ -> a(1) |
| ACCORD | 4nd->and(1) |
| ACCOUNT | hyphen_space_rejoin(1) |
| ACCRETION | 8->S_abbrev(1), euro->e(1) |
| ACQUIT |  @ -> a(1) |
| ACT | hyphen_space_rejoin(1) |
| ACTE | hyphen_rejoin(1) |
| ACTIO | &@->a(1) |
| ACTION | hyphen_space_rejoin(1) |
| ACTUAL | pipe_remove(1) |
| AD INQUIRENDUM |  @ -> a(1) |
| ADEQUATE | hyphen_space_rejoin(1) |
| ADFERRUMINATIO | gv->qv(1), qv_paren_fix(1) |
| ADHIBERE | hyphen_rejoin(1) |
| ADJACENT | 8->S_abbrev(1) |
| ADJUDICATION | hyphen_rejoin(1) |
| ADMINICULAR | euro->e(1) |
| ADMINISTRATION OF ESTATES | 8->S_abbrev(1), pipe_remove(1) |
| ADMINISTRATIVE | hyphen_space_rejoin(1) |
| ADMINISTRATOR | witb->with(1) |
| ADMORTIZATION | hyphen_space_rejoin(1) |
| ADNOTATIO | aud->and(1) |
| ADULTERINE | hyphen_space_rejoin(2) |
| ADULTEROUS | witb->with(1) |
| ADULTERY | pipe_remove(2) |
| ADVANCES | 8->S_abbrev(1) |
| ADVISORY | 8->S_abbrev(1) |
| ... | (1030 more entries) |
