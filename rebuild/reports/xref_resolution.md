# Unresolved Cross-Reference Resolution Report

Analyzed 125 unresolved cross-references (115 unique missing targets).

## Summary

| Category | Unique Targets | Total Refs | Description |
|----------|---------------|------------|-------------|
| truncated_ref | 20 | 21 | OCR truncated reference (false positive) |
| ocr_garbled | 20 | 21 | OCR-garbled target name (correctable) |
| variant_match | 1 | 1 | Target exists under variant spelling |
| suppressed_entry | 2 | 6 | Target is suppressed in overlay |
| legitimately_absent | 0 | 0 | Target genuinely absent from dictionary |
| subentry_reference | 72 | 76 | Target is a subentry within another entry |

---

## Truncated References (20)

These are regex false positives where OCR truncated the reference mid-word.
No action needed — these are not real cross-references.

| Target | Count | Referenced By |
|--------|-------|---------------|
| IN F | 2 | FORMA, FULL |
| AMI | 1 | AMY |
| DE O | 1 | ATHEIST |
| AD H | 1 | ATTORNEY |
| DE NON DEN | 1 | CIMANDO |
| AGN | 1 | COGNATIO |
| DEA | 1 | DEAD |
| WAGER OF L | 1 | DEFENDERE |
| DEP | 1 | DEPOSITUM |
| DIM | 1 | DIMISIT |
| CLERICO C | 1 | ERANDO |
| WRIT OF ER | 1 | ERROR |
| DEADLY F | 1 | FEUD |
| STO | 1 | GUARANTY |
| BREHON L | 1 | LEX |
| PRZ | 1 | PREDIAL |
| OWN | 1 | PROPERTY |
| IN P | 1 | PROPRIA PERSONA |
| PLE | 1 | REFERENDUM |
| TONNAGE D | 1 | TAX |

---

## OCR-Garbled Targets (20)

Target headword name damaged by OCR. Actual target identified.

| Garbled Target | Corrected To | Count | Referenced By |
|----------------|-------------|-------|---------------|
| INGROSS | ENGROSS | 2 | INROSSATION, INROSSER |
| JNSANITY | INSANITY | 1 | AMENTIA |
| COUTHLAUGH | COUTHUTLAUGH | 1 | CUTH |
| IORMEDON | FORMEDON | 1 | DESCENDER |
| BARNEST | EARNEST | 1 | EARLES-PENNY |
| DUPLEX VALOR MARITATII | DULPEX VALOR MARITAGII | 1 | FORFEITURE |
| MEBITS | MERITS | 1 | MERITORIOUS |
| EABNINGS | EARNINGS | 1 | NEPUOY |
| RIPABIAN | RIPARIAN | 1 | OWNER |
| WATEE | WATER | 1 | PERCH |
| MABRIAGE | MARRIAGE | 1 | PLURAL |
| PREZEMUNIRE | PRAEMUNIRE | 1 | PREMUNIRE |
| PRASUMPTIO | PRAESUMPTIO | 1 | PRESUMPTIO |
| PRELIMINABY | PRELIMINARY | 1 | PROOF |
| INPURE | UMPIRE | 1 | PUR |
| DVIDENCE | EVIDENCE | 1 | RELEVANT |
| EXTRAORDINABY | EXTRAORDINARY | 1 | REMEDY |
| FELONY DE SE | FELO DE SE | 1 | SELF-DEFENSE |
| CHANCELLORB | CHANCELLOR | 1 | VICE |
| EVECTMENT | EJECTMENT | 1 | WRIT OF DOWER |

---

## Variant Spelling Matches (1)

Target exists under a slightly different spelling.

| Target | Matched To | Distance | Count |
|--------|-----------|----------|-------|
| WATERCOURSE | WATER-COURSE | 0 | 1 |

---

## Suppressed Entries (2)

Target exists in overlay but is suppressed (not in live corpus).

| Target | Entry Type | Count | Referenced By |
|--------|-----------|-------|---------------|
| LAND | fragment_artifact | 5 | GABEL, MINERAL, SCHOOL |
| SECURED | legacy_duplicate | 1 | CREDITOR |

---

## Subentry References (72)

Target term appears within body text of other entries (not standalone).

| Target | Count | Referenced By |
|--------|-------|---------------|
| QUO WARRANTO | Target appears as subentry in  | 2 | INFORMALITY, INFORMATION |
| BUILDING AND | Target appears as subentry in  | 2 | LOADMANAGE, LOAN |
| COURT OF PROBATE | Target appears as subentry in  | 2 | PROBATE, PROBATIS |
| BONA FIDE | Target appears as subentry in  | 2 | PUR, PURCHASER |
| ABJURBATION | Target appears as subentry in  | 1 | ABJURE |
| FRANKALMOIGNE | Target appears as subentry in  | 1 | ALMOIN |
| ALTERA | Target appears as subentry in  | 1 | ALTER |
| BERTILLON SYSTEM | Target appears as subentry in  | 1 | ANTHROPOMETRY |
| APPARENT HEIR | Target appears as subentry in  | 1 | APPEARAND |
| APPRENTICE EN LA LEY | Target appears as subentry in  | 1 | APPRENTICIUS AD LEGEM |
| BANERET | Target appears as subentry in  | 1 | BANNERET |
| PLEA IN BAR | Target appears as subentry in  | 1 | BARATRIAM |
| CAUTIONE | Target appears as subentry in  | 1 | CAUTION |
| OCCUPA | Target appears as subentry in  | 1 | CENSE |
| ADCLERICO CAPTO PER STATUTUM | Target appears as subentry in  | 1 | CLERICO |
| CROWN OFFICE IN CHANCERBY | Target appears as subentry in  | 1 | CLERK |
| DE COLLIGENDUM | Target appears as subentry in  | 1 | COLLIGENDUM |
| TENANTS IN COMMON | Target appears as subentry in  | 1 | COMMON |
| PRESUMP | Target appears as subentry in  | 1 | CONCLUSIVE |
| HEREDIT | Target appears as subentry in  | 1 | CORPOREAL |
| CHAL | Target appears as subentry in  | 1 | DEFECTUS |
| APOSTOLICAE | Target appears as subentry in  | 1 | DIMISSORIAE |
| PRESUMPTIONS | Target appears as subentry in  | 1 | DISPUTE |
| EMINENT DOMAIN | Target appears as subentry in  | 1 | DOMAIN |
| DE DONIS | Target appears as subentry in  | 1 | DONEE |
| DOMESDAY | Target appears as subentry in  | 1 | DOOM |
| PARTNERS | Target appears as subentry in  | 1 | DORMANT |
| AUTER DROIT | Target appears as subentry in  | 1 | EMPTIO REI SPERATA |
| PRIVATE EXAMINATION | Target appears as subentry in  | 1 | EXAMINATION |
| ULTRA VIBES | Target appears as subentry in  | 1 | EXTRA |
| FEIGNED ACTION | Target appears as subentry in  | 1 | FALSE |
| IN FUERI | Target appears as subentry in  | 1 | FIERI |
| COURT OF ERRORS AND APPEALS | Target appears as subentry in  | 1 | GATES |
| SUPREME COURT | Target appears as subentry in  | 1 | GATES |
| DE MEDIETATE | Target appears as subentry in  | 1 | HALF |
| HABEN | Target appears as subentry in  | 1 | HAVE |
| HIBI | Target appears as subentry in  | 1 | HIRE |
| UNDUE INFLUENCE | Target appears as subentry in  | 1 | INFLUENCE |
| THIELAGE | Target appears as subentry in  | 1 | INSTRUMENTA |
| MABITIME INTEBEST | Target appears as subentry in  | 1 | INTEREST |
| CODE CIVIL | Target appears as subentry in  | 1 | JUSTINIAN |
| IN KIND | Target appears as subentry in  | 1 | KIND |
| LN DEMEIES | Target appears as subentry in  | 1 | LANCETI |
| LYING IN | Target appears as subentry in  | 1 | LIE |
| COMMISSION OF ARRAY | Target appears as subentry in  | 1 | LIEUTENANCY |
| INSUR | Target appears as subentry in  | 1 | LIFE |
| GRAND CAPE | Target appears as subentry in  | 1 | MAGNUM |
| DE MEDIETATE LINGUS | Target appears as subentry in  | 1 | MEDIETAS |
| INTERNATION | Target appears as subentry in  | 1 | NATIONALIZACION |
| CONSIDERA | Target appears as subentry in  | 1 | NOMINAL |
| ASSISE OF | Target appears as subentry in  | 1 | NOVEL DISSEISIN |
| NON OBSTANTE | Target appears as subentry in  | 1 | OBSTA |
| AGRE | Target appears as subentry in  | 1 | ORDER |
| TITLE | Target appears as subentry in  | 1 | PAPER |
| OWELTY | Target appears as subentry in  | 1 | PARTITIO |
| JUDEX PEDANEUS | Target appears as subentry in  | 1 | PEDANEUS |
| CHARITABLE USES | Target appears as subentry in  | 1 | PIOUS USES |
| GUARDIANS OF | Target appears as subentry in  | 1 | POOR |
| CHAP | Target appears as subentry in  | 1 | PROPRIETARY |
| NOLLE PROSE | Target appears as subentry in  | 1 | PROSEQUI |
| QUICKEN | Target appears as subentry in  | 1 | QUICK |
| REFE | Target appears as subentry in  | 1 | REFERENCE |
| CORPORA | Target appears as subentry in  | 1 | RELIGIOUS |
| INVOLUN | Target appears as subentry in  | 1 | SERVITUDE |
| LETTERS OF SLAINS | Target appears as subentry in  | 1 | SLAINS |
| JURISDIC | Target appears as subentry in  | 1 | SUMMARY |
| COLLATERAL INHERI | Target appears as subentry in  | 1 | TAX |
| WINDOW | Target appears as subentry in  | 1 | TAX |
| NEGA | Target appears as subentry in  | 1 | TIVE |
| FEHMGERICHT | Target appears as subentry in  | 1 | VEHMGERICHT |
| A VIN | Target appears as subentry in  | 1 | VINCULO MATRIMONII |
| AUNCEL WEIGUT | Target appears as subentry in  | 1 | WEIGHT |

---
