#!/usr/bin/env python3
"""
running_header_extraction.py — Extract running headers from source_pages.jsonl
and detect gaps in the corpus based on expected alphabetical coverage.

Step 1: Extract running headers from each page
Step 2: Compare header terms against corpus and overlay
Step 3: Classify gaps as subentry, OCR noise, or genuine gap

Running header format in Black's 2nd Ed:
  - Even pages (verso): PAGE_NUM    FIRST_HEADWORD
  - Odd pages (recto):  LAST_HEADWORD    PAGE_NUM
  - Some pages: HEADWORD PAGE_NUM (single term with page number)
  - OCR often merges header with body text or garbles capitalization
"""

import json
import re
from pathlib import Path
from collections import defaultdict

REPO = Path(".")
SOURCE_PAGES = REPO / "rebuild" / "out" / "source_pages.jsonl"
LIVE_CORPUS = REPO / "blacks_entries.json"
OVERLAY_PATH = REPO / "rebuild" / "overlay" / "editorial_overlay.json"
HEADERS_JSON = REPO / "rebuild" / "reports" / "running_header_extraction.json"
GAPS_MD = REPO / "rebuild" / "reports" / "running_header_gaps.md"
HEADERS_OUT = REPO / "rebuild" / "out" / "running_headers.json"

FIRST_CONTENT_LEAF = 12
LAST_CONTENT_LEAF = 1240


def levenshtein(s1, s2):
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if c1 == c2 else 1)))
        prev = curr
    return prev[-1]


def normalize_term(s):
    """Normalize a term for comparison."""
    s = s.strip().upper()
    s = s.replace("\u00c6", "AE").replace("\u00e6", "AE")
    s = s.replace("\u0152", "OE").replace("\u0153", "OE")
    s = re.sub(r'[.,;:\-\u2014\[\]{}()\'"<>]+$', '', s).strip()
    s = re.sub(r'^[.,;:\-\u2014\[\]{}()\'"<>_\\]+', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def is_running_header(line, printed_page=None):
    """Determine if a line looks like a running header."""
    line = line.strip()
    if not line:
        return False
    if len(line) > 80:
        return False
    alpha_chars = sum(1 for c in line if c.isalpha())
    if alpha_chars < 2:
        return False
    upper_chars = sum(1 for c in line if c.isupper())
    lower_chars = sum(1 for c in line if c.islower())
    if lower_chars > upper_chars * 0.3:
        return False
    if line.startswith(('(', '"', "'", 'the ', 'The ', 'a ', 'an ', 'of ', 'to ', 'in ', 'by ')):
        return False
    return True


def try_extract_header(line):
    """Try to extract header from a possibly merged header+body line."""
    line = line.strip()
    if not line:
        return None
    m = re.match(r'^([A-Z][A-Z\s.,;\-]{2,}?)\s+(\d{1,4})\b', line)
    if m:
        header_part = m.group(1).strip()
        page_num = m.group(2)
        if len(header_part) >= 3 and int(page_num) < 1300:
            return header_part + " " + page_num
    if len(line) < 60:
        upper_chars = sum(1 for c in line if c.isupper())
        lower_chars = sum(1 for c in line if c.islower())
        if upper_chars > 0 and lower_chars <= upper_chars * 0.2:
            return line
    return None


def parse_header(raw_header):
    """Parse a running header into (first_term, last_term)."""
    h = raw_header.strip()
    h = re.sub(r'^\d+\s+', '', h)
    h = re.sub(r'\s+\d+$', '', h)
    h = re.sub(r'^[.:;,\-\s_\\]+', '', h)
    h = re.sub(r'[.:;,\-\s>]+$', '', h)
    if not h or len(h) < 2:
        return None, None
    # Fix common OCR substitutions
    h = re.sub(r'\bOO', 'CO', h)
    parts = re.split(r'\s{3,}|\s+[-\u2014]\s+', h)
    if len(parts) >= 2:
        first = normalize_term(parts[0])
        last = normalize_term(parts[-1])
        if first and last and len(first) >= 2 and len(last) >= 2:
            return first, last
    term = normalize_term(h)
    if len(term) >= 2:
        return term, term
    return None, None


def load_source_pages():
    pages = []
    with open(SOURCE_PAGES, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                pages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return pages


def step1_extract_headers(pages):
    """Extract running headers from each content page."""
    print("=== Step 1: Extract Running Headers ===\n")
    headers = []
    header_count = 0
    no_header_count = 0

    for page in pages:
        leaf = page.get("leaf", 0)
        if leaf < FIRST_CONTENT_LEAF or leaf > LAST_CONTENT_LEAF:
            continue
        printed_page = page.get("printed_page")
        lines = page.get("lines", [])
        nonempty = []
        for l in lines[:6]:
            if l.strip():
                nonempty.append(l.strip())
                if len(nonempty) >= 3:
                    break
        raw_header = None
        first_term = None
        last_term = None

        if nonempty and is_running_header(nonempty[0], printed_page):
            raw_header = nonempty[0]
            first_term, last_term = parse_header(raw_header)
        if not first_term and len(nonempty) >= 2 and is_running_header(nonempty[1], printed_page):
            raw_header = nonempty[1]
            first_term, last_term = parse_header(raw_header)
        if not first_term and nonempty:
            extracted = try_extract_header(nonempty[0])
            if extracted:
                raw_header = extracted
                first_term, last_term = parse_header(raw_header)

        if first_term:
            header_count += 1
        else:
            no_header_count += 1

        headers.append({
            "leaf": leaf,
            "printed_page": printed_page,
            "first_term": first_term,
            "last_term": last_term,
            "raw_header": raw_header,
        })

    print(f"  Content pages scanned: {len(headers)}")
    print(f"  Pages with headers:    {header_count}")
    print(f"  Pages without headers: {no_header_count}")
    return headers


def step2_gap_detection(headers, live_entries, overlay):
    """Detect and classify gaps."""
    print("\n=== Step 2: Gap Detection ===\n")

    # Build indices
    corpus_terms = set()
    corpus_by_page = defaultdict(list)
    all_bodies = []
    for e in live_entries:
        term = e["term"].upper()
        corpus_terms.add(term)
        all_bodies.append(e.get("body", "").upper())
        for sp in e.get("source_pages", []):
            corpus_by_page[sp].append(term)

    all_body_text = " ".join(all_bodies)

    overlay_by_term = {}
    for e in overlay:
        t = e.get("term", "").upper()
        if t:
            overlay_by_term[t] = e

    valid_headers = [h for h in headers if h["first_term"]]

    # Classify each header term
    exact_corpus = 0
    fuzzy_corpus = 0
    suppressed = 0
    subentry_in_body = 0
    ocr_noise_count = 0
    genuine_gap_count = 0

    classified = []
    seen_terms = set()

    for h in valid_headers:
        leaf = h["leaf"]
        for term_key in ["first_term", "last_term"]:
            term = h.get(term_key)
            if not term or term in seen_terms:
                continue
            seen_terms.add(term)

            # 1. Exact corpus match
            if term in corpus_terms:
                exact_corpus += 1
                continue

            # 2. Exact overlay match (suppressed)
            if term in overlay_by_term:
                oe = overlay_by_term[term]
                etype = oe.get("entry_type", "?")
                suppressed += 1
                continue

            # 3. Fuzzy match in corpus (Levenshtein <= 2)
            best_dist = 3
            best_match = None
            for ct in corpus_terms:
                if abs(len(ct) - len(term)) > 2:
                    continue
                d = levenshtein(term, ct)
                if d < best_dist:
                    best_dist = d
                    best_match = ct
                if d == 0:
                    break
            if best_match:
                fuzzy_corpus += 1
                continue

            # 4. Fuzzy match in overlay
            best_dist_o = 3
            for ot in overlay_by_term:
                if abs(len(ot) - len(term)) > 2:
                    continue
                d = levenshtein(term, ot)
                if d < best_dist_o:
                    best_dist_o = d
                if d == 0:
                    break
            if best_dist_o <= 2:
                suppressed += 1
                continue

            # 5. Check if term appears in entry bodies (subentry/maxim)
            if term in all_body_text:
                subentry_in_body += 1
                classified.append({
                    "leaf": leaf,
                    "header_term": term,
                    "raw_header": h["raw_header"],
                    "classification": "SUBENTRY_IN_BODY",
                })
                continue

            # 6. Check for OCR noise patterns
            is_ocr = False
            if re.search(r'[§{}><\[\]|©°]', term):
                is_ocr = True
            elif re.match(r'^[A-Z]\.$', term):
                is_ocr = True
            elif len(term) <= 2:
                is_ocr = True
            elif term in ("BLACK'S DICTIONARY OF LAW",):
                is_ocr = True
            elif re.search(r'\d{3,}', term):  # Contains page numbers
                is_ocr = True
            elif re.search(r'[A-Z]\. [A-Z]', term) and len(term.split()) > 4:
                # Header with body text merged
                is_ocr = True

            if is_ocr:
                ocr_noise_count += 1
                classified.append({
                    "leaf": leaf,
                    "header_term": term,
                    "raw_header": h["raw_header"],
                    "classification": "OCR_NOISE",
                })
                continue

            # 7. Genuine gap
            genuine_gap_count += 1
            classified.append({
                "leaf": leaf,
                "header_term": term,
                "raw_header": h["raw_header"],
                "classification": "GENUINE_GAP",
            })

    print(f"  Unique header terms:       {len(seen_terms)}")
    print(f"  Exact corpus matches:      {exact_corpus}")
    print(f"  Fuzzy corpus matches:      {fuzzy_corpus}")
    print(f"  In overlay (suppressed):   {suppressed}")
    print(f"  Subentries in body text:   {subentry_in_body}")
    print(f"  OCR noise discarded:       {ocr_noise_count}")
    print(f"  Genuine gaps:              {genuine_gap_count}")

    return classified, seen_terms


def write_reports(headers, classified, seen_terms):
    """Write output files."""
    with open(HEADERS_OUT, "w", encoding="utf-8") as f:
        json.dump(headers, f, indent=2, ensure_ascii=False)
    print(f"\nWrote: {HEADERS_OUT}")

    pages_with = sum(1 for h in headers if h["first_term"])
    genuine = [c for c in classified if c["classification"] == "GENUINE_GAP"]
    subentries = [c for c in classified if c["classification"] == "SUBENTRY_IN_BODY"]
    ocr = [c for c in classified if c["classification"] == "OCR_NOISE"]

    extraction_data = {
        "total_content_pages": len(headers),
        "pages_with_headers": pages_with,
        "unique_header_terms": len(seen_terms),
        "genuine_gaps": len(genuine),
        "subentries_in_body": len(subentries),
        "ocr_noise": len(ocr),
        "classified": classified,
        "headers": headers,
    }
    with open(HEADERS_JSON, "w", encoding="utf-8") as f:
        json.dump(extraction_data, f, indent=2, ensure_ascii=False)
    print(f"Wrote: {HEADERS_JSON}")

    # Markdown report
    pct = pages_with * 100 // len(headers) if headers else 0
    md = [
        "# Running Header Gap Analysis",
        "",
        f"Extracted running headers from {pages_with} of {len(headers)} content pages ({pct}% extraction rate).",
        f"Identified {len(seen_terms)} unique header terms.",
        "",
        "## Classification Summary",
        "",
        "| Category | Count | Description |",
        "|----------|-------|-------------|",
        f"| Exact corpus match | {len(seen_terms) - len(classified)} | Header term found in live corpus |",
        f"| Subentry in body | {len(subentries)} | Term appears in entry body text (maxim, subentry) |",
        f"| OCR noise | {len(ocr)} | Garbled header extraction artifact |",
        f"| Genuine gap | {len(genuine)} | Not found anywhere in pipeline |",
        "",
        "Note: The 23% extraction rate is because most pages in the DjVu OCR",
        "do not cleanly separate running headers from body text. The header is",
        "often merged with the first line of body text during text extraction.",
        "This means the gap analysis is necessarily incomplete — it can only",
        "detect gaps on the ~23% of pages where a header was successfully extracted.",
        "",
        "---",
        "",
    ]

    if genuine:
        md.append(f"## Genuine Gaps ({len(genuine)} entries)")
        md.append("")
        md.append("These header terms were not found via exact or fuzzy match (Levenshtein <= 2)")
        md.append("in the live corpus, overlay, or entry body text.")
        md.append("")
        md.append("| Leaf | Header Term | Raw Header |")
        md.append("|------|------------|-----------|")
        for g in genuine:
            raw = (g.get("raw_header") or "").replace("|", "/")
            md.append(f"| {g['leaf']} | {g['header_term']} | {raw} |")
        md.extend(["", "---", ""])

    if subentries:
        md.append(f"## Subentries in Body Text ({len(subentries)} entries)")
        md.append("")
        md.append("These terms appear in entry body text as subentries, maxims, or cross-references.")
        md.append("They are not standalone headwords but exist within the corpus.")
        md.append("")
        md.append("| Leaf | Header Term | Raw Header |")
        md.append("|------|------------|-----------|")
        for s in subentries:
            raw = (s.get("raw_header") or "").replace("|", "/")
            md.append(f"| {s['leaf']} | {s['header_term']} | {raw} |")
        md.extend(["", "---", ""])

    if ocr:
        md.append(f"## OCR Noise ({len(ocr)} entries)")
        md.append("")
        md.append("| Leaf | Header Term | Raw Header |")
        md.append("|------|------------|-----------|")
        for n in ocr:
            raw = (n.get("raw_header") or "").replace("|", "/")
            md.append(f"| {n['leaf']} | {n['header_term']} | {raw} |")
        md.append("")

    with open(GAPS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"Wrote: {GAPS_MD}")


def main():
    print("Loading source pages...")
    pages = load_source_pages()
    print(f"  {len(pages)} pages loaded")

    print("Loading live corpus...")
    live = json.load(open(LIVE_CORPUS, encoding="utf-8"))
    print(f"  {len(live)} live entries")

    print("Loading overlay...")
    overlay = json.load(open(OVERLAY_PATH, encoding="utf-8"))
    print(f"  {len(overlay)} overlay entries\n")

    headers = step1_extract_headers(pages)
    classified, seen_terms = step2_gap_detection(headers, live, overlay)
    write_reports(headers, classified, seen_terms)

    print("\n=== Running Header Analysis Complete ===")


if __name__ == "__main__":
    main()
