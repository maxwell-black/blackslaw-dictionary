# LexPredict vs blackslaw.io Comparison Report

## Dataset Overview

| Metric | Count |
|--------|-------|
| blackslaw.io live entries | 12900 |
| blackslaw.io unique normalized | 12885 |
| LexPredict entries | 13261 |
| LexPredict unique normalized | 13190 |

## Match Results

| Category | Count | Notes |
|----------|-------|-------|
| Exact match (both) | 8988 | 69.8% of live, 68.1% of LP |
| Live only (before Lev) | 3897 | In blackslaw but not LP |
| LP only (before Lev) | 4202 | In LP but not blackslaw |
| Levenshtein matched (live->LP) | 2726 | OCR variants |
| Levenshtein matched (LP->live) | 1408 | OCR variants |
| True unmatched (live only) | 1171 | Possible LP gaps or our fabrications |
| True unmatched (LP only) | 2794 | **Possible blackslaw gaps** or LP fabrications |

## Action Items

### Potential gaps in blackslaw.io (2794 entries)

These entries exist in LexPredict but have no exact or near match in blackslaw.io.
Some are real entries we're missing. Some are LexPredict OCR artifacts.
Review manually, prioritizing entries with longer definitions (more likely real).

Top potential gaps (by definition length, showing first 50):

| Term | Def Length | Definition Preview |
|------|-----------|-------------------|
| I H. BI | 2836 | ook. In mercantile law. A book in which an account of bilis of exchange and prom-issory notes, whether payable or receiv |
| IS L. R | 1895 | officer. Any officer of the United States who holds his appointment under the national government, whether his duties ar |
| COURT OF EXCHEQUER | 1324 | In English law. A very ancient court of record, set up by william the Conqueror as a part of the aula regis, aud afterwa |
| MARQUE AND REPRISAL, LETTERS OF | 1013 | These words, “marque” and “reprisal," are frequently used as synony-mous, but, taken in thelr strict etymological sense, |
| PLUS PETITIO | 991 | In Roman law. A phrase denoting the offense of claiming more thau was just In one’s pleadings. Thlfc mord might be claim |
| UNFAIR COMPETITION | 942 | A term which may be applied generally to all dls-honest or fraudulent rivalry in trade and commerce, but Is particularly |
| ARCHES COURT | 895 | In English ecclesiastical law. A court of appeal belonging to the Archbishop of Canterbury, the Judge of which is called |
| COURT OF SESSION | 860 | The name of the highest court of civil jurisdiction lu Scot-land. It was composed of fifteen judges, now of thirteen. It |
| IN PERSONAM, IN REM | 855 | In the Ro-maa law, from which they are taken, the expressions “in rem” and “in personam” were always opposed to one anot |
| EX SCRIPTIS OLIM VISIS | 828 | From writings formerly seen. A term used as descriptive of that kind of proof of handwriting where the knowledge has bee |
| COURT OF HONOR | 807 | A court having Ju-risdiction to hear and redress injuries or affronts to a man’s honor or personal dignity, of a nature  |
| COURT OF OYER AND TERMINER | 803 | In English law. A court for the trial of cases of treason and felony. The commis-sloners of assise and nisi prius are ju |
| SUPREME COURT OF JUDICATURE | 801 | The court formed by the English judicature act, 1873, (as modified by the judicature act, 1875, the appellate jurisdicti |
| ABSCONDING DEBTOR | 797 | one,who;ab-sconds from his credltors. An absconding, debtor is oue who lives without the stpte, or who has intentionally |
| CANTERBURY, ARCHBISHOP OF | 789 | In English eccleslastlcal law. The primate of all England; the chief ecclesiastical digni-tary in the church. Hls custom |
| STET BILLA | 763 | If the plalntlff ln a plaint in the mayor’s court of London has attached property belonging to the defendant and ob-tain |
| NOTARY PUBLIC | 742 | A public officer whose function ia to attest and certify, by his hand and official seal, certain classes of documents, i |
| SALADINE TENTH | 735 | A tax imposed in England and France, in 1188, by Pope Innocent III., to raise a fund for the crusade undertaken by Richa |
| SUPERSTITIOUS USE | 725 | In Engllsh law. when lands, tenements, rents, goods, or chattels are given, secured, or appointed for and towards the ma |
| STATE OF FACTS | 710 | Formerly, when a master in chancery was directed by the court of chancery to make an inquiry or investiga-tion lnto any  |
| COURT OF STAR CHAMBER | 699 | This was an English court of very ancient origin, but new-modeled by St. 3 Hen. VII. c. 1, aud 21 Hen. VIII. c. 20, cons |
| EJECTIONE FIRMS | 692 | Ejection, or ejectment of farm. The name of a writ or action of trespass, which lay at common law where lands or tenemen |
| RHODIAN LAWS | 688 | This, the earliest code or collection of maritime laws, was formulated by the people of the island of Rhodes, who, by th |
| COURT OF WARDS AND LIVERIES | 683 | A court of record, established in England iu the reign of Henry VIII. For the sur-vey and management of the valuable fru |
| SUBSTITUTIONAL, SUBSTITUTION-ARY | 677 | where a will contains a gift of property tq a class of persons, with a clause providing that on the death of a member of |
| MILLBANK PRISON | 672 | Formerly called the “Penitentiary at Millbank.” A prison at westminster, for convicts under sentence of transportation,  |
| MANCIPI RES | 666 | LaL In Roman law. Certain classes of thlngs which could not be aliened or transferred except by means of a certain forma |
| ABSTRACT OF TITLE | 654 | A condensed' history of tbe title to land, consisting of a synopsis or summary of the material or op-erative portion of  |
| DAMNUM ABSQUE INJURIA | 648 | Loss, hurt, or harm without injury in the legal sense, that is, withont such an invasion of rights as is redressible by  |
| UNSOUND MIND | 637 | A person of unsound mind is an adult who from infirmity of mind ls incapable of managing himself or his af-falrs. The te |
| CO., ISI U | 631 | ses the body of those principles and rules of action, relating to the govern-ment and security of persons and property,  |
| MOBBING AND RIOTING | 613 | In Scotch law. A general term including all those convocations of the lieges for violent and un-lawful purposes, which a |
| TALITER PROCESSUM EST | 610 | Upon pleading the judgment of an inferior court, the proceedings preliminary to such judg-ment, and on which the same wa |
| COURT FOR DIVORCE AND MATRI-MONIAL CAUSES | 605 | This court was estab-lished by St. 20 & 21 Vict. c. 85, which trans-ferred to it all jurisdiction then exerclsable by an |
| NORMAN FRENCH | 604 | The tongue in whlch several formal proceedings of state in England are stlll carrled on. The lan-guage, having remained  |
| PROCES VERBAL | 599 | In French law. A written report, whlch ls signed, setting forth a statement of facts. This term ls applled to the report |
| DIVINE SERVICE | 598 | Divine service was the name of a feudal tenure, by which the tenants were obliged to do some special divine services in  |
| ORPHANAGE PART | 598 | That portion of an intestate's effects which his children were entitled to by the custom of London. This custom appears  |
| AMICUS CURLS | 594 | Lat A friend of the court A by-stander (usually a counsel-lor) who Interposes and volunteers lnforma-tion upon some matt |
| QUIA EMFTORES | 592 | “Because the pur-chasere.” The title of the statute of westm. S. (18 Edw. L c. 1.) This statute took from the tenants of |
| DE ANNO BISSEXTILI | 590 | of the bis-sextile or leap year. The title of a statute passed ln the twenty-first year of Henry III., which in fact, ho |
| DISCONTINUANCE OF AN ESTATE | 587 | The termination or suspension of an estate-tail, in consequence of the act of the tenant ln tail, in conveying a larger  |
| DRAMATIC COMPOSITION | 584 | In copy-right law. A literary work setting forth a story, incident, or scene from life, in which, however, the narrative |
| MEN OF STRAW | 580 | Men who used in former days to ply about courts of law, so called from their manner of makiug known their occupation, (i |
| BUBBLE ACT | 572 | The statute 6 Geo. I. c. 18, “for restraining several extravagant and unwarrantable practices herein mentioned," was so  |
| PER STIRPES | 569 | Lat By roots or stocks; by representatlon. This term, de-rived from the clvil law, ls much used in the law of descents a |
| MORT CIVILE | 565 | In French law. Civil death, as upon conviction for felony. It was nominally abollshed by a law of the 31st of May, 1854, |
| RURAL DEANS | 561 | In English ecclesias-tical la... Very ancient officers of the church, almost grown out of use, until about the middle of |
| AD VALOREM | 558 | According to value. Duties are either ad valorem or speei/fc; the former when the duty Is laid in the form of a percenta |
| COMMON RECOVERY | 556 | In conveyanc-Ing. A species of common assurance, or mode of conveying lands by matter of record, formerly ln frequent us |

### Potential extras in blackslaw.io (1171 entries)

These entries exist in blackslaw.io but have no exact or near match in LexPredict.
Most are likely real entries that LexPredict missed (LP also has OCR gaps).
Short-body entries with garbled headwords are candidates for further review.

Shortest-body extras (most suspicious, showing first 50):

| Headword | Body Length | Body Preview |
|----------|-----------|-------------|
| COMMITTING | 3 | See |
| DEMONSTRATIVE | 3 | See |
| ITINERE PER ATTORNATUM | 3 | See |
| SATISFACTORY EVIDENCE | 3 | See |
| SCRAMBLING | 5 | — See |
| COMMUTATIVE | 8 | See Jus- |
| EXEMPLARY | 8 | See Dam- |
| IDONEUM | 8 | IDONEARE |
| LADING LADING, BILL OF | 8 | See BIL. |
| VINDICTIVE | 8 | See Dax- |
| SUPPLETORY OATH | 10 | See Oartn. |
| TRANSGRESSIVE | 10 | See Trust. |
| CATCHING | 11 | See BagGain |
| MUCIANA | 11 | See Cavuto. |
| SWAINMOTE | 11 | See SwErIn; |
| NEWLY-DISCOVERED | 13 | See EVIDENCE. |
| COPARTNERSHIP | 14 | A partnership. |
| SHAWM'S ATORES | 17 | Soldiers. Cowell. |
| POSTLIMINY | 19 | See PostTLiMinivuM. |
| WHITSUN | 19 | Pentecostals, (q..) |
| BURGUNDIAN | 23 | See Lex Bup- GUNDIONUM. |
| CARCEL-AGE | 23 | Gaol-dues; prison-fees. |
| DOMMAGES | 23 | In French law. Damages. |
| CLAVIGERATUS | 24 | A treasurer of a chur@). |
| HERBERGARE | 24 | To harbor; to entertain. |
| LIEUTENANCY LIEUTENANCY, COMMISSION OF | 24 | See CoMMISSION OF ARRAY. |
| LOCOCESSION | 24 | The act of giving place. |
| CIRCUMSTANTIBUS | 25 | TALES DE. See TALES. Sa a |
| ERE-MURDER | 25 | MURDER. See MANSLAUGHTER. |
| VENDITIONI | 25 | Sale; the act of selling. |
| CONSIDERATIO | 26 | The judgment of the court. |
| SANGUINITATE | 26 | Writs of cosinage, (q. v.) |
| STIPULATED | 26 | Liquidated damage, (g. ¥.) |
| MISSI PRESBYTER | 27 | A priest in orders. Blount. |
| GALLIVOLATIUM | 28 | A cock-shoot, or cock-glade. |
| ILLICITUM | 28 | Lat. An illegal corporation. |
| SYMOND'S INN | 28 | Formerly an inn of chancery. |
| YVERNAIL | 28 | L. Fr. Winter grain. Kelham. |
| EFFECTUS SEQUITUR CAUSAM | 29 | The effect follows the cause. |
| IMPETITIO | 29 | Impeachment of waste, (g. v.) |
| CARCERATUS | 30 | ship.  Loaded; freighted, as a |
| FURANDI | 30 | Lat. An intention of stealing. |
| SERVIENS AD CLAVAM | 30 | Serjeant at mace. 2 Mod. 58. ; |
| SYMBOLUM | 30 | Lat. A mortuary, or soul-scot. |
| DISCONVENABLE | 31 | L. Fr. Improper; unfit. Kelham. |
| QUACUNQUE | 31 | Lat. Whichever way you take it. |
| REGISTRUM | 31 | The regis ter of writs, (g. v.) |
| SPIRITUAL TENURES, I | 31 | I. Frankalmoigne, or free alms. |
| COMMARCHIO | 33 | A boundary; the confines of land. |
| CUTHRED | 33 | A knowing or skillful counsellor. |

### Levenshtein near-matches (OCR variant pairs)

These pairs differ by 1-3 characters and are likely the same entry
garbled differently by different OCR engines.

#### blackslaw -> LexPredict (distance 1 only, first 30):

| blackslaw term | LexPredict term | Dist | OCR Pattern |
|---------------|----------------|------|-------------|
| A NATIVITATE | A NATIVTTATE | 1 | I->T (pos 7) |
| ABAVITA | ABAMITA | 1 | V->M (pos 3) |
| ABAVUNCULUS | ABAVUNOULUS | 1 | C->O (pos 6) |
| ABBAOCY | ABBACY | 1 | length_or_complex_diff |
| ABDUCTION | ABDUOTION | 1 | C->O (pos 4) |
| ABISHERING | ABISHERSING | 1 | length_or_complex_diff |
| ABSENTE | ABSENCE | 1 | T->C (pos 5) |
| ACCEPTARE | ACCEPT ARE | 1 | length_or_complex_diff |
| ACCESSORY OCONTRAOT | ACCESSORY OONTRAOT | 1 | length_or_complex_diff |
| ACCIPITARE | ACOIPITARE | 1 | C->O (pos 2) |
| ACCOLA | ACOOLA | 1 | C->O (pos 2) |
| ACCOUNTABLE | AOCOUNTABLE | 1 | C->O (pos 1) |
| ACCOUNTING | AOCOUNTING | 1 | C->O (pos 1) |
| ACCREDULITARE | ACOREDULITARE | 1 | C->O (pos 2) |
| ACCRETION | ACORETION | 1 | C->O (pos 2) |
| ACOCRESCERE | AOCRESCERE | 1 | length_or_complex_diff |
| ACOROACH | AOOROACH | 1 | C->O (pos 1) |
| ACOROOCHER | ACOROCHER | 1 | length_or_complex_diff |
| ACROSS | AGROSS | 1 | C->G (pos 1) |
| ACT | FACT | 1 | length_or_complex_diff |
| ACTA | FACTA | 1 | length_or_complex_diff |
| ACTA PUBLICA | ACTA PUBLIGA | 1 | C->G (pos 10) |
| ACTIO NON ULTERIUS | AGTIO NON ULTERIUS | 1 | C->G (pos 1) |
| ACTION ON THE CASE | AGTION ON THE CASE | 1 | C->G (pos 1) |
| ACTRIX | AGTRIX | 1 | C->G (pos 1) |
| AD COMPOTUM REDDENDUM | AD GOMPOTUM REDDENDUM | 1 | C->G (pos 3) |
| AD RATIONEM PONERE | AD RATIONEM FONERE | 1 | P->F (pos 12) |
| ADIPOCERE | ADIFOCERE | 1 | P->F (pos 3) |
| ADJECTIVE LAW | ADJECTTVE LAW | 1 | I->T (pos 6) |
| ADJUDICATEE | ADJUDICATES | 1 | E->S (pos 10) |

#### LexPredict -> blackslaw (distance 1 only, first 30):

| LexPredict term | blackslaw term | Dist | OCR Pattern |
|----------------|---------------|------|-------------|
| A NATIVTTATE | A NATIVITATE | 1 | T->I (pos 7) |
| A VAILS | AVAILS | 1 | length_or_complex_diff |
| ABAMITA | ABAVITA | 1 | M->V (pos 3) |
| ABAVTTA | ABAVITA | 1 | T->I (pos 4) |
| ABAVUNOULUS | ABAVUNCULUS | 1 | O->C (pos 6) |
| ABBACY | ABBAOCY | 1 | length_or_complex_diff |
| ABDUOTION | ABDUCTION | 1 | O->C (pos 4) |
| ABISHERSING | ABISHERING | 1 | length_or_complex_diff |
| ABSENCE | ABSENTE | 1 | C->T (pos 5) |
| ACCEPT ARE | ACCEPTARE | 1 | length_or_complex_diff |
| ACCESSORY OONTRAOT | ACCESSORY OCONTRAOT | 1 | length_or_complex_diff |
| ACOIPITARE | ACCIPITARE | 1 | O->C (pos 2) |
| ACOOLA | ACCOLA | 1 | O->C (pos 2) |
| ACOREDULITARE | ACCREDULITARE | 1 | O->C (pos 2) |
| ACORETION | ACCRETION | 1 | O->C (pos 2) |
| ACOROCHER | ACOROOCHER | 1 | length_or_complex_diff |
| ACTA PUBLIGA | ACTA PUBLICA | 1 | G->C (pos 10) |
| AD GOMPOTUM REDDENDUM | AD COMPOTUM REDDENDUM | 1 | G->C (pos 3) |
| AD RATIONEM FONERE | AD RATIONEM PONERE | 1 | F->P (pos 12) |
| AD VENA | ADVENA | 1 | length_or_complex_diff |
| ADBCENDENTES | ADSCENDENTES | 1 | B->S (pos 2) |
| ADIFOCERE | ADIPOCERE | 1 | F->P (pos 3) |
| ADJECTTVE LAW | ADJECTIVE LAW | 1 | T->I (pos 6) |
| ADJUDICATES | ADJUDICATEE | 1 | S->E (pos 10) |
| ADMONITION | ADMONITIO | 1 | length_or_complex_diff |
| AFFEGTUS | AFFECTUS | 1 | G->C (pos 4) |
| AGROSS | ACROSS | 1 | G->C (pos 1) |
| AGTIO NON ULTERIUS | ACTIO NON ULTERIUS | 1 | G->C (pos 1) |
| AGTION ON THE CASE | ACTION ON THE CASE | 1 | G->C (pos 1) |
| AGTRIX | ACTRIX | 1 | G->C (pos 1) |

## Known LexPredict Issues

The LexPredict dataset has its own OCR problems:
- ABSTRACT is missing entirely
- HABEAS CORPUS is missing entirely
- Contains O-for-C garbling (OOURT, OONTRACTU, CCELO)
- 59 duplicate headwords (C. C appears 11 times)
- No OCR cleanup was applied (raw 2017 extraction)
- Therefore: entries 'missing' from LP are not necessarily invalid in blackslaw
