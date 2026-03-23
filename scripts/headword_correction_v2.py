#!/usr/bin/env python3
"""
headword_correction_v2.py — Conservative headword correction for OCR garbles.

Three independent strategies, all conservative:

1. O->C substitution where corrected form exists as verified_main AND
   bodies are highly similar (>0.80 SequenceMatcher) -> mark as duplicate

2. O->C substitution where corrected form does NOT exist in overlay but
   has much higher corpus frequency (count >= 5, ratio > 3x) -> correct

3. Fuzzy match against verified entries (ratio >= 0.92) AND
   body similarity >= 0.80 -> mark as duplicate

Usage:
  python scripts/headword_correction_v2.py --report
  python scripts/headword_correction_v2.py --apply
"""
import json
import re
import sys
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
LIVE_PATH = REPO / "blacks_entries.json"

CANDIDATE_TYPES = {"legacy_unresolved"}

KNOWN_LEGIT = {
    "ACROACH", "ACROOCHER", "ACOROOCHER", "ACOROACH",
    "GARD", "FERMER", "DALE", "SPITAL", "STAPULA",
    "ROUTOUSLY", "INROLL", "ENROLL", "ENROL",
    "DROIT", "EXPLOIT", "FOISON", "OYER",
    "VOITURE", "SEISOR", "DISSEISSOR",
    "AGIO", "RATIO", "ORATIO", "COGNOVIT",
    "SERVO", "PROVO", "PROVOST",
    "DIGAMA", "CARETA", "HEROUD", "DEMY", "FRAUNC",
    "PRIM", "DARIT", "DEACONRY", "DECANIA",
    "HYPOTHECARII", "REHABERE", "RESEALING", "STRICTI",
    "OUT", "CUT", "COT", "COD", "COG", "COP", "COR",
    "COW", "CRO", "CUR", "OAR", "OAT", "ORE",
    "EO", "REO", "GO", "GC", "AO", "AC",
    "ALIO", "DIANATIO", "USUCAPIO",
    "ACCOUNT", "ACCOMMODATION", "ACCOMPLISH", "ACCORDING",
    "ACCORD", "ACCESSION", "ACCESSOR",
    "ACCESSORY", "ACCOLADE",
    "ADVOCATE", "ALCOHOL", "ALLOCATE",
    "ANOMALOUS", "APOSTILLE", "ADOLESCENCE",
    "ADULTEROUS", "AFFIRMATION", "ADMINISTRATOR",
    "AB INITIO", "ACCOUNT-BOOK",
    # Terms confirmed as real from body inspection
    "ACTON", "ADVOWEE", "BLENCH", "FLIGHT", "CAUSE",
    "DAMAGE", "CAUTION", "GROSSE", "MAGNUS", "NETHER",
    "PAYER", "STRAND", "SIGHT", "SOLDER", "VENTRE",
    "SEWARD", "COUVERTURE", "SOLLICITOR", "SOLLICITORS",
}


def normalize_body(body, max_len=300):
    """Normalize body text for comparison."""
    return re.sub(r"\s+", " ", (body or "").upper().strip())[:max_len]


def body_similarity(body1, body2):
    """Compute body similarity ratio."""
    b1 = normalize_body(body1)
    b2 = normalize_body(body2)
    if not b1 or not b2:
        return 0.0
    return SequenceMatcher(None, b1, b2).ratio()


def build_corpus_index(entries):
    """Build word frequency counter."""
    per_entry_bodies = {}
    all_words = []
    for e in entries:
        body = (e.get("body") or "").upper()
        per_entry_bodies[e["term"]] = body
        all_words.extend(re.findall(r"[A-Z]+", body))
    word_counts = Counter(all_words)
    return word_counts, per_entry_bodies


def generate_oc_corrections(term):
    """Generate O->C substitution candidates for each word."""
    words = term.split()
    all_candidates = []

    for wi, word in enumerate(words):
        positions = [i for i, ch in enumerate(word) if ch == "O"]
        if not positions:
            continue

        # Single
        for pos in positions:
            new_word = word[:pos] + "C" + word[pos + 1:]
            new_words = list(words)
            new_words[wi] = new_word
            all_candidates.append(" ".join(new_words))

        # Double
        if len(positions) >= 2:
            for a in range(len(positions)):
                for b in range(a + 1, len(positions)):
                    chars = list(word)
                    chars[positions[a]] = "C"
                    chars[positions[b]] = "C"
                    new_words = list(words)
                    new_words[wi] = "".join(chars)
                    all_candidates.append(" ".join(new_words))

        # Triple
        if len(positions) >= 3:
            for a in range(len(positions)):
                for b in range(a + 1, len(positions)):
                    for c in range(b + 1, len(positions)):
                        chars = list(word)
                        chars[positions[a]] = "C"
                        chars[positions[b]] = "C"
                        chars[positions[c]] = "C"
                        new_words = list(words)
                        new_words[wi] = "".join(chars)
                        all_candidates.append(" ".join(new_words))

    return list(set(all_candidates) - {term})


def main():
    mode = "--report"
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    print("Loading data...")
    with OVERLAY_PATH.open("r", encoding="utf-8") as f:
        overlay = json.load(f)
    with LIVE_PATH.open("r", encoding="utf-8") as f:
        live_entries = json.load(f)

    live_by_term = {e["term"]: e for e in live_entries}
    overlay_by_term = {}
    for e in overlay:
        overlay_by_term.setdefault(e["term"], []).append(e)
    all_overlay_terms = {e["term"] for e in overlay}

    # Verified entries with their bodies
    verified_types = {"verified_main", "provisional_main", "recovered_main", "headword_corrected"}
    verified_entries = {}
    verified_by_first = {}
    for e in overlay:
        if e["entry_type"] in verified_types:
            t = e["term"]
            verified_entries[t] = e
            verified_by_first.setdefault(t[0], []).append(t)

    print("Building corpus index...")
    word_counts, per_entry_bodies = build_corpus_index(live_entries)

    # Get candidates
    already_corrected = {e.get("original_term") for e in overlay if e.get("original_term")}
    already_phantom = {e["term"] for e in overlay if e["entry_type"] == "alias_phantom"}

    candidates = []
    for oe in overlay:
        if oe["entry_type"] not in CANDIDATE_TYPES:
            continue
        if oe["term"] in already_corrected or oe["term"] in already_phantom:
            continue
        if oe["term"] not in live_by_term:
            continue
        candidates.append(oe)

    print(f"Candidates: {len(candidates)}")

    corrections = []
    duplicates = []
    found_terms = set()

    # === Strategy 1: O->C yielding existing verified entry + body similarity ===
    print("Strategy 1: O->C -> verified entry + body check...")
    for oe in candidates:
        term = oe["term"]
        if term in KNOWN_LEGIT or len(term) < 4:
            continue
        if not any("O" in w for w in term.split()):
            continue

        cand_body = per_entry_bodies.get(term, "")
        oc_candidates = generate_oc_corrections(term)

        for corrected in oc_candidates:
            if corrected in verified_entries:
                # Check body similarity
                verified_body = per_entry_bodies.get(corrected, "")
                sim = body_similarity(cand_body, verified_body)
                if sim >= 0.80:
                    ve = verified_entries[corrected]
                    duplicates.append({
                        "term": term,
                        "corrected": corrected,
                        "target_type": ve["entry_type"],
                        "target_id": ve["id"],
                        "body_sim": round(sim, 2),
                        "strategy": "oc_dup",
                        "id": oe["id"],
                    })
                    found_terms.add(term)
                    break
        if term in found_terms:
            continue

    s1_count = len(found_terms)
    print(f"  Found: {s1_count} duplicates")

    # === Strategy 2: O->C yielding non-existent term with high corpus freq ===
    print("Strategy 2: O->C -> high-frequency correction...")
    for oe in candidates:
        term = oe["term"]
        if term in found_terms or term in KNOWN_LEGIT or len(term) < 5:
            continue
        if not any("O" in w for w in term.split()):
            continue

        # Only single-word terms for this strategy (multi-word too risky)
        if " " in term:
            continue

        g_count = word_counts.get(term, 0)
        oc_candidates = generate_oc_corrections(term)

        best = None
        for corrected in oc_candidates:
            if corrected in all_overlay_terms:
                continue
            c_count = word_counts.get(corrected, 0)
            # Must be significantly more common
            if c_count >= 5 and c_count > g_count * 3:
                if best is None or c_count > best[1]:
                    best = (corrected, c_count, g_count)

        if best:
            corrected, c_count, g_count = best
            cand_body = per_entry_bodies.get(term, "")
            in_body = corrected in cand_body
            corrections.append({
                "term": term,
                "corrected": corrected,
                "corpus_count": c_count,
                "garbled_count": g_count,
                "in_own_body": in_body,
                "strategy": "oc_freq",
                "id": oe["id"],
            })
            found_terms.add(term)

    s2_count = len(found_terms) - s1_count
    print(f"  Found: {s2_count} corrections")

    # === Strategy 3: Fuzzy match + body similarity ===
    print("Strategy 3: Fuzzy headword + body similarity...")
    s3_count = 0
    for oe in candidates:
        term = oe["term"]
        if term in found_terms or term in KNOWN_LEGIT or len(term) < 5:
            continue

        first_char = term[0]
        check_chars = {first_char}
        if first_char == "O":
            check_chars.add("C")

        cand_body = per_entry_bodies.get(term, "")
        best_match = None

        for ch in check_chars:
            for vt in verified_by_first.get(ch, []):
                if abs(len(vt) - len(term)) > 2:
                    continue
                hw_ratio = SequenceMatcher(None, term, vt).ratio()
                if hw_ratio < 0.92:
                    continue

                verified_body = per_entry_bodies.get(vt, "")
                b_sim = body_similarity(cand_body, verified_body)
                if b_sim >= 0.80:
                    combined = hw_ratio * 0.3 + b_sim * 0.7
                    if best_match is None or combined > best_match[2]:
                        best_match = (vt, b_sim, combined, hw_ratio)

        if best_match:
            vt, b_sim, combined, hw_ratio = best_match
            ve = verified_entries[vt]
            duplicates.append({
                "term": term,
                "corrected": vt,
                "target_type": ve["entry_type"],
                "target_id": ve["id"],
                "body_sim": round(b_sim, 2),
                "hw_ratio": round(hw_ratio, 2),
                "strategy": "fuzzy_dup",
                "id": oe["id"],
            })
            found_terms.add(term)
            s3_count += 1

    print(f"  Found: {s3_count} fuzzy duplicates")

    # Sort
    corrections = sorted(corrections, key=lambda x: x["term"])
    duplicates = sorted(duplicates, key=lambda x: x["term"])

    # Report
    print(f"\n=== PROPOSED CORRECTIONS ({len(corrections)}) ===")
    for c in corrections:
        flag = " [in body]" if c.get("in_own_body") else ""
        print(f"  {c['term']} -> {c['corrected']} (g={c['garbled_count']}, c={c['corpus_count']}{flag})")

    print(f"\n=== DUPLICATES ({len(duplicates)}) ===")
    for d in duplicates:
        extra = f"body={d['body_sim']}"
        if "hw_ratio" in d:
            extra += f", hw={d['hw_ratio']}"
        print(f"  {d['term']} -> {d['corrected']} ({d['target_type']}) [{d['strategy']}, {extra}]")

    # Write report
    report = {
        "summary": {
            "candidates": len(candidates),
            "corrections": len(corrections),
            "duplicates": len(duplicates),
        },
        "corrections": corrections,
        "duplicates": duplicates,
    }
    report_path = REPO / "rebuild" / "reports" / "headword_correction_v2_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"\nReport: {report_path}")

    if mode == "--apply":
        apply_corrections(overlay, corrections, duplicates)


def apply_corrections(overlay, corrections, duplicates):
    """Apply corrections and duplicate suppressions to the overlay."""
    corrections_by_term = {c["term"]: c for c in corrections}
    duplicates_by_term = {d["term"]: d for d in duplicates}

    changed = 0
    for entry in overlay:
        term = entry["term"]

        if term in corrections_by_term:
            c = corrections_by_term[term]
            entry["original_term"] = term
            entry["term"] = c["corrected"]
            entry["entry_type"] = "headword_corrected"
            entry["correction_evidence"] = {
                "corpus_count": c["corpus_count"],
                "garbled_count": c["garbled_count"],
            }
            changed += 1

        elif term in duplicates_by_term:
            d = duplicates_by_term[term]
            entry["entry_type"] = "legacy_duplicate"
            entry["canonical_target"] = d["corrected"]
            entry["duplicate_evidence"] = f"{d['strategy']}, body_sim={d.get('body_sim', 'n/a')}"
            changed += 1

    with OVERLAY_PATH.open("w", encoding="utf-8") as f:
        json.dump(overlay, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nApplied {changed} changes to overlay")
    print(f"  Corrections: {len(corrections)}")
    print(f"  Duplicates suppressed: {len(duplicates)}")


if __name__ == "__main__":
    main()
