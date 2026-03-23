#!/usr/bin/env python3
"""
corpus_audit.py — Comprehensive READ-ONLY audit of the Black's Law Dictionary corpus.

Reads:
  - blacks_entries.json              (live corpus)
  - rebuild/overlay/editorial_overlay.json
  - rebuild/out/live_build_report.json
  - data/manifest.json + data/entries_*.json

Writes (reports only):
  - rebuild/reports/audit_findings.json
  - rebuild/reports/audit_summary.md
  - rebuild/reports/regression_probe_status.json

This script does NOT modify any data files.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

# Force UTF-8 stdout on Windows to avoid charmap errors
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

LIVE_CORPUS   = REPO / "blacks_entries.json"
OVERLAY       = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
BUILD_REPORT  = REPO / "rebuild" / "out" / "live_build_report.json"
MANIFEST      = REPO / "data" / "manifest.json"
DATA_DIR      = REPO / "data"
REPORTS_DIR   = REPO / "rebuild" / "reports"

FINDINGS_OUT  = REPORTS_DIR / "audit_findings.json"
SUMMARY_OUT   = REPORTS_DIR / "audit_summary.md"
PROBES_OUT    = REPORTS_DIR / "regression_probe_status.json"

VALID_PAGE_MIN = 1
VALID_PAGE_MAX = 1238

EXCLUDED_TYPES = {
    "alias_phantom",
    "legacy_duplicate",
    "fragment_artifact",
    "junk_headword",
    "appendix_abbrev",
    "legacy_unresolved",
}

MAX_EXAMPLES = 5  # representative examples per audit class


# ── helpers ────────────────────────────────────────────────────────────────────
def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def body_preview(body: str, n: int = 80) -> str:
    return body[:n].replace("\n", " ") if body else ""


def write_json(path: Path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def severity_label(count: int) -> str:
    if count == 0:
        return "clean"
    if count <= 5:
        return "low"
    if count <= 50:
        return "medium"
    return "high"


# ── load data ──────────────────────────────────────────────────────────────────
def load_all():
    print("Loading data files ...")
    live = load_json(LIVE_CORPUS)
    overlay = load_json(OVERLAY)
    build_report = load_json(BUILD_REPORT)
    manifest = load_json(MANIFEST)
    return live, overlay, build_report, manifest


# ── audit 1: suspicious headwords ─────────────────────────────────────────────
def audit_suspicious_headwords(live):
    findings = []
    citation_pattern = re.compile(
        r"^\d+\s+([A-Z]|[A-Za-z]+\.)\s", re.ASCII
    )
    punct_pattern = re.compile(r"[();]")
    period_abbrev = re.compile(r"^[A-Z]{1,4}\.\s*$|^[A-Z]\.[A-Z]")

    for entry in live:
        term = entry["term"]
        reasons = []

        # single-letter terms (except "A")
        if len(term) == 1 and term != "A":
            reasons.append("single_letter")

        # shorter than 2 chars (covers single-letter again, plus empty)
        if len(term) < 2 and term != "A":
            reasons.append("too_short")

        # embedded punctuation (parens, semicolons, periods not in abbreviations)
        if punct_pattern.search(term):
            reasons.append("embedded_punctuation")
        if "." in term and not period_abbrev.match(term):
            # period that doesn't look like an abbreviation
            if not re.match(r"^[A-Z]\.\s*[A-Z]\.", term):  # e.g. U.S.
                reasons.append("suspicious_period")

        # looks like a citation fragment
        if citation_pattern.match(term):
            reasons.append("citation_fragment")

        if reasons:
            findings.append({
                "term": term,
                "reasons": reasons,
                "body_preview": body_preview(entry.get("body", "")),
            })

    return {
        "count": len(findings),
        "severity": severity_label(len(findings)),
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 2: headword / body boundary ─────────────────────────────────────────
def audit_headword_body_boundary(live):
    skip_prefixes = re.compile(
        r"^(In |Lat\.|adj\.|v\.|n\.|Fr\.|Sp\.|Sax\.|Eng\.)", re.IGNORECASE
    )
    allcaps_start = re.compile(r"^([A-Z]{3,})")
    findings = []

    for entry in live:
        body = entry.get("body", "")
        term = entry["term"]
        if not body:
            continue
        if skip_prefixes.match(body):
            continue
        m = allcaps_start.match(body)
        if m:
            caps_word = m.group(1)
            # skip if it matches the headword (normal echo)
            if caps_word == term or term.startswith(caps_word):
                continue
            findings.append({
                "term": term,
                "caps_in_body": caps_word,
                "body_preview": body_preview(body),
            })

    return {
        "count": len(findings),
        "severity": severity_label(len(findings)),
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 3: empty or near-empty body ─────────────────────────────────────────
def audit_empty_or_near_empty(live):
    findings = []
    for entry in live:
        body = entry.get("body", "")
        if len(body) < 20:
            findings.append({
                "term": entry["term"],
                "body_length": len(body),
                "body": body,
            })
    return {
        "count": len(findings),
        "severity": severity_label(len(findings)),
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 4: residual reflow ──────────────────────────────────────────────────
def audit_residual_reflow(live):
    findings = []
    for entry in live:
        body = entry.get("body", "")
        if not body:
            continue
        # Split on \n\n to get paragraphs, then look at single \n within each
        paragraphs = body.split("\n\n")
        bad_breaks = []
        for para in paragraphs:
            lines = para.split("\n")
            for i in range(len(lines) - 1):
                line = lines[i]
                next_line = lines[i + 1]
                if not line or not next_line:
                    continue
                # Skip \n before em-dashes
                if next_line.lstrip().startswith("—") or next_line.lstrip().startswith("--"):
                    continue
                # Skip \n before numbered lists
                if re.match(r"^\s*\d+[\.\)]\s", next_line):
                    continue
                # Check: line ends mid-word (no terminal punctuation, no hyphen)
                # and next line starts lowercase mid-sentence
                ends_mid = (
                    not line.rstrip().endswith(("-", ".", ",", ";", ":", "!", "?", '"', "'", ")"))
                    and len(line.rstrip()) > 0
                    and line.rstrip()[-1].isalpha()
                )
                starts_lower = (
                    len(next_line.lstrip()) > 0
                    and next_line.lstrip()[0].islower()
                )
                if ends_mid and starts_lower:
                    snippet = line[-30:] + " [\\n] " + next_line[:30]
                    bad_breaks.append(snippet)
        if bad_breaks:
            findings.append({
                "term": entry["term"],
                "break_count": len(bad_breaks),
                "samples": bad_breaks[:3],
            })

    return {
        "count": len(findings),
        "severity": severity_label(len(findings)),
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 5: OCR artifacts ────────────────────────────────────────────────────
def audit_ocr_artifacts(live):
    # Digits in word positions like "4nd", "4ll", "4s "
    digit_in_word = re.compile(r"(?<![0-9§\-–,.\/#:])(\d[a-z]{1,3})(?=[\s,;.\)])", re.ASCII)
    # @ sign in body
    at_sign = re.compile(r"@")

    findings = []
    for entry in live:
        body = entry.get("body", "")
        if not body:
            continue
        issues = []

        if at_sign.search(body):
            issues.append("contains_@")

        for m in digit_in_word.finditer(body):
            token = m.group(1)
            # skip ordinals like 1st, 2nd, 3rd, 4th, etc. and common suffixes
            if re.match(r"^\d+(st|nd|rd|th|d|s)$", token):
                continue
            issues.append(f"digit_in_word: '{token}'")

        if issues:
            findings.append({
                "term": entry["term"],
                "issues": issues[:5],
                "body_preview": body_preview(body),
            })

    return {
        "count": len(findings),
        "severity": severity_label(len(findings)),
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 6: duplicate / near-duplicate ────────────────────────────────────────
def audit_duplicate_near_duplicate(live):
    # Group by first letter for efficiency
    by_letter = defaultdict(list)
    for entry in live:
        term = entry["term"]
        if term:
            by_letter[term[0].upper()].append(entry)

    findings = []
    seen_pairs = set()

    for letter, entries in by_letter.items():
        n = len(entries)
        for i in range(n):
            for j in range(i + 1, n):
                t1 = entries[i]["term"]
                t2 = entries[j]["term"]
                pair_key = (min(t1, t2), max(t1, t2))
                if pair_key in seen_pairs:
                    continue
                ratio = SequenceMatcher(None, t1, t2).ratio()
                if ratio >= 0.95:
                    seen_pairs.add(pair_key)
                    findings.append({
                        "term_a": t1,
                        "term_b": t2,
                        "similarity": round(ratio, 4),
                    })

    return {
        "count": len(findings),
        "severity": severity_label(len(findings)),
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 7: source_pages issues ──────────────────────────────────────────────
def audit_source_pages(live):
    out_of_range = []
    empty_array = []
    no_field = []

    for entry in live:
        term = entry["term"]
        if "source_pages" not in entry:
            no_field.append({"term": term})
            continue
        pages = entry["source_pages"]
        if isinstance(pages, list) and len(pages) == 0:
            empty_array.append({"term": term})
            continue
        if isinstance(pages, list):
            bad = []
            for p in pages:
                try:
                    pn = int(p) if isinstance(p, str) else p
                    if not (VALID_PAGE_MIN <= pn <= VALID_PAGE_MAX):
                        bad.append(p)
                except (ValueError, TypeError):
                    bad.append(p)  # non-numeric page value
            if bad:
                out_of_range.append({"term": term, "bad_pages": bad, "all_pages": pages})

    findings = {
        "out_of_range": {
            "count": len(out_of_range),
            "severity": severity_label(len(out_of_range)),
            "examples": out_of_range[:MAX_EXAMPLES],
            "all": out_of_range,
        },
        "empty_array": {
            "count": len(empty_array),
            "severity": severity_label(len(empty_array)),
            "examples": empty_array[:MAX_EXAMPLES],
        },
        "no_field": {
            "count": len(no_field),
            "severity": severity_label(len(no_field)),
            "examples": no_field[:MAX_EXAMPLES],
        },
    }
    return findings


# ── audit 8: unresolved cross-references ──────────────────────────────────────
def audit_unresolved_crossrefs(live):
    live_terms = {e["term"].upper() for e in live}
    see_pattern = re.compile(r"\bSee ([A-Z][A-Z ]{2,})")
    findings = []
    ref_counter = Counter()

    for entry in live:
        body = entry.get("body", "")
        if not body:
            continue
        for m in see_pattern.finditer(body):
            ref = m.group(1).strip()
            # Trim trailing spaces
            ref = ref.rstrip()
            if ref.upper() not in live_terms:
                ref_counter[ref] += 1
                findings.append({
                    "term": entry["term"],
                    "referenced": ref,
                    "body_snippet": body[max(0, m.start() - 20):m.end() + 20],
                })

    # deduplicate by referenced term for the summary
    unique_refs = sorted(ref_counter.items(), key=lambda x: -x[1])

    return {
        "count": len(findings),
        "unique_missing_refs": len(unique_refs),
        "severity": severity_label(len(unique_refs)),
        "top_missing_refs": [{"ref": r, "occurrences": c} for r, c in unique_refs[:20]],
        "examples": findings[:MAX_EXAMPLES],
        "all": findings,
    }


# ── audit 9: manifest / split consistency ─────────────────────────────────────
def audit_manifest_split(live, manifest):
    live_count = len(live)
    manifest_total = sum(v["count"] for v in manifest.values())
    issues = []

    if manifest_total != live_count:
        issues.append({
            "issue": "manifest_total_mismatch",
            "manifest_total": manifest_total,
            "live_count": live_count,
        })

    # Load each split file, check counts
    split_terms = {}
    for letter, info in manifest.items():
        split_path = REPO / info["file"]
        if not split_path.exists():
            issues.append({"issue": "split_file_missing", "letter": letter, "path": str(split_path)})
            continue
        split_data = load_json(split_path)
        actual_count = len(split_data)
        if actual_count != info["count"]:
            issues.append({
                "issue": "split_count_mismatch",
                "letter": letter,
                "manifest_count": info["count"],
                "actual_count": actual_count,
            })
        for e in split_data:
            t = e["term"]
            if t in split_terms:
                issues.append({
                    "issue": "term_in_multiple_splits",
                    "term": t,
                    "files": [split_terms[t], info["file"]],
                })
            split_terms[t] = info["file"]

    # Check every live entry appears in exactly one split
    live_terms = {e["term"] for e in live}
    missing_from_split = live_terms - set(split_terms.keys())
    extra_in_split = set(split_terms.keys()) - live_terms

    if missing_from_split:
        issues.append({
            "issue": "live_entries_not_in_splits",
            "count": len(missing_from_split),
            "examples": sorted(list(missing_from_split))[:MAX_EXAMPLES],
        })
    if extra_in_split:
        issues.append({
            "issue": "split_entries_not_in_live",
            "count": len(extra_in_split),
            "examples": sorted(list(extra_in_split))[:MAX_EXAMPLES],
        })

    return {
        "manifest_total": manifest_total,
        "live_count": live_count,
        "match": manifest_total == live_count and len(issues) == 0,
        "issue_count": len(issues),
        "severity": severity_label(len(issues)),
        "issues": issues,
    }


# ── audit 10: overlay accounting ──────────────────────────────────────────────
def audit_overlay_accounting(live, overlay, build_report):
    issues = []

    # Build lookup structures
    overlay_by_id = {}
    overlay_dup_ids = []
    for entry in overlay:
        eid = entry["id"]
        if eid in overlay_by_id:
            overlay_dup_ids.append(eid)
        overlay_by_id[eid] = entry

    live_term_set = {e["term"] for e in live}

    build_entries = build_report.get("entries", [])
    build_by_id = {}
    build_dup_ids = []
    for entry in build_entries:
        eid = entry["id"]
        if eid in build_by_id:
            build_dup_ids.append(eid)
        build_by_id[eid] = entry

    # Every overlay entry must be in live build OR have an excluded type
    overlay_not_accounted = []
    for entry in overlay:
        eid = entry["id"]
        etype = entry.get("entry_type", "")
        if eid not in build_by_id and etype not in EXCLUDED_TYPES:
            overlay_not_accounted.append({
                "id": eid,
                "term": entry["term"],
                "entry_type": etype,
            })

    # Every live entry's ID must trace back to overlay
    live_not_in_overlay = []
    for entry in build_entries:
        eid = entry["id"]
        if eid not in overlay_by_id:
            live_not_in_overlay.append({
                "id": eid,
                "term": entry["term"],
            })

    if overlay_dup_ids:
        issues.append({
            "issue": "duplicate_ids_in_overlay",
            "count": len(overlay_dup_ids),
            "examples": overlay_dup_ids[:MAX_EXAMPLES],
        })
    if build_dup_ids:
        issues.append({
            "issue": "duplicate_ids_in_build",
            "count": len(build_dup_ids),
            "examples": build_dup_ids[:MAX_EXAMPLES],
        })
    if overlay_not_accounted:
        issues.append({
            "issue": "overlay_entries_not_in_live_or_excluded",
            "count": len(overlay_not_accounted),
            "examples": overlay_not_accounted[:MAX_EXAMPLES],
        })
    if live_not_in_overlay:
        issues.append({
            "issue": "live_entries_not_in_overlay",
            "count": len(live_not_in_overlay),
            "examples": live_not_in_overlay[:MAX_EXAMPLES],
        })

    return {
        "overlay_total": len(overlay),
        "live_total": len(build_entries),
        "excluded_types": sorted(EXCLUDED_TYPES),
        "issue_count": len(issues),
        "severity": severity_label(len(issues)),
        "issues": issues,
    }


# ── regression probes ─────────────────────────────────────────────────────────
def run_regression_probes(live, overlay):
    EXPECTED_LIVE = [
        "A POSTERIORI", "A QUO", "BADGE", "BAIL", "ABSTRACT", "MORTGAGE",
        "A PRENDRE", "AEGYLDE", "ARRIERE VASSAL", "BANKER", "BILLET",
        "CABALLERO", "CONSIGNOR", "AB INCONVENIENTI", "AEDILITIUM EDICTUM",
    ]
    EXPECTED_SUPPRESSED = [
        "I N", "L P", "S W", "FOLK-LAND FOLK-LAND; FOLK-MOTE",
        "CORRODY", "FORSTALL",
    ]
    STATUS_TO_VERIFY = [
        "ACCESSORY OCONTRAOT", "ACCOMENDA", "APOORISARIUS",
        "COURTS OF ASSIZE AND NISI PRIUS", "N.P", "QO", "Y.", "T",  # removed ")" to keep it as string
    ]

    live_by_term = {e["term"]: e for e in live}
    overlay_by_term = {e["term"]: e for e in overlay}

    results = []

    all_probes = (
        [(t, "expected_live") for t in EXPECTED_LIVE]
        + [(t, "expected_suppressed") for t in EXPECTED_SUPPRESSED]
        + [(t, "status_to_verify") for t in STATUS_TO_VERIFY]
    )

    for term, expectation in all_probes:
        probe = {"term": term, "expectation": expectation}

        if term in live_by_term:
            probe["status"] = "live_headword"
            probe["body_preview"] = body_preview(live_by_term[term].get("body", ""))
        elif term in overlay_by_term:
            etype = overlay_by_term[term].get("entry_type", "unknown")
            probe["status"] = "suppressed"
            probe["entry_type"] = etype
        else:
            probe["status"] = "absent"

        # Always include entry_type from overlay if present
        if term in overlay_by_term and "entry_type" not in probe:
            probe["entry_type"] = overlay_by_term[term].get("entry_type", "unknown")
        elif term in overlay_by_term:
            pass  # already set
        # If it's live, also grab overlay entry_type for reference
        if term in overlay_by_term and probe["status"] == "live_headword":
            probe["entry_type"] = overlay_by_term[term].get("entry_type", "unknown")

        results.append(probe)

    return results


# ── markdown summary ──────────────────────────────────────────────────────────
def build_summary_md(findings, probes):
    lines = [
        "# Corpus Audit Summary",
        "",
        f"**Date**: generated by `corpus_audit.py`",
        "",
        "## Audit Classes",
        "",
    ]

    class_order = [
        ("suspicious_headwords", "Suspicious Headwords"),
        ("headword_body_boundary", "Headword/Body Boundary"),
        ("empty_or_near_empty_body", "Empty or Near-Empty Body"),
        ("residual_reflow", "Residual Reflow"),
        ("ocr_artifacts", "OCR Artifacts"),
        ("duplicate_near_duplicate", "Duplicate / Near-Duplicate"),
        ("source_pages_issues", "Source Pages Issues"),
        ("unresolved_crossrefs", "Unresolved Cross-References"),
        ("manifest_split_consistency", "Manifest / Split Consistency"),
        ("overlay_accounting", "Overlay Accounting"),
    ]

    for key, title in class_order:
        data = findings[key]
        lines.append(f"### {title}")
        lines.append("")

        if key == "source_pages_issues":
            for sub in ("out_of_range", "empty_array", "no_field"):
                sub_data = data[sub]
                lines.append(f"- **{sub}**: {sub_data['count']} ({sub_data['severity']})")
                for ex in sub_data.get("examples", [])[:3]:
                    lines.append(f"  - `{ex['term']}`" + (f" pages={ex.get('bad_pages','')}" if 'bad_pages' in ex else ""))
            lines.append("")
            continue

        count = data.get("count", data.get("issue_count", 0))
        sev = data.get("severity", "unknown")
        lines.append(f"- **Count**: {count}  |  **Severity**: {sev}")
        lines.append("")

        examples = data.get("examples", [])
        if examples:
            lines.append("**Representative examples:**")
            lines.append("")
            for ex in examples[:MAX_EXAMPLES]:
                if isinstance(ex, dict):
                    parts = []
                    for k, v in ex.items():
                        if k == "all":
                            continue
                        parts.append(f"{k}=`{v}`")
                    lines.append(f"- {' | '.join(parts)}")
                else:
                    lines.append(f"- `{ex}`")
            lines.append("")

        # Extra details for specific audits
        if key == "manifest_split_consistency":
            lines.append(f"- Manifest total: {data.get('manifest_total')}  |  Live count: {data.get('live_count')}")
            lines.append(f"- Match: {data.get('match')}")
            lines.append("")

        if key == "overlay_accounting":
            lines.append(f"- Overlay total: {data.get('overlay_total')}  |  Live total: {data.get('live_total')}")
            lines.append("")

        if key == "unresolved_crossrefs":
            lines.append(f"- Unique missing refs: {data.get('unique_missing_refs', 0)}")
            top = data.get("top_missing_refs", [])
            if top:
                lines.append("")
                lines.append("**Top missing references:**")
                lines.append("")
                for r in top[:10]:
                    lines.append(f"- `{r['ref']}` ({r['occurrences']} occurrences)")
            lines.append("")

    # Regression probes
    lines.append("## Regression Probe Status")
    lines.append("")
    lines.append("| Term | Expectation | Status | Entry Type | Body Preview |")
    lines.append("|------|-------------|--------|------------|--------------|")
    for p in probes:
        term = p["term"]
        expect = p["expectation"]
        status = p["status"]
        etype = p.get("entry_type", "--")
        preview = p.get("body_preview", "--")
        # Escape pipes in preview
        preview = preview.replace("|", "\\|")
        lines.append(f"| {term} | {expect} | {status} | {etype} | {preview} |")
    lines.append("")

    return "\n".join(lines)


# ── main ───────────────────────────────────────────────────────────────────────
def main():
    live, overlay, build_report, manifest = load_all()
    print(f"  Live corpus: {len(live)} entries")
    print(f"  Overlay:     {len(overlay)} entries")
    print(f"  Build report entries: {len(build_report.get('entries', []))}")
    print()

    findings = {}

    print("[1/10] Suspicious headwords ...")
    findings["suspicious_headwords"] = audit_suspicious_headwords(live)
    print(f"       ->{findings['suspicious_headwords']['count']} found")

    print("[2/10] Headword/body boundary ...")
    findings["headword_body_boundary"] = audit_headword_body_boundary(live)
    print(f"       ->{findings['headword_body_boundary']['count']} found")

    print("[3/10] Empty or near-empty body ...")
    findings["empty_or_near_empty_body"] = audit_empty_or_near_empty(live)
    print(f"       ->{findings['empty_or_near_empty_body']['count']} found")

    print("[4/10] Residual reflow ...")
    findings["residual_reflow"] = audit_residual_reflow(live)
    print(f"       ->{findings['residual_reflow']['count']} found")

    print("[5/10] OCR artifacts ...")
    findings["ocr_artifacts"] = audit_ocr_artifacts(live)
    print(f"       ->{findings['ocr_artifacts']['count']} found")

    print("[6/10] Duplicate / near-duplicate headwords ...")
    findings["duplicate_near_duplicate"] = audit_duplicate_near_duplicate(live)
    print(f"       ->{findings['duplicate_near_duplicate']['count']} found")

    print("[7/10] Source pages issues ...")
    sp = audit_source_pages(live)
    findings["source_pages_issues"] = sp
    print(f"       ->out_of_range={sp['out_of_range']['count']}  empty={sp['empty_array']['count']}  no_field={sp['no_field']['count']}")

    print("[8/10] Unresolved cross-references ...")
    findings["unresolved_crossrefs"] = audit_unresolved_crossrefs(live)
    print(f"       ->{findings['unresolved_crossrefs']['count']} refs, {findings['unresolved_crossrefs']['unique_missing_refs']} unique missing")

    print("[9/10] Manifest / split consistency ...")
    findings["manifest_split_consistency"] = audit_manifest_split(live, manifest)
    print(f"       ->match={findings['manifest_split_consistency']['match']}  issues={findings['manifest_split_consistency']['issue_count']}")

    print("[10/10] Overlay accounting ...")
    findings["overlay_accounting"] = audit_overlay_accounting(live, overlay, build_report)
    print(f"       ->issues={findings['overlay_accounting']['issue_count']}")

    print()
    print("Running regression probes ...")
    probes = run_regression_probes(live, overlay)
    live_probes = sum(1 for p in probes if p["status"] == "live_headword")
    suppressed_probes = sum(1 for p in probes if p["status"] == "suppressed")
    absent_probes = sum(1 for p in probes if p["status"] == "absent")
    print(f"  ->{live_probes} live, {suppressed_probes} suppressed, {absent_probes} absent")

    # ── strip "all" lists from findings for the JSON output (keep examples only) ──
    findings_clean = {}
    for key, val in findings.items():
        if isinstance(val, dict) and "all" in val:
            findings_clean[key] = {k: v for k, v in val.items() if k != "all"}
        elif isinstance(val, dict):
            cleaned = {}
            for k2, v2 in val.items():
                if isinstance(v2, dict) and "all" in v2:
                    cleaned[k2] = {k: v for k, v in v2.items() if k != "all"}
                else:
                    cleaned[k2] = v2
            findings_clean[key] = cleaned
        else:
            findings_clean[key] = val

    # ── write outputs ──────────────────────────────────────────────────────────
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print()
    print(f"Writing {FINDINGS_OUT} ...")
    write_json(FINDINGS_OUT, findings_clean)

    print(f"Writing {PROBES_OUT} ...")
    write_json(PROBES_OUT, probes)

    summary_md = build_summary_md(findings_clean, probes)
    print(f"Writing {SUMMARY_OUT} ...")
    with open(SUMMARY_OUT, "w", encoding="utf-8") as f:
        f.write(summary_md)

    # ── stdout summary ─────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  CORPUS AUDIT SUMMARY")
    print("=" * 60)
    for key, title in [
        ("suspicious_headwords", "Suspicious Headwords"),
        ("headword_body_boundary", "Headword/Body Boundary"),
        ("empty_or_near_empty_body", "Empty/Near-Empty Body"),
        ("residual_reflow", "Residual Reflow"),
        ("ocr_artifacts", "OCR Artifacts"),
        ("duplicate_near_duplicate", "Duplicate/Near-Dup"),
        ("unresolved_crossrefs", "Unresolved Crossrefs"),
    ]:
        d = findings_clean[key]
        c = d.get("count", 0)
        s = d.get("severity", "?")
        print(f"  {title:30s}  {c:>5d}  [{s}]")

    sp = findings_clean["source_pages_issues"]
    print(f"  {'Source Pages (out of range)':30s}  {sp['out_of_range']['count']:>5d}  [{sp['out_of_range']['severity']}]")
    print(f"  {'Source Pages (empty array)':30s}  {sp['empty_array']['count']:>5d}  [{sp['empty_array']['severity']}]")
    print(f"  {'Source Pages (no field)':30s}  {sp['no_field']['count']:>5d}  [{sp['no_field']['severity']}]")

    mc = findings_clean["manifest_split_consistency"]
    print(f"  {'Manifest/Split Consistency':30s}  {'OK' if mc['match'] else 'FAIL':>5s}  [{mc['severity']}]")

    oa = findings_clean["overlay_accounting"]
    print(f"  {'Overlay Accounting':30s}  {oa['issue_count']:>5d}  [{oa['severity']}]")

    print("-" * 60)
    print(f"  Regression Probes: {live_probes} live / {suppressed_probes} suppressed / {absent_probes} absent")
    print("=" * 60)
    print()
    print("Done. Full reports written to rebuild/reports/.")


if __name__ == "__main__":
    main()
