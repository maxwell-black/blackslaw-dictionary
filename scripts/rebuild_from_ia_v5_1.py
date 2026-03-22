#!/usr/bin/env python3
"""
rebuild_from_ia_v5.py — Black's Law Dictionary corpus rebuild from IA DjVu XML.

v5.1: v5 + three fixes:
  1. Fuzzy same-term merge: OCR variants like BAOK/BACK (edit dist 1, not in
     oracle) merge into current entry instead of being treated as body text
  2. Aggressive orphan cleanup: standalone 1-4 digit lines and 1-4 char all-caps
     lines stripped unconditionally from bodies
  3. Fallback bodies (unmatched entries) also get orphan cleanup applied

Base: v4 column separation + v5.4 segmentation (classify_segment, short-head
guards, prefix extensions, punctuation-anchored mid-line splits).
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "rebuild" / "raw"
OUT_DIR = ROOT / "rebuild" / "out"
REPORT_DIR = ROOT / "rebuild" / "reports"

SENSE_MARKERS = {
    "v.",
    "n.",
    "adj.",
    "adv.",
    "vb.",
    "prep.",
    "part.",
    "pl.",
    "pp.",
}

TRANSLATION_TABLE = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2014": "\u2014",
        "\u2013": "-",
        "\ufb01": "fi",
        "\ufb02": "fl",
        "\xa0": " ",
    }
)

EMBEDDED_HEADWORD_RE = re.compile(r"(?m)^(?!\u2014)([A-Z][A-Z0-9 '&().,-]{4,})\.(?:\s|$)")
PAGE_NUMBER_RE = re.compile(r"(?m)^\d{1,4}$")
SHORT_HEADER_RE = re.compile(r"(?m)^[A-Z]{1,4}$")

# Mid-line boundary: sentence-ending punct + whitespace + uppercase start
_MIDLINE_BOUNDARY_RE = re.compile(r'([.!?;:]["\')\]]*)(\s+)(?=[A-Z])')
_ROMAN_RE = re.compile(r"^[IVXLCDM]+$")

# Orphan numerics: standalone 1-4 digit numbers on their own line in body text
_ORPHAN_NUMERIC_RE = re.compile(r"(?m)^\d{1,4}$")
# Page header cluster: number + short caps header on adjacent lines
_PAGE_HEADER_CLUSTER_RE = re.compile(r"\n\s*\d{1,4}\s*\n\s*[A-Z][A-Z .'\-]{1,40}\s*\n")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class LineRec:
    text: str
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass
class PageRec:
    leaf: int
    printed_page: str | None
    page_type: str | None
    width: int
    height: int
    lines: list[str]


@dataclass
class SourceCandidate:
    source_index: int
    source_headword: str
    norm_headword: str
    body: str
    source_pages: list[str]
    leaves: list[int]


@dataclass
class RebuiltEntry:
    term: str
    body: str
    source_headword: str | None
    source_pages: list[str]
    match_score: float
    confidence: float
    flags: list[str]
    suggested_term: str | None


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def tag_name(elem: ET.Element) -> str:
    return elem.tag.rsplit("}", 1)[-1].upper()


def normalize_chars(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(TRANSLATION_TABLE)
    text = text.replace("\ufeff", "")
    return text


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_line_text(text: str) -> str:
    text = normalize_chars(text)
    text = re.sub(r"\s+([,.;:?!\)])", r"\1", text)
    text = re.sub(r"([\(\[])\s+", r"\1", text)
    text = re.sub(r"^\u2014\s+", "\u2014", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_term(text: str) -> str:
    text = normalize_chars(text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper()
    text = text.replace("\u2014", "-")
    text = re.sub(r"\s+", " ", text)
    text = text.strip().rstrip(".,;:")
    return text


def leading_letter(term: str) -> str:
    for ch in normalize_term(term):
        if "A" <= ch <= "Z":
            return ch
    return "#"


def oracle_exact_match(headword: str, oracle_norms: set[str]) -> bool:
    norm = normalize_term(headword)
    return norm in oracle_norms


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


def similarity_score(current_term: str, source_term: str) -> float:
    a = normalize_term(current_term)
    b = normalize_term(source_term)
    if not a or not b:
        return -4.0
    if a == b:
        return 5.0
    if a.replace(".", "") == b.replace(".", ""):
        return 4.5
    ratio = SequenceMatcher(None, a, b).ratio()
    edit = levenshtein(a, b)
    if a[0] == b[0] and max(len(a), len(b)) <= 3 and edit <= 1:
        return 3.0
    if a[0] == b[0] and edit == 1 and ratio >= 0.80:
        return 3.8
    if a[0] == b[0] and ratio >= 0.94:
        return 4.0
    if a[0] == b[0] and ratio >= 0.88:
        return 3.0
    if a[0] == b[0] and ratio >= 0.80:
        return 1.5
    return -4.0


def confidence_from_score(score: float) -> float:
    if score >= 5.0:
        return 0.99
    if score >= 4.0:
        return 0.95
    if score >= 3.0:
        return 0.90
    if score >= 1.5:
        return 0.82
    if score > 0.0:
        return 0.70
    return 0.0


def union_boxes(boxes: Iterable[tuple[int, int, int, int]]) -> tuple[int, int, int, int]:
    box_list = list(boxes)
    if not box_list:
        return (0, 0, 0, 0)
    return (
        min(b[0] for b in box_list),
        min(b[1] for b in box_list),
        max(b[2] for b in box_list),
        max(b[3] for b in box_list),
    )


# ---------------------------------------------------------------------------
# Page parsing — scandata
# ---------------------------------------------------------------------------

def parse_scandata(path: Path) -> dict[int, dict[str, str | None]]:
    if not path.exists():
        return {}
    tree = ET.parse(path)
    root = tree.getroot()
    meta: dict[int, dict[str, str | None]] = {}
    for page in root.findall(".//page"):
        leaf_raw = page.attrib.get("leafNum") or page.attrib.get("leafnum")
        if leaf_raw is None:
            continue
        try:
            leaf = int(leaf_raw)
        except ValueError:
            continue
        meta[leaf] = {
            "printed_page": normalize_space(page.findtext("pageNumber") or "") or None,
            "page_type": normalize_space(page.findtext("pageType") or "") or None,
        }
    return meta


# ---------------------------------------------------------------------------
# Page cleaning — column separation (from v4)
# ---------------------------------------------------------------------------

def looks_like_page_furniture(text: str, region: str) -> bool:
    t = normalize_space(text)
    if not t:
        return True
    if re.fullmatch(r"\d{1,4}", t):
        return True
    if re.fullmatch(r"[ivxlcdmIVXLCDM]{1,10}", t):
        return True
    if region == "header":
        if re.fullmatch(r"[A-Z]{1,4}", t):
            return True
        if re.fullmatch(r"[A-Z][A-Z' .\-]{1,40}", t) and len(t.split()) <= 3:
            return True
    return False


def should_join_hyphen(prev_line: str, next_line: str) -> bool:
    return bool(
        prev_line
        and next_line
        and prev_line.endswith("-")
        and re.search(r"[A-Za-z]{2,}-$", prev_line)
        and next_line[0].islower()
    )


def _process_column_lines(
    recs: list[LineRec],
    page_height: int,
) -> list[str]:
    if not recs:
        return []

    line_heights = [max(1, r.y1 - r.y0) for r in recs]
    median_height = statistics.median(line_heights) if line_heights else 12

    gaps: list[float] = []
    for prev, curr in zip(recs, recs[1:]):
        gap = curr.y0 - prev.y1
        if gap >= 0:
            gaps.append(gap)
    median_gap = statistics.median(gaps) if gaps else 0
    para_threshold = max(median_gap * 1.8, median_height * 0.8, 10)

    out: list[str] = []
    prev_rec: LineRec | None = None
    for rec in recs:
        text = rec.text.strip()
        if not text:
            continue
        if prev_rec is not None:
            gap = rec.y0 - prev_rec.y1
            if gap > para_threshold and out and out[-1] != "":
                out.append("")
            if out and out[-1] != "" and should_join_hyphen(out[-1], text):
                out[-1] = out[-1][:-1] + text.lstrip()
            else:
                out.append(text)
        else:
            out.append(text)
        prev_rec = rec

    return out


def clean_page(
    raw_lines: list[LineRec],
    width: int,
    height: int,
    leaf: int,
    page_meta: dict[str, str | None],
) -> PageRec:
    if not raw_lines:
        return PageRec(leaf, page_meta.get("printed_page"), page_meta.get("page_type"), width, height, [])

    # Normalize y-coordinates (DjVu sometimes has y0 > y1)
    for rec in raw_lines:
        if rec.y0 > rec.y1:
            rec.y0, rec.y1 = rec.y1, rec.y0

    raw_lines = sorted(raw_lines, key=lambda rec: (rec.y0, rec.x0))

    # Strip page furniture
    kept: list[LineRec] = []
    for rec in raw_lines:
        mid_y = (rec.y0 + rec.y1) / 2
        if mid_y <= height * 0.09 and looks_like_page_furniture(rec.text, "header"):
            continue
        if mid_y >= height * 0.94 and looks_like_page_furniture(rec.text, "footer"):
            continue
        kept.append(rec)

    # Column separation
    x_mid = width / 2.0
    left_col = [r for r in kept if (r.x0 + r.x1) / 2.0 < x_mid]
    right_col = [r for r in kept if (r.x0 + r.x1) / 2.0 >= x_mid]

    left_col.sort(key=lambda r: (r.y0, r.x0))
    right_col.sort(key=lambda r: (r.y0, r.x0))

    left_lines = _process_column_lines(left_col, height)
    right_lines = _process_column_lines(right_col, height)

    out_lines: list[str] = list(left_lines)
    if out_lines and right_lines:
        if out_lines[-1] != "":
            out_lines.append("")
    out_lines.extend(right_lines)

    while out_lines and out_lines[0] == "":
        out_lines.pop(0)
    while out_lines and out_lines[-1] == "":
        out_lines.pop()

    return PageRec(leaf, page_meta.get("printed_page"), page_meta.get("page_type"), width, height, out_lines)


# ---------------------------------------------------------------------------
# DjVu XML parsing
# ---------------------------------------------------------------------------

def parse_djvu_xml(xml_path: Path, scan_meta: dict[int, dict[str, str | None]]) -> list[PageRec]:
    pages: list[PageRec] = []
    page_index = 0
    context = ET.iterparse(xml_path, events=("end",))
    for _event, elem in context:
        if tag_name(elem) != "OBJECT":
            continue
        width = int(elem.attrib.get("width", "0") or 0)
        height = int(elem.attrib.get("height", "0") or 0)
        raw_lines: list[LineRec] = []
        for line_elem in elem.iter():
            if tag_name(line_elem) != "LINE":
                continue
            words: list[str] = []
            boxes: list[tuple[int, int, int, int]] = []
            for word_elem in line_elem:
                if tag_name(word_elem) != "WORD":
                    continue
                token = normalize_line_text(word_elem.text or "")
                if not token:
                    continue
                coords = word_elem.attrib.get("coords")
                if coords and re.fullmatch(r"\d+,\d+,\d+,\d+", coords):
                    boxes.append(tuple(int(part) for part in coords.split(",")))
                words.append(token)
            if words:
                x0, y0, x1, y1 = union_boxes(boxes)
                raw_lines.append(LineRec(normalize_line_text(" ".join(words)), x0, y0, x1, y1))
        page_meta = scan_meta.get(page_index, {})
        page = clean_page(raw_lines, width, height, page_index, page_meta)
        pages.append(page)
        page_index += 1
        elem.clear()
    return pages


# ---------------------------------------------------------------------------
# Headword extraction
# ---------------------------------------------------------------------------

def is_caps_token(token: str) -> bool:
    core = token.strip('"\'\u201c\u201d\u2018\u2019[]()')
    if not core:
        return False
    if re.fullmatch(r"(?:[A-Z]\.)+", core):
        return True
    stem = core.rstrip(".,;:")
    return bool(stem) and bool(re.fullmatch(r"[A-Z0-9&'\-]+", stem))


def clean_headword(raw: str) -> str:
    raw = normalize_space(raw)
    raw = raw.rstrip(".,;:")
    return raw


def extract_headword(line: str) -> str | None:
    s = line.strip()
    if not s:
        return None
    if s[0] in {"\u2014", "-", "'", '"'}:
        return None
    if s[0].islower():
        return None

    tokens = s.split()
    if not tokens:
        return None

    captured: list[str] = []
    saw_terminal = False
    expect_sense = False

    for i, token in enumerate(tokens):
        lower = token.lower()
        if expect_sense and lower in SENSE_MARKERS:
            return clean_headword(" ".join(captured))
        if not is_caps_token(token):
            break
        captured.append(token)
        if token.endswith(","):
            expect_sense = True
            continue
        if token.endswith(".") or token.endswith(":") or token.endswith(";"):
            saw_terminal = True
            if i + 1 < len(tokens) and tokens[i + 1].lower() in SENSE_MARKERS:
                return clean_headword(" ".join(captured))
            return clean_headword(" ".join(captured))
        expect_sense = False

    if captured and saw_terminal:
        return clean_headword(" ".join(captured))
    return None


# ---------------------------------------------------------------------------
# Body finalization
# ---------------------------------------------------------------------------

def strip_first_headword(headword: str, body: str) -> str:
    escaped = re.escape(headword)
    flex = escaped.replace(r"\ ", r"\s+")
    pattern = re.compile(rf"^\s*{flex}\s*([.,;:]\s*)?", re.IGNORECASE)
    return pattern.sub("", body, count=1).lstrip()


def rewrite_same_headword_sense_paragraphs(headword: str, body: str) -> str:
    escaped = re.escape(headword).replace(r"\ ", r"\s+")
    sense = r"((?:v|n|adj|adv|vb|prep|part|pl|pp)\.)"
    pattern = re.compile(rf"(?m)^\s*{escaped}\s*,\s*{sense}\s*", re.IGNORECASE)
    return pattern.sub(r"\1 ", body)


def finalize_body(headword: str, body_lines: list[str]) -> str:
    lines = list(body_lines)
    while lines and lines[0] == "":
        lines.pop(0)
    while lines and lines[-1] == "":
        lines.pop()
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = strip_first_headword(headword, text)
    text = rewrite_same_headword_sense_paragraphs(headword, text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_orphan_numerics(body: str) -> str:
    """Strip standalone 1-4 digit page numbers, short all-caps running headers,
    and page-header clusters that leaked through furniture stripping."""
    # First strip clustered headers: number + short caps header on adjacent lines
    body = _PAGE_HEADER_CLUSTER_RE.sub("\n", body)
    # Then strip orphan numerics and short caps that sit on their own line
    lines = body.split("\n")
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Skip standalone page numbers (1-4 digits alone on a line)
        if stripped and re.fullmatch(r"\d{1,4}", stripped):
            continue
        # Skip short all-caps running headers (1-4 chars alone on a line)
        if stripped and re.fullmatch(r"[A-Z]{1,4}", stripped):
            continue
        cleaned.append(line)
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


# ---------------------------------------------------------------------------
# v5: short-head guards (from 5.4)
# ---------------------------------------------------------------------------

def _is_suspicious_short_head(headword: str) -> bool:
    """
    Heads like A / BE / IV are real terms, but they also occur constantly in
    citations and abbreviations. We allow them only when the following context
    looks like a definition, not a citation.
    """
    norm = normalize_term(headword)
    compact = norm.replace(" ", "")
    if not compact:
        return True
    if len(compact) <= 2:
        return True
    if compact.isdigit():
        return True
    if _ROMAN_RE.fullmatch(compact):
        return True
    return False


def _definition_tail(segment: str, headword: str) -> str:
    """
    Return the text immediately after the extracted headword, with the
    entry-opening punctuation / sense marker stripped off.
    """
    if segment.startswith(headword):
        tail = segment[len(headword):].lstrip()
    else:
        tail = segment

    if tail.startswith(","):
        tail = tail[1:].lstrip()
        # Strip one or two abbreviated sense markers, e.g. "v." / "adv."
        m = re.match(r"(?:[A-Za-z]+\.\s*){1,2}", tail)
        if m:
            tail = tail[m.end():]
    elif tail[:1] in ".:;":
        tail = tail[1:].lstrip()

    return tail


def _short_head_context_ok(segment: str, headword: str) -> bool:
    """
    Heuristic guard for short / roman-numeral heads. Accept only when the text
    after the head looks definition-like rather than citation-like.
    """
    tail = _definition_tail(segment, headword)
    if not tail:
        return False

    ch = tail[0]
    # Digits, lowercase starts, quotes, and various citation openers are suspect
    if ch.isdigit() or ch.islower() or ch in "\"'([{/&\u00a7":
        return False

    # Single-letter or abbreviated citation continuations:
    # "Y. Supp. 432", "c. 3", "Mass. 43", "Hill (N. Y.)", etc.
    if re.match(r"^[A-Z]\.\s", tail):
        return False
    if re.match(r"^[A-Z]{2,5}\.\s*\d", tail):
        return False
    if re.match(r"^[A-Z][a-z]{0,7}\.\s*(?:\d|\()", tail):
        return False

    return True


def _is_same_term_fuzzy(head_norm: str, current_norm: str, oracle_norms: set[str]) -> bool:
    """
    Fuzzy same-term check for OCR variants like BAOK/BACK.
    Returns True if:
      - exact match, OR
      - edit distance <= 1, same first char, same length +/- 1,
        AND head_norm is NOT a real oracle entry (so it's an OCR error,
        not a legitimate different term like BAIL vs BAIT)
    """
    if head_norm == current_norm:
        return True
    if not head_norm or not current_norm:
        return False
    if head_norm[0] != current_norm[0]:
        return False
    if abs(len(head_norm) - len(current_norm)) > 1:
        return False
    if head_norm in oracle_norms:
        # It's a real entry in the oracle — don't merge, treat as separate
        return False
    if levenshtein(head_norm, current_norm) <= 1:
        return True
    return False


# ---------------------------------------------------------------------------
# v5: mid-line splitting (from 5.4)
# ---------------------------------------------------------------------------

def find_midline_splits(line: str, oracle_norms: set[str]) -> list[str]:
    """
    Split a physical OCR line into logical chunks at punctuation-anchored
    mid-line entry boundaries.

    A split is accepted only if the suffix begins with a headword recognized by
    extract_headword() and that headword is an exact oracle match. That keeps
    CONTRACT / EASEMENT-style mid-line starts while blocking most noise.
    """
    if not line:
        return []

    parts: list[str] = []
    start = 0
    pos = 0

    while True:
        m = _MIDLINE_BOUNDARY_RE.search(line, pos)
        if not m:
            tail = line[start:].strip()
            if tail:
                parts.append(tail)
            break

        split_at = m.end(2)
        suffix = line[split_at:].lstrip()
        head = extract_headword(suffix)

        ok = False
        if head is not None and oracle_exact_match(head, oracle_norms):
            if not _is_suspicious_short_head(head) or _short_head_context_ok(suffix, head):
                ok = True

        if ok:
            prefix = line[start:m.start(2)].rstrip()
            if prefix:
                parts.append(prefix)
            start = split_at
            pos = split_at
        else:
            pos = m.end()

    return parts


# ---------------------------------------------------------------------------
# v5: build_source_candidates (from 5.4, integrated with v4 page/column logic)
# ---------------------------------------------------------------------------

def _trim_body_lines(body_lines: list[str]) -> list[str]:
    out = body_lines[:]
    while out and out[0] == "":
        out.pop(0)
    while out and out[-1] == "":
        out.pop()
    return out


def build_source_candidates(
    pages: list[PageRec],
    oracle_norms: set[str],
) -> list[SourceCandidate]:
    candidates: list[SourceCandidate] = []

    current_headword: str | None = None
    current_norm: str | None = None
    current_body_lines: list[str] = []
    current_pages: list[str] = []
    current_leaves: list[int] = []

    def attach_page(page: PageRec) -> None:
        printed = page.printed_page.strip() if page.printed_page else None
        if printed and (not current_pages or current_pages[-1] != printed):
            current_pages.append(printed)
        if not current_leaves or current_leaves[-1] != page.leaf:
            current_leaves.append(page.leaf)

    def append_body(text: str, page: PageRec) -> None:
        if current_headword is None:
            return

        if text == "":
            if not current_body_lines or current_body_lines[-1] != "":
                current_body_lines.append("")
            return

        current_body_lines.append(text)
        attach_page(page)

    def flush_current() -> None:
        nonlocal current_headword, current_norm, current_body_lines, current_pages, current_leaves

        if current_headword is None:
            current_norm = None
            current_body_lines = []
            current_pages = []
            current_leaves = []
            return

        body_lines = _trim_body_lines(current_body_lines)
        body = finalize_body(current_headword, body_lines)
        body = clean_orphan_numerics(body)

        candidates.append(
            SourceCandidate(
                source_index=len(candidates),
                source_headword=current_headword,
                norm_headword=current_norm or normalize_term(current_headword),
                body=body,
                source_pages=current_pages[:],
                leaves=current_leaves[:],
            )
        )

        current_headword = None
        current_norm = None
        current_body_lines = []
        current_pages = []
        current_leaves = []

    def start_entry(headword: str, segment: str, page: PageRec) -> None:
        nonlocal current_headword, current_norm, current_body_lines, current_pages, current_leaves
        current_headword = headword
        current_norm = normalize_term(headword)
        current_body_lines = [segment]
        current_pages = []
        current_leaves = []
        attach_page(page)

    def classify_segment(segment: str, prev_blank: bool) -> tuple[str, str | None]:
        """
        Returns:
            ("start", headword)  -> flush current and start a new entry
            ("merge", headword)  -> same-term sense line; append to current entry
            ("body", headword|None) -> ordinary body text
        """
        headword = extract_headword(segment)
        if headword is None:
            return ("body", None)

        head_norm = normalize_term(headword)
        if not head_norm:
            return ("body", headword)

        # Same-term sense continuation (e.g. BACK, adv. while building BACK)
        # Also catches OCR variants like BAOK for BACK (edit dist 1, not in oracle)
        if current_norm and _is_same_term_fuzzy(head_norm, current_norm, oracle_norms):
            return ("merge", headword)

        head_is_oracle = oracle_exact_match(headword, oracle_norms)

        # Guard short / roman-numeral / citation-prone heads everywhere
        if _is_suspicious_short_head(headword) and not _short_head_context_ok(segment, headword):
            return ("body", headword)

        # Primary cue: a real blank line before the line
        if prev_blank:
            # Keep non-oracle prefix extensions inside the parent entry,
            # e.g. BADGE OF FRAUD under BADGE, unless the full phrase is in the oracle
            if (
                current_norm
                and not head_is_oracle
                and head_norm != current_norm
                and head_norm.startswith(current_norm + " ")
            ):
                return ("body", headword)
            return ("start", headword)

        # Secondary cue: no blank, so require exact oracle confirmation
        if head_is_oracle:
            return ("start", headword)

        return ("body", headword)

    prev_blank = True

    for page in pages:
        # Do not force a page break to behave like an entry break when an entry
        # is already open; let the actual blank-line signal drive that
        if current_headword is None:
            prev_blank = True

        for raw_line in page.lines:
            if raw_line == "":
                append_body("", page)
                prev_blank = True
                continue

            segments = find_midline_splits(raw_line, oracle_norms)
            if not segments:
                prev_blank = False
                continue

            first_segment = True
            for segment in segments:
                if not segment:
                    continue

                mode, headword = classify_segment(
                    segment,
                    prev_blank if first_segment else False,
                )

                if mode == "start":
                    flush_current()
                    start_entry(headword, segment, page)  # type: ignore[arg-type]
                elif mode == "merge":
                    append_body(segment, page)
                else:
                    append_body(segment, page)

                first_segment = False

            prev_blank = False

    flush_current()
    return candidates


# ---------------------------------------------------------------------------
# Alignment (identical to v4)
# ---------------------------------------------------------------------------

def align_letter(
    current_indices: list[int],
    current_terms: list[str],
    source_indices: list[int],
    source_terms: list[str],
) -> dict[int, tuple[int, float]]:
    n = len(current_terms)
    m = len(source_terms)
    if n == 0:
        return {}

    score = [[0.0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        score[i][0] = score[i - 1][0] - 2.0
        back[i][0] = "U"
    for j in range(1, m + 1):
        score[0][j] = score[0][j - 1] - 0.8
        back[0][j] = "L"

    for i in range(1, n + 1):
        curr_term = current_terms[i - 1]
        for j in range(1, m + 1):
            src_term = source_terms[j - 1]
            diag = score[i - 1][j - 1] + similarity_score(curr_term, src_term)
            up = score[i - 1][j] - 2.0
            left = score[i][j - 1] - 0.8
            best = max(diag, up, left)
            score[i][j] = best
            if best == diag:
                back[i][j] = "D"
            elif best == up:
                back[i][j] = "U"
            else:
                back[i][j] = "L"

    mapping: dict[int, tuple[int, float]] = {}
    i, j = n, m
    while i > 0 or j > 0:
        move = back[i][j]
        if move == "D":
            curr_idx = current_indices[i - 1]
            src_idx = source_indices[j - 1]
            match_score = similarity_score(current_terms[i - 1], source_terms[j - 1])
            if match_score > 0:
                mapping[curr_idx] = (src_idx, match_score)
            i -= 1
            j -= 1
        elif move == "U":
            i -= 1
        else:
            j -= 1
    return mapping


def align_all(current_entries: list[dict], source_candidates: list[SourceCandidate]) -> dict[int, tuple[int, float]]:
    current_by_letter: dict[str, list[int]] = defaultdict(list)
    source_by_letter: dict[str, list[int]] = defaultdict(list)

    for idx, entry in enumerate(current_entries):
        current_by_letter[leading_letter(entry["term"])].append(idx)
    for idx, candidate in enumerate(source_candidates):
        source_by_letter[leading_letter(candidate.source_headword)].append(idx)

    mapping: dict[int, tuple[int, float]] = {}
    for letter in sorted(current_by_letter):
        curr_indices = current_by_letter[letter]
        src_indices = source_by_letter.get(letter, [])
        curr_terms = [current_entries[i]["term"] for i in curr_indices]
        src_terms = [source_candidates[i].source_headword for i in src_indices]
        mapping.update(align_letter(curr_indices, curr_terms, src_indices, src_terms))
    return mapping


# ---------------------------------------------------------------------------
# Rebuilt entries, flags, reports
# ---------------------------------------------------------------------------

def build_flags(term: str, source_headword: str | None, body: str, match_score: float) -> list[str]:
    flags: list[str] = []
    if not body.strip():
        flags.append("empty_body")
    if PAGE_NUMBER_RE.search(body):
        flags.append("page_number_artifact")
    if SHORT_HEADER_RE.search(body):
        flags.append("short_header_artifact")
    if source_headword is None:
        flags.append("missing_source_candidate")
    elif normalize_term(term) != normalize_term(source_headword):
        flags.append("headword_mismatch")
    if EMBEDDED_HEADWORD_RE.search(body):
        flags.append("embedded_caps_subentry")
    if len(body.strip()) < 40:
        flags.append("short_body")
    if match_score <= 0:
        flags.append("low_match_score")
    return sorted(set(flags))


def build_rebuilt_entries(
    current_entries: list[dict],
    source_candidates: list[SourceCandidate],
    mapping: dict[int, tuple[int, float]],
) -> list[RebuiltEntry]:
    rebuilt: list[RebuiltEntry] = []
    for idx, entry in enumerate(current_entries):
        if idx in mapping:
            source_idx, match_score = mapping[idx]
            candidate = source_candidates[source_idx]
            body = candidate.body
            source_headword = candidate.source_headword
            source_pages = candidate.source_pages
            suggested_term = source_headword if normalize_term(entry["term"]) != normalize_term(source_headword) else None
            confidence = confidence_from_score(match_score)
        else:
            match_score = 0.0
            body = clean_orphan_numerics(entry.get("body", ""))
            source_headword = None
            source_pages = []
            suggested_term = None
            confidence = 0.0
        flags = build_flags(entry["term"], source_headword, body, match_score)
        rebuilt.append(
            RebuiltEntry(
                term=entry["term"],
                body=body,
                source_headword=source_headword,
                source_pages=source_pages,
                match_score=match_score,
                confidence=confidence,
                flags=flags,
                suggested_term=suggested_term,
            )
        )
    return rebuilt


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_reports(current_entries: list[dict], source_candidates: list[SourceCandidate], rebuilt: list[RebuiltEntry]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    alignment_csv = REPORT_DIR / "alignment.csv"
    with alignment_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "index",
            "current_term",
            "source_headword",
            "suggested_term",
            "match_score",
            "confidence",
            "source_pages",
            "flags",
        ])
        for idx, row in enumerate(rebuilt):
            writer.writerow([
                idx,
                row.term,
                row.source_headword or "",
                row.suggested_term or "",
                f"{row.match_score:.2f}",
                f"{row.confidence:.2f}",
                ", ".join(row.source_pages),
                ", ".join(row.flags),
            ])

    low_confidence = [
        {
            "index": idx,
            "term": row.term,
            "source_headword": row.source_headword,
            "suggested_term": row.suggested_term,
            "match_score": row.match_score,
            "confidence": row.confidence,
            "source_pages": row.source_pages,
            "flags": row.flags,
            "current_body": current_entries[idx].get("body", ""),
            "rebuilt_body": row.body,
        }
        for idx, row in enumerate(rebuilt)
        if row.confidence < 0.90 or row.flags
    ]
    write_json(REPORT_DIR / "low_confidence_review.json", low_confidence)

    term_fix_candidates = [
        {
            "index": idx,
            "current_term": row.term,
            "source_headword": row.source_headword,
            "match_score": row.match_score,
            "confidence": row.confidence,
            "source_pages": row.source_pages,
        }
        for idx, row in enumerate(rebuilt)
        if row.suggested_term and row.confidence >= 0.90
    ]
    write_json(REPORT_DIR / "term_fix_candidates.json", term_fix_candidates)

    stats = {
        "total_current_entries": len(current_entries),
        "total_source_candidates": len(source_candidates),
        "exact_or_normalized_matches": sum(1 for row in rebuilt if row.match_score >= 4.5),
        "high_confidence_fuzzy_matches": sum(1 for row in rebuilt if 3.0 <= row.match_score < 4.5),
        "low_confidence_matches": sum(1 for row in rebuilt if 0 < row.match_score < 3.0),
        "missing_source_candidates": sum(1 for row in rebuilt if row.source_headword is None),
        "entries_with_flags": sum(1 for row in rebuilt if row.flags),
    }
    write_json(REPORT_DIR / "stats.json", stats)


def maybe_apply_safe_term_fixes(rebuilt: list[RebuiltEntry]) -> list[dict]:
    live_rows: list[dict] = []
    for row in rebuilt:
        term = row.term
        if row.suggested_term and row.confidence >= 0.95 and "headword_mismatch" in row.flags:
            term = row.suggested_term
        live_rows.append(
            {
                "term": term,
                "body": row.body,
                "source_headword": row.source_headword,
                "source_pages": row.source_pages,
                "confidence": row.confidence,
                "flags": row.flags,
            }
        )
    return live_rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="v5.1: Rebuild blackslaw bodies with fuzzy merge + aggressive cleanup.")
    parser.add_argument("--entries", default="blacks_entries.json", help="Current JSON corpus")
    parser.add_argument("--raw-dir", default=str(RAW_DIR), help="Directory containing djvu.xml and scandata.xml")
    parser.add_argument("--apply-safe-term-fixes", action="store_true", help="Apply only very-high-confidence term fixes to the live output")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Load current entries
    with Path(args.entries).open("r", encoding="utf-8") as fh:
        current_entries: list[dict] = json.load(fh)

    # Build oracle set from current entry terms (min length 2 to skip single chars)
    oracle_norms: set[str] = set()
    for entry in current_entries:
        norm = normalize_term(entry["term"])
        if len(norm) >= 2:
            oracle_norms.add(norm)
    print(f"Loading entries: {len(current_entries)}")
    print(f"Oracle: {len(oracle_norms)} normalized terms")

    # Parse pages
    scan_meta = parse_scandata(raw_dir / "scandata.xml")
    print("Parsing DjVu XML...")
    pages = parse_djvu_xml(raw_dir / "djvu.xml", scan_meta)
    print(f"Pages parsed: {len(pages)}")

    # Segment source candidates
    print("Segmenting entries...")
    source_candidates = build_source_candidates(pages, oracle_norms)
    print(f"Source candidates: {len(source_candidates)}")

    # Check for duplicates
    from collections import Counter
    norm_counts = Counter(c.norm_headword for c in source_candidates)
    dupes = {k: v for k, v in norm_counts.items() if v > 1}
    top_dupes = sorted(dupes.items(), key=lambda x: -x[1])[:10]
    print(f"Duplicate norms: {len(dupes)}")
    for term, count in top_dupes:
        print(f"  {term}: {count}")

    # Align
    print("Aligning...")
    mapping = align_all(current_entries, source_candidates)

    # Build rebuilt entries
    rebuilt = build_rebuilt_entries(current_entries, source_candidates, mapping)

    # Write outputs
    write_jsonl(OUT_DIR / "source_pages.jsonl", (asdict(page) for page in pages))
    write_jsonl(OUT_DIR / "source_candidates.jsonl", (asdict(candidate) for candidate in source_candidates))
    write_json(OUT_DIR / "blacks_entries.rebuilt.json", [asdict(row) for row in rebuilt])

    live_rows = maybe_apply_safe_term_fixes(rebuilt) if args.apply_safe_term_fixes else [
        {
            "term": row.term,
            "body": row.body,
            "source_headword": row.source_headword,
            "source_pages": row.source_pages,
            "confidence": row.confidence,
            "flags": row.flags,
        }
        for row in rebuilt
    ]
    write_json(OUT_DIR / "blacks_entries.live_candidate.json", live_rows)

    write_reports(current_entries, source_candidates, rebuilt)

    # Summary
    exact = sum(1 for row in rebuilt if row.match_score >= 4.5)
    fuzzy = sum(1 for row in rebuilt if 3.0 <= row.match_score < 4.5)
    low = sum(1 for row in rebuilt if 0 < row.match_score < 3.0)
    missing = sum(1 for row in rebuilt if row.source_headword is None)

    print(f"\n--- v5 Summary ---")
    print(f"Current entries:     {len(current_entries)}")
    print(f"Source candidates:   {len(source_candidates)}")
    print(f"Exact matches:       {exact}")
    print(f"Fuzzy matches:       {fuzzy}")
    print(f"Low-conf matches:    {low}")
    print(f"Missing source:      {missing}")
    print(f"Output:              {OUT_DIR / 'blacks_entries.rebuilt.json'}")
    print(f"Live candidate:      {OUT_DIR / 'blacks_entries.live_candidate.json'}")
    print(f"Reports:             {REPORT_DIR}")

    # Key entry spot checks
    print(f"\n--- Key entries ---")
    by_src = {c.norm_headword: c for c in source_candidates}
    for term in ["BACK", "BADGE", "BAGGAGE", "CONTRACT", "EASEMENT", "HABEAS CORPUS", "MORTGAGE", "NEGLIGENCE"]:
        norm = normalize_term(term)
        if norm in by_src:
            c = by_src[norm]
            has_adv = "adv." in c.body.lower() if term == "BACK" else None
            has_bof = "BADGE OF FRAUD" in c.body if term == "BADGE" else None
            extras = ""
            if has_adv is not None:
                extras += f"  adv={'Yes' if has_adv else 'No'}"
            if has_bof is not None:
                extras += f"  bof={'Yes' if has_bof else 'No'}"
            print(f"  {term:25s} body={len(c.body):>5d}{extras}")
        else:
            print(f"  {term:25s} NOT FOUND")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
