# LexPredict Gap Investigation Report

71 LP-only entries with definitions > 500 chars, cross-referenced against
the editorial overlay (13,641 entries, all types) and DjVu source data.
Fuzzy matching (Levenshtein <= 2) used to account for OCR noise in both corpora.

## Summary

| Classification | Count | Description |
|---------------|-------|-------------|
| FOUND_IN_OVERLAY | 1 | Already in overlay (may be live, suppressed, or garbled match) |
| SUBENTRY_IN_PARENT | 22 | Embedded as subentry/reference in a parent entry body |
| RECOVERABLE_FROM_DJVU | 0 | Found in DjVu source, recoverable with source page |
| NOT_FOUND | 46 | Not in overlay or DjVu source — candidate for import |
| LP_DEBRIS | 2 | On inspection, OCR debris in LexPredict data |

---

## FOUND_IN_OVERLAY (1 entries)

These entries already exist in the overlay. No action needed unless the entry_type
indicates suppression — in which case, review whether the suppression was correct.

| # | LP Term | Def Len | Match | Overlay ID | Overlay Term | Type |
|---|---------|---------|-------|------------|-------------|------|
| 5 | PLUS PETITIO | 991 | fuzzy (distance=2) | BLD2-09845 | PLURIS PETITIO | verified_main |

---

## SUBENTRY_IN_PARENT (22 entries)

These terms appear in the body of a parent entry as subentries or references.
They exist in our corpus but not as standalone headwords — LexPredict split them
into separate entries. No action needed unless we want to promote them to standalone.

| # | LP Term | Def Len | Parent Entry |
|---|---------|---------|-------------|
| 3 | COURT OF EXCHEQUER | 1324 | EXCHEQUER |
| 6 | UNFAIR COMPETITION | 942 | COMPETITION |
| 7 | ARCHES COURT | 895 | COURT |
| 13 | SUPREME COURT OF JUDICATURE | 801 | SUPREME |
| 19 | SUPERSTITIOUS USE | 725 | USE |
| 24 | COURT OF WARDS AND LIVERIES | 683 | WARDS |
| 29 | DAMNUM ABSQUE INJURIA | 648 | DAMNUM |
| 30 | UNSOUND MIND | 637 | UNSOUND |
| 35 | NORMAN FRENCH | 604 | NORMAN |
| 36 | PROCES VERBAL | 599 | PROCES |
| 37 | DIVINE SERVICE | 598 | DIVINE |
| 42 | DISCONTINUANCE OF AN ESTATE | 587 | DISCONTINUANCE |
| 45 | BUBBLE ACT | 572 | BUBBLE |
| 46 | PER STIRPES | 569 | PER |
| 53 | OUT OF THE STATE | 548 | OUT |
| 56 | CATONIANA REGULA | 539 | CATONIANA |
| 58 | ESTATE OF INHERITANCE | 537 | INHERITANCE |
| 59 | IRRESISTIBLE IMPULSE | 537 | IRRESISTIBLE |
| 60 | GRAMMAR SCHOOL | 532 | GRAMMAR |
| 64 | FORCIBLE ENTRY AND DETAINER | 527 | FORCIBLE |
| 65 | JUS PRIVATUM | 525 | JUS |
| 68 | INTER CONJUNCTAS PERSONAS | 515 | INTER |

---


---

## NOT_FOUND (46 entries)

These entries are in LexPredict but not in our overlay or DjVu source.
They are candidates for import, but each needs policy review:
- Is it a real dictionary entry or LexPredict OCR artifact?
- If real, should it be added to the overlay as a new entry?

| # | LP Term | Def Len | Definition Preview |
|---|---------|---------|-------------------|
| 2 | IS L. R | 1895 | officer. Any officer of the United States who holds his appointment under the national government, w |
| 4 | MARQUE AND REPRISAL, LETTERS OF | 1013 | These words, “marque” and “reprisal," are frequently used as synony-mous, but, taken in thelr strict |
| 8 | COURT OF SESSION | 860 | The name of the highest court of civil jurisdiction lu Scot-land. It was composed of fifteen judges, |
| 9 | IN PERSONAM, IN REM | 855 | In the Ro-maa law, from which they are taken, the expressions “in rem” and “in personam” were always |
| 10 | EX SCRIPTIS OLIM VISIS | 828 | From writings formerly seen. A term used as descriptive of that kind of proof of handwriting where t |
| 11 | COURT OF HONOR | 807 | A court having Ju-risdiction to hear and redress injuries or affronts to a man’s honor or personal d |
| 12 | COURT OF OYER AND TERMINER | 803 | In English law. A court for the trial of cases of treason and felony. The commis-sloners of assise a |
| 14 | ABSCONDING DEBTOR | 797 | one,who;ab-sconds from his credltors. An absconding, debtor is oue who lives without the stpte, or w |
| 15 | CANTERBURY, ARCHBISHOP OF | 789 | In English eccleslastlcal law. The primate of all England; the chief ecclesiastical digni-tary in th |
| 16 | STET BILLA | 763 | If the plalntlff ln a plaint in the mayor’s court of London has attached property belonging to the d |
| 17 | NOTARY PUBLIC | 742 | A public officer whose function ia to attest and certify, by his hand and official seal, certain cla |
| 18 | SALADINE TENTH | 735 | A tax imposed in England and France, in 1188, by Pope Innocent III., to raise a fund for the crusade |
| 20 | STATE OF FACTS | 710 | Formerly, when a master in chancery was directed by the court of chancery to make an inquiry or inve |
| 21 | COURT OF STAR CHAMBER | 699 | This was an English court of very ancient origin, but new-modeled by St. 3 Hen. VII. c. 1, aud 21 He |
| 22 | EJECTIONE FIRMS | 692 | Ejection, or ejectment of farm. The name of a writ or action of trespass, which lay at common law wh |
| 23 | RHODIAN LAWS | 688 | This, the earliest code or collection of maritime laws, was formulated by the people of the island o |
| 25 | SUBSTITUTIONAL, SUBSTITUTION-ARY | 677 | where a will contains a gift of property tq a class of persons, with a clause providing that on the  |
| 26 | MILLBANK PRISON | 672 | Formerly called the “Penitentiary at Millbank.” A prison at westminster, for convicts under sentence |
| 27 | MANCIPI RES | 666 | LaL In Roman law. Certain classes of thlngs which could not be aliened or transferred except by mean |
| 28 | ABSTRACT OF TITLE | 654 | A condensed' history of tbe title to land, consisting of a synopsis or summary of the material or op |
| 31 | CO., ISI U | 631 | ses the body of those principles and rules of action, relating to the govern-ment and security of pe |
| 32 | MOBBING AND RIOTING | 613 | In Scotch law. A general term including all those convocations of the lieges for violent and un-lawf |
| 33 | TALITER PROCESSUM EST | 610 | Upon pleading the judgment of an inferior court, the proceedings preliminary to such judg-ment, and  |
| 34 | COURT FOR DIVORCE AND MATRI-MONIAL CAUSES | 605 | This court was estab-lished by St. 20 & 21 Vict. c. 85, which trans-ferred to it all jurisdiction th |
| 38 | ORPHANAGE PART | 598 | That portion of an intestate's effects which his children were entitled to by the custom of London.  |
| 39 | AMICUS CURLS | 594 | Lat A friend of the court A by-stander (usually a counsel-lor) who Interposes and volunteers lnforma |
| 40 | QUIA EMFTORES | 592 | “Because the pur-chasere.” The title of the statute of westm. S. (18 Edw. L c. 1.) This statute took |
| 41 | DE ANNO BISSEXTILI | 590 | of the bis-sextile or leap year. The title of a statute passed ln the twenty-first year of Henry III |
| 43 | DRAMATIC COMPOSITION | 584 | In copy-right law. A literary work setting forth a story, incident, or scene from life, in which, ho |
| 44 | MEN OF STRAW | 580 | Men who used in former days to ply about courts of law, so called from their manner of makiug known  |
| 47 | MORT CIVILE | 565 | In French law. Civil death, as upon conviction for felony. It was nominally abollshed by a law of th |
| 48 | RURAL DEANS | 561 | In English ecclesias-tical la... Very ancient officers of the church, almost grown out of use, until |
| 49 | AD VALOREM | 558 | According to value. Duties are either ad valorem or speei/fc; the former when the duty Is laid in th |
| 50 | COMMON RECOVERY | 556 | In conveyanc-Ing. A species of common assurance, or mode of conveying lands by matter of record, for |
| 51 | TERRITORIAL, TERRITORIALITY | 554 | These terms are used to slgnlfy connection with, or limitation with reference to, a par-tlcular coun |
| 52 | VTNOUS LIQUORS | 551 | Thfs term includes all alcoholic beverages made from the Juice of the grape by the process of fermen |
| 54 | JUS NATURALE | 542 | The natural law, or law of nature; law. or legal principles, sup-posed to be discoverable by the lig |
| 55 | REBELLIOUS ASSEMBLY | 541 | In Eng-lish law. A gathering of twelve persons or more, intending, going about, or practicing unlawf |
| 57 | EBB AND FLOW | 537 | An expression used Eoolesia est infra setatom ot in ons-formerly in this country to denote the limit |
| 61 | WITHDRAWING A JUROR | 532 | In prac-tice. The withdrawing of one of the twelve jurors from the box, with the result that, the ju |
| 62 | NOVELUE CONSTI-TUTIONES | 529 | NSTI-TUTIONES.) New constitutions; generally translated in English, “Novels.” The Latin name of thos |
| 63 | FORCIBLE TRESPASS | 528 | In North Carolina, this Is an invasion of the rights of auother with respect to his personal prop-er |
| 67 | JUS DISPONENDI | 516 | The right of dis-posing. An expression used either general-ly to signify the right of alienation, as |
| 69 | STATE OF FACTS AND PROPOSAL | 514 | In English lunacy practice, when a person has beeu found a lunatic, the next step is to submit to th |
| 70 | COURT OF PECULIARS | 513 | A spiritual court in England, belng a branch of, and annexed to, the Court of Arches. It has a juris |
| 71 | EX MERO MOTU | 505 | TU. of his own mere motion; of his own accord; voluntarily and without prompting or request. Royal l |

---

## LP_DEBRIS (2 entries)

These are OCR artifacts in the LexPredict dataset, not real entries.

| # | LP Term | Def Len | Reason |
|---|---------|---------|--------|
| 1 | I H. BI | 2836 | Garbled term format (letter space letter-dot pattern) |
| 66 | I W. A M | 519 | Garbled term format (letter space letter-dot pattern) |
