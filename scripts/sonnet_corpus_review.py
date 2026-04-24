#!/usr/bin/env python3
"""
sonnet_corpus_review.py — Use Claude Sonnet to review dictionary entries for a given letter.

Sends batches of entries to Sonnet for review, collecting corrections for:
- TRIM_BODY: embedded entries merged into parent bodies
- FIX_OCR: OCR scanning errors in body text
- FIX_HEADWORD: damaged entry terms
- FLAG: issues needing manual review

Requires: ANTHROPIC_API_KEY environment variable (or key file)
Usage: python sonnet_corpus_review.py <letter>
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

REPO = Path(__file__).resolve().parent.parent
MODEL = "claude-sonnet-4-6"
BATCH_SIZE = 50
MAX_WORKERS = 4

SYSTEM_PROMPT = """You are reviewing entries from Black's Law Dictionary (2nd Edition, 1910) for data quality issues.

For each entry that needs correction, output a JSON correction object. Return a JSON array of ALL corrections found across all entries (empty array [] if none needed).

Correction types:

1. TRIM_BODY: The body contains another dictionary entry merged in (look for ALL-CAPS headwords followed by definitions appearing mid-body after paragraph breaks).
   Format: {"type": "trim", "term": "<parent entry>", "trim_at": "<first 30 chars of embedded entry>", "reason": "<why>"}

2. FIX_OCR: The body has OCR scanning errors — garbled characters, wrong letters, broken words.
   Format: {"type": "ocr_fix", "term": "<entry>", "old": "<exact damaged text>", "new": "<corrected text>", "reason": "<why>"}
   Common OCR errors: tbe->the, aud->and, wbich->which, bave->have, witb->with, 8->S in abbreviations (U. 8. -> U. S.), broken hyphens, accented characters where plain belong, garbled punctuation.

3. FIX_HEADWORD: The entry term itself is damaged or misspelled.
   Format: {"type": "headword", "term": "<current damaged term>", "correct": "<fixed term>", "reason": "<why>"}

4. FLAG: Something looks wrong but you're unsure.
   Format: {"type": "flag", "term": "<entry>", "issue": "<description>"}

CRITICAL — DO NOT flag or "fix" any of these (they are CORRECT for 1910):
- Latin legal terms (habeas corpus, certiorari, mandamus, res judicata, etc.)
- Law French (cestui que trust, chose in action, feme covert, etc.)
- Archaic English spellings: connexion, shew/shewn, colour/honour/favour, judgement, gaol, waggon, despatch, enrol/enrolment, wilful, plead/pleaded, amongst, whilst, towards
- British spellings and 1910-era usage
- Old citation formats and abbreviations
- "q. v." cross-references

Return ONLY a valid JSON array. No markdown formatting, no code fences, no commentary."""


def setup_api_key():
    """Ensure API key is available."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        # Check for .env in repo root
        env_file = REPO / ".env"
        if env_file.exists():
            text = env_file.read_text().strip()
            # Support both KEY="VALUE" and KEY=VALUE formats, allowing for spaces
            m = re.search(r'\s*=\s*(?:"([^"]+)"|([^ \n]+))', text)
            if m:
                api_key = m.group(1) or m.group(2)
                os.environ["ANTHROPIC_API_KEY"] = api_key
    return api_key


def format_batch(entries):
    """Format a batch of entries for the prompt."""
    parts = []
    for e in entries:
        body = e.get("body", "") or ""
        # Truncate very long bodies to avoid token limits
        if len(body) > 2000:
            body = body[:2000] + "... [truncated]"
        parts.append(f"TERM: {e['term']}\nBODY: {body}")
    return "\n\n---\n\n".join(parts)


def review_batch(client, batch, batch_num):
    """Send a batch to Sonnet and parse corrections."""
    text = format_batch(batch)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        response_text = resp.content[0].text.strip()

        # Parse JSON — strip markdown code fences if present
        cleaned = re.sub(r'```(?:json)?\s*', '', response_text).strip()
        cleaned = re.sub(r'```\s*$', '', cleaned).strip()

        # Try direct parse first, then fallback to regex extraction
        for attempt_text in [cleaned, response_text]:
            try:
                corrections = json.loads(attempt_text)
                if isinstance(corrections, list):
                    return batch_num, corrections, None
            except json.JSONDecodeError:
                pass

        # Last resort: find JSON array in response
        m = re.search(r'\[.*\]', response_text, re.DOTALL)
        if m:
            try:
                corrections = json.loads(m.group())
                if isinstance(corrections, list):
                    return batch_num, corrections, None
            except json.JSONDecodeError:
                pass
        return batch_num, [], f"JSON parse error: {response_text[:200]}"

    except Exception as e:
        return batch_num, [], str(e)


def main():
    if len(sys.argv) < 2:
        print("Usage: python sonnet_corpus_review.py <letter>")
        sys.exit(1)

    letter = sys.argv[1].upper()
    entries_file = REPO / "data" / f"entries_{letter.lower()}.json"

    if not entries_file.exists():
        print(f"ERROR: {entries_file} not found")
        sys.exit(1)

    api_key = setup_api_key()
    if not api_key:
        print("ERROR: No ANTHROPIC_API_KEY found")
        sys.exit(1)

    import anthropic
    client = anthropic.Anthropic()

    print(f"Loading entries for letter {letter}...", flush=True)
    with open(entries_file, encoding="utf-8") as f:
        entries = json.load(f)
    print(f"  {len(entries)} entries", flush=True)

    # Create batches
    batches = []
    for i in range(0, len(entries), BATCH_SIZE):
        batches.append(entries[i:i + BATCH_SIZE])
    print(f"  {len(batches)} batches of ~{BATCH_SIZE}", flush=True)

    # Process batches with thread pool
    all_corrections = []
    errors = []
    start = time.time()

    print(f"\nProcessing with {MAX_WORKERS} workers...", flush=True)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for i, batch in enumerate(batches):
            future = executor.submit(review_batch, client, batch, i)
            futures[future] = i

        done = 0
        for future in as_completed(futures):
            done += 1
            batch_num, corrections, error = future.result()
            if error:
                errors.append({"batch": batch_num, "error": error})
                print(f"  Batch {batch_num}: ERROR - {error[:100]}", flush=True)
            else:
                all_corrections.extend(corrections)

            if done % 5 == 0 or done == len(batches):
                elapsed = time.time() - start
                print(f"  ...{done}/{len(batches)} batches, {len(all_corrections)} corrections ({elapsed:.0f}s)", flush=True)

    elapsed = time.time() - start
    print(f"\n=== Letter {letter} Results ({elapsed:.0f}s) ===", flush=True)
    print(f"  Entries reviewed: {len(entries)}", flush=True)
    print(f"  Total corrections: {len(all_corrections)}", flush=True)
    print(f"  Errors: {len(errors)}", flush=True)

    # Count by type
    by_type = {}
    for c in all_corrections:
        t = c.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    for t, count in sorted(by_type.items()):
        print(f"    {t}: {count}", flush=True)

    # Save results
    output_file = REPO / "rebuild" / "reports" / f"sonnet_review_{letter.lower()}.json"
    result = {
        "letter": letter,
        "entries_reviewed": len(entries),
        "corrections": all_corrections,
        "errors": errors,
        "by_type": by_type,
        "elapsed_seconds": round(elapsed, 1),
    }
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  Saved: {output_file}", flush=True)


if __name__ == "__main__":
    main()
