#!/usr/bin/env python3
"""
build_wordlist.py - Build a comprehensive reference wordlist for OCR validation.

Combines:
- Black's Law Dictionary headwords (from the current entries as baseline)
- Latin legal terms
- Law French terms  
- Spanish legal terms
- Common English legal terms

Output: scripts/reference_terms.txt
"""

import json
import re
from pathlib import Path

def main():
    wordlist = set()
    
    # 1. Add current entries as baseline (these are mostly correct)
    print("Loading current entries...")
    with open('blacks_entries.json') as f:
        entries = json.load(f)
    
    for entry in entries:
        term = entry['term'].strip().rstrip('.,;:').upper()
        if len(term) > 2:
            wordlist.add(term)
    
    print(f"  Added {len(wordlist)} terms from current entries")
    
    # 2. Latin legal terms (common ones)
    latin_terms = [
        'ACTUS', 'ANIMUS', 'BONA', 'BONO', 'CAUSA', 'CIVILIS', 'COMMUNIS',
        'CONTRA', 'CORPUS', 'CUM', 'DE', 'DEBITUM', 'DILECTUS', 'DOMINIUM',
        'DONATIO', 'EJUSDEM', 'ESTOPPEL', 'EX', 'FORIS', 'HABENDUM',
        'HABERE', 'INJURIA', 'INTER', 'INTUITU', 'JUS', 'LEGITIMUS',
        'LEX', 'LOCUS', 'MALA', 'MENS', 'MUTATIS', 'NEMO', 'NON',
        'NULLUS', 'ONUS', 'PARS', 'PARTE', 'PATER', 'PER', 'PERSONA',
        'POSSE', 'POSSESSIO', 'POST', 'PRIMA', 'PRO', 'QUANTUM',
        'QUASI', 'QUIA', 'QUO', 'QUOD', 'RATIO', 'RE', 'RES',
        'RITE', 'SALUS', 'SINE', 'SITUS', 'SOLVENDO', 'STATUS',
        'TENENDUM', 'TENENS', 'TENURE', 'TORTUS', 'UBI', 'ULTIMA',
        'UNIVERSITAS', 'USUS', 'VERSUS', 'VIA', 'VICE', 'VINCULO',
        'VIS', 'VOLUNTAS', 'AEQUITAS', 'AEDES', 'AEDIFICARE',
        'AEDIFICATUM', 'AEGROTO', 'AEGYLDE', 'AEFESN', 'AEQUUS',
        'AETAS', 'AETHELING', 'CURIUM', 'CURIAE', 'OCURIZ',
        'ACCRETION', 'ACCRUING', 'ACCRESCERE', 'ACCRESCENTIA'
    ]
    
    for term in latin_terms:
        wordlist.add(term.upper())
    
    print(f"  Added {len(latin_terms)} Latin terms")
    
    # 3. Law French terms (common in Black's)
    law_french_terms = [
        'AVER', 'TENER', 'CONSILHOIS', 'CUEILLETTE', 'MENSA', 'THORO',
        'VINCULO', 'MATRIMONII', 'RUBRO', 'NIGRUM', 'MEMORIA',
        'FORFAIT', 'GARANTIE', 'ESNE', 'SOCAGE', 'FRANK', 'ALMOINE',
        'MORT', 'ANCESTOR', 'DAMAGE', 'DEMESNE', 'EIGNE', 'ELDEST',
        'FEALTY', 'FEE', 'FEOFFMENT', 'FOREST', 'FRANKPLEDGE',
        'GAGE', 'HERIOT', 'HOMAGE', 'HUE', 'JURY', 'LARCENY',
        'MESNE', 'MORTMAIN', 'OYER', 'PLEA', 'PRIMER', 'SEISIN',
        'SUIT', 'TAILLE', 'TENANT', 'TOLL', 'TORT', 'TREASON',
        'WARRANT', 'WASTE', 'WRIT'
    ]
    
    for term in law_french_terms:
        wordlist.add(term.upper())
    
    print(f"  Added {len(law_french_terms)} Law French terms")
    
    # 4. Spanish legal terms (common ones)
    spanish_terms = [
        'GANANCIAS', 'GANANCIALES', 'DERECHO', 'LEYES', 'CORTES',
        'FUERO', 'REAL', 'AUDIENCIA', 'CHANCILLERIA', 'CONSEJO',
        'SUPREMO', 'TRIBUNAL', 'JURISDICCION', 'COMPETENCIA',
        'PROCEDIMIENTO', 'RECURSO', 'CASACION', 'APLICACION',
        'EJECUTIVO', 'JUDICIAL', 'LEGISLATIVO', 'CONGRESO',
        'DIPUTADOS', 'SENADO', 'CONSTITUCION', 'CODIGO',
        'CIVIL', 'PENAL', 'COMERCIO', 'MERCANTIL'
    ]
    
    for term in spanish_terms:
        wordlist.add(term.upper())
    
    print(f"  Added {len(spanish_terms)} Spanish terms")
    
    # 5. Common English legal terms that might be missing
    english_legal = [
        'ABATEMENT', 'ABSTRACT', 'ACCESSION', 'ACCORD', 'ACCRETION',
        'ACCUMULATED', 'ACKNOWLEDGMENT', 'ACQUITTAL', 'ACTION',
        'ACTUAL', 'ADEMPTION', 'ADJOURNMENT', 'ADJUDICATION',
        'ADMINISTRATOR', 'ADMIRALTY', 'ADMISSIBLE', 'ADOPTION',
        'ADVERSE', 'AFFIDAVIT', 'AFFINITY', 'AFFIRMANCE',
        'AGISTMENT', 'ALIENATION', 'ALIMONY', 'ALLEGATION',
        'ALLOCUTION', 'ALLODIAL', 'AMORTIZATION', 'ANCILLARY',
        'ANNUITY', 'ANONymous', 'ANTENUPTIAL', 'APPELLANT',
        'APPELLATE', 'APPORTIONMENT', 'APPRAISEMENT', 'ARBITRAMENT',
        'ARBITRATION', 'ARGUMENT', 'ARRAIGNMENT', 'ARREARAGES',
        'ARRESTMENT', 'ARTICLES', 'ASSAULT', 'ASSIGNMENT',
        'ASSUMPSIT', 'ATTACHMENT', 'ATTAINder', 'ATTORNMENT',
        'AVERMENT', 'AVOWANT', 'AVOWRY', 'BAILMENT', 'BARRATRY',
        'BENEFICIARY', 'BEQUEST', 'BILL', 'BONA', 'BOND',
        'BREACH', 'BRIEF', 'BROKERAGE', 'BURDEN', 'BURGLARY',
        'CANON', 'CAPTION', 'CATTLE', 'CAVEAT', 'CERTIORARI',
        'CESSION', 'CHATTEL', 'CHIVALRY', 'CIRCUIT', 'CITATION',
        'CLAIM', 'CODICIL', 'COLLATERAL', 'COLLISION', 'COMBINATION',
        'COMMENDAM', 'COMMISSARY', 'COMMISSION', 'COMMITMENT',
        'COMMON', 'COMMUTATION', 'COMPACT', 'COMPENSATION',
        'COMPETENCY', 'COMPOSITION', 'COMPROMISE', 'CONCEALMENT',
        'CONCESSION', 'CONCILIATION', 'CONCURRENCE', 'CONDEMNATION',
        'CONDONATION', 'CONFEDERACY', 'CONFIRMATION', 'CONFISCATION',
        'CONFLICT', 'CONFORMITY', 'CONFRONTATION', 'CONFUSION',
        'CONGRESS', 'CONJECTURE', 'CONSANGUINITY', 'CONSCIENCE',
        'CONSENSUS', 'CONSENT', 'CONSEQUENTIAL', 'CONSERVATOR',
        'CONSIDERATION', 'CONSIGNMENT', 'CONSORTIUM', 'CONSPIRACY',
        'CONSTITUTION', 'CONSTRUCTION', 'CONSULTATION', 'CONSUMMATION',
        'CONTEMPT', 'CONTEST', 'CONTINENTAL', 'CONTINGENT',
        'CONTRACT', 'CONTRIBUTION', 'CONTROL', 'CONTROVERSY',
        'CONVEYANCE', 'CONVICTION', 'CORPORATION', 'CORROBORATION',
        'CORRUPTION', 'COSTS', 'COUNSEL', 'COVENANT', 'CREDITOR',
        'CRIME', 'CROSS', 'CRUELTY', 'CULPABLE', 'CUMULATIVE',
        'CUSTODY', 'DAMAGE', 'DEAD', 'DEATH', 'DEBT', 'DECEDENT',
        'DECISION', 'DECLARATION', 'DEDICATION', 'DEDUCTION',
        'DEED', 'DEFAULT', 'DEFEASANCE', 'DEFECT', 'DEFENSE',
        'DEFICIENCY', 'DEGREE', 'DELAY', 'DELEGATION', 'DELIBERATION',
        'DELIVERY', 'DEMAND', 'DEMISE', 'DEMURRER', 'DENIAL',
        'DEPARTMENT', 'DEPENDENT', 'DEPORTATION', 'DEPOSITION',
        'DEPRECIATION', 'DEPRIVATION', 'DERELICTION', 'DERIVATIVE',
        'DESCENT', 'DESERTION', 'DESIGNATION', 'DETAINER', 'DETENTION',
        'DETERMINATION', 'DETINUE', 'DEVASTATION', 'DEVIATION',
        'DEVISE', 'DEVISEE', 'DILIGENCE', 'DIRECT', 'DISABLED',
        'DISABILITY', 'DISALLOWANCE', 'DISBARMENT', 'DISCHARGE',
        'DISCLAIMER', 'DISCONTINUANCE', 'DISCOUNT', 'DISCOVERY',
        'DISCRETION', 'DISCRIMINATION', 'DISFRANCHISEMENT', 'DISHONOR',
        'DISINHERITANCE', 'DISMISSAL', 'DISORDER', 'DISPARAGEMENT',
        'DISPENSATION', 'DISPLACEMENT', 'DISPOSAL', 'DISPOSITION',
        'DISPOSSESS', 'DISPUTE', 'DISQUALIFICATION', 'DISSOLUTION',
        'DISTINCT', 'DISTRESS', 'DISTRIBUTION', 'DISTRICT', 'DISTURBANCE',
        'DIVERSION', 'DIVESTITURE', 'DIVISION', 'DIVORCE', 'DOCKET',
        'DOCUMENT', 'DOMAIN', 'DOMICILE', 'DONATION', 'DOWER',
        'DUE', 'DUTY', 'EASEMENT', 'EJECTMENT', 'ELAPSED', 'ELECTION',
        'ELEGIT', 'ELEMENT', 'ELIGIBILITY', 'EMANCIPATION', 'EMBARGO',
        'EMBEZZLEMENT', 'EMINENT', 'EMOLUMENT', 'EMPHYTEUSIS', 'EMPIRICAL',
        'ENABLING', 'ENACTMENT', 'ENCLOSURE', 'ENCUMBRANCE', 'ENDORSEMENT',
        'ENDOWMENT', 'ENFORCEMENT', 'ENGAGEMENT', 'ENJOYMENT', 'ENLARGEMENT',
        'ENLISTMENT', 'ENTAIL', 'ENTERPRISE', 'ENTERTAINMENT', 'ENTICEMENT',
        'ENTIRETY', 'ENTITY', 'ENTRAPMENT', 'ENTRY', 'EPIQUE', 'EQUALITY',
        'EQUITABLE', 'EQUITY', 'EQUIVALENT', 'ERASURE', 'ERRONEOUS',
        'ERROR', 'ESCAPE', 'ESCHEAT', 'ESCROW', 'ESQUIRE', 'ESSENCE',
        'ESTABLISHMENT', 'ESTATE', 'ESTIMATE', 'ESTOPPEL', 'ESTRAY',
        'ETHICS', 'EVICTION', 'EVIDENCE', 'EVOLUTION', 'EXACTION',
        'EXAMINATION', 'EXCEPTION', 'EXCESS', 'EXCHANGE', 'EXCISE',
        'EXCLUSION', 'EXCOMMUNICATION', 'EXCONCESSION', 'EXCULPATION',
        'EXCUSE', 'EXECUTION', 'EXECUTOR', 'EXEMPTION', 'EXERCISE',
        'EXHAUSTION', 'EXHIBIT', 'EXILE', 'EXISTENCE', 'EXPANSION',
        'EXPECTANCY', 'EXPEDIENCY', 'EXPENSE', 'EXPERIENCE', 'EXPERT',
        'EXPIRATION', 'EXPLICIT', 'EXPLOITATION', 'EXPORT', 'EXPOSITION',
        'EXPOSURE', 'EXPRESSION', 'EXTORTION', 'EXTRA', 'EXTRADITION',
        'EXTRATERRITORIAL', 'EXTREME', 'EYE', 'FABRIC', 'FACILITY',
        'FACT', 'FACTOR', 'FAILURE', 'FAIR', 'FAITH', 'FALSE',
        'FALSIFICATION', 'FAMILY', 'FARM', 'FASCISM', 'FATAL',
        'FATHER', 'FAULT', 'FAVER', 'FEALTY', 'FEAR', 'FEASANCE',
        'FEDERAL', 'FEE', 'FELO', 'FELONY', 'FEME', 'FEUD',
        'FIAT', 'FICTION', 'FIDELITY', 'FIDUCIARY', 'FIEF', 'FIEN',
        'FILIATION', 'FILING', 'FINAL', 'FINANCE', 'FINDING',
        'FINE', 'FINGER', 'FIRM', 'FIRST', 'FISCAL', 'FIXTURE',
        'FLAG', 'FLEEING', 'FLOATING', 'FLOOR', 'FLOTA', 'FLUX',
        'FORCE', 'FORCIBLE', 'FORECLOSURE', 'FOREIGN', 'FORESIGHT',
        'FORFEITURE', 'FORGERY', 'FORM', 'FORMAL', 'FORMATION',
        'FORMULA', 'FORTHWITH', 'FORTRESS', 'FORTUNE', 'FORUM',
        'FORWARD', 'FOSTER', 'FOUNDATION', 'FOUNDER', 'FOUNTAIN',
        'FOURTH', 'FRANCHISE', 'FRATERNAL', 'FRATERNITY', 'FRAUD',
        'FREE', 'FREEDOM', 'FREIGHT', 'FREQUENCY', 'FRESH', 'FRIEND',
        'FRINGE', 'FRISK', 'FRITH', 'FRIVOLITY', 'FRONTIER', 'FROST',
        'FRUIT', 'FRUSTRATION', 'FUGITIVE', 'FULL', 'FUNCTION',
        'FUND', 'FUNDAMENTAL', 'FUNGIBLE', 'FURTHER', 'FUSION',
        'FUTURE', 'GAIN', 'GALE', 'GAME', 'GANG', 'GAOL',
        'GARMENT', 'GARNISHMENT', 'GAS', 'GATE', 'GATHERING',
        'GAUGE', 'GAVEL', 'GENDER', 'GENERAL', 'GENERATION',
        'GENIUS', 'GENOCIDE', 'GENRE', 'GENTLE', 'GENUINE',
        'GERMAN', 'GESTATION', 'GIFT', 'GILD', 'GIST', 'GIVE',
        'GLAD', 'GLASS', 'GLUE', 'GOAL', 'GOD', 'GOLD',
        'GOOD', 'GOODS', 'GOVERNMENT', 'GOVERNOR', 'GRACE',
        'GRADE', 'GRAND', 'GRANT', 'GRANTEE', 'GRANTOR', 'GRAPH',
        'GRATIS', 'GRATITUDE', 'GRATUITOUS', 'GRAVE', 'GRAVITY',
        'GRAY', 'GREAT', 'GREEN', 'GRIEF', 'GRIEVANCE', 'GRIEVOUS',
        'GROUND', 'GROUP', 'GUARANTEE', 'GUARANTOR', 'GUARD',
        'GUARDIAN', 'GUEST', 'GUIDE', 'GUILD', 'GUILT', 'GUILTY',
        'HABEAS', 'HABIT', 'HABITATION', 'HABITUAL', 'HACK', 'HAIL',
        'HAIR', 'HALF', 'HALL', 'HALT', 'HAMLET', 'HAND',
        'HANDWRITING', 'HANGING', 'HARBOR', 'HARD', 'HARM',
        'HARMLESS', 'HARVEST', 'HASTE', 'HATE', 'HAZARD', 'HEAD',
        'HEALTH', 'HEARING', 'HEARSAY', 'HEART', 'HEAT', 'HEAVEN',
        'HEIR', 'HEIRESS', 'HEIRLOOM', 'HELL', 'HELP', 'HEMISPHERE',
        'HERALD', 'HERB', 'HERD', 'HERE', 'HEREAFTER', 'HEREBY',
        'HEREDITAMENT', 'HEREDITARY', 'HEREDITY', 'HEREIN', 'HERESY',
        'HERITAGE', 'HERMAPHRODITE', 'HERO', 'HIDE', 'HIERARCHY',
        'HIGH', 'HIGHWAY', 'HIJACKING', 'HILL', 'HINDRANCE', 'HIP',
        'HIRE', 'HISTORY', 'HIT', 'HIVE', 'HOARD', 'HOBBY',
        'HOLD', 'HOLDER', 'HOLOGRAPH', 'HOLY', 'HOME', 'HOMICIDE',
        'HOMO', 'HONEST', 'HONOR', 'HOOD', 'HOOK', 'HOPE',
        'HORIZON', 'HORN', 'HORROR', 'HORSE', 'HOSPICE', 'HOSPITAL',
        'HOST', 'HOSTAGE', 'HOSTILE', 'HOT', 'HOUR', 'HOUSE',
        'HOUSEHOLD', 'HOVEL', 'HOW', 'HUE', 'HUMAN', 'HUMANE',
        'HUMANITARIAN', 'HUMANITY', 'HUMBUG', 'HUNDRED', 'HUNT',
        'HURRICANE', 'HURT', 'HUSBAND', 'HUSTLING', 'HUT', 'HYBRID',
        'HYDRO', 'HYGIENE', 'HYMN', 'HYPOTHESIS', 'HYSTERIA'
    ]
    
    for term in english_legal:
        wordlist.add(term.upper())
    
    print(f"  Added {len(english_legal)} English legal terms")
    
    # Write output
    Path('scripts').mkdir(exist_ok=True)
    with open('scripts/reference_terms.txt', 'w') as f:
        for term in sorted(wordlist):
            f.write(f'{term}\n')
    
    print(f"\n✅ Total wordlist: {len(wordlist)} terms")
    print(f"   Written to scripts/reference_terms.txt")

if __name__ == '__main__':
    main()
