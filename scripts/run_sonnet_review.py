#!/usr/bin/env python3
"""
run_sonnet_review.py — Orchestrate Sonnet corpus review for one or all letters.

For each letter: runs Sonnet review, applies quality-gated corrections,
runs the full pipeline, and reports results.

Usage:
    python run_sonnet_review.py A          # Single letter
    python run_sonnet_review.py A-Z        # All letters
    python run_sonnet_review.py D-M        # Range of letters
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def run_cmd(cmd, desc=""):
    """Run a command and return (success, output)."""
    if desc:
        print(f"\n>>> {desc}", flush=True)
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(REPO), encoding="utf-8",
        errors="replace"
    )
    if result.returncode != 0:
        print(f"  ERROR (exit {result.returncode}):", flush=True)
        print(result.stderr[:500] if result.stderr else result.stdout[:500], flush=True)
        return False, result.stdout + result.stderr
    return True, result.stdout


def process_letter(letter):
    """Run the full review pipeline for one letter."""
    print(f"\n{'='*60}", flush=True)
    print(f"  LETTER {letter}", flush=True)
    print(f"{'='*60}", flush=True)

    start = time.time()

    # Step 1: Sonnet review
    ok, out = run_cmd(
        [sys.executable, str(SCRIPTS / "sonnet_corpus_review.py"), letter],
        f"Sonnet review: letter {letter}"
    )
    if not ok:
        print(f"  FAILED: Sonnet review for {letter}", flush=True)
        return 0
    print(out.encode("ascii", errors="replace").decode("ascii"), flush=True)

    # Step 2: Apply corrections (quality gate)
    ok, out = run_cmd(
        [sys.executable, str(SCRIPTS / "apply_sonnet_corrections.py"), letter],
        f"Apply corrections: letter {letter}"
    )
    if not ok:
        print(f"  FAILED: Apply corrections for {letter}", flush=True)
        return 0
    print(out.encode("ascii", errors="replace").decode("ascii"), flush=True)

    elapsed = time.time() - start
    print(f"\n  Letter {letter} complete in {elapsed:.0f}s", flush=True)

    # Extract accepted count from output
    accepted = 0
    for line in out.split("\n"):
        if "Accepted OCR fixes:" in line:
            try:
                accepted += int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
        if "Accepted trims:" in line:
            try:
                accepted += int(line.split(":")[1].strip())
            except (ValueError, IndexError):
                pass
    return accepted


def run_pipeline():
    """Run the full rebuild pipeline."""
    steps = [
        ([sys.executable, str(SCRIPTS / "generate_live_corpus_v3.py")], "Generate live corpus"),
        ([sys.executable, str(SCRIPTS / "validate_rebuild.py")], "Validate"),
    ]
    for cmd, desc in steps:
        ok, out = run_cmd(cmd, desc)
        if not ok:
            return False
        # Print summary lines
        for line in out.split("\n"):
            if any(k in line for k in ["PASS", "FAIL", "WARNING", "Delta", "Live entries", "VALIDATION"]):
                print(f"  {line.strip()}", flush=True)

    # Copy candidate to live
    import shutil
    src = REPO / "rebuild" / "out" / "blacks_entries.live_candidate.json"
    dst = REPO / "blacks_entries.json"
    shutil.copy2(src, dst)
    print("  Copied candidate to blacks_entries.json", flush=True)

    # OCR cleanup
    ok, out = run_cmd(
        [sys.executable, str(SCRIPTS / "ocr_body_cleanup.py")],
        "Deterministic OCR cleanup"
    )
    if ok:
        for line in out.split("\n"):
            if "Fixed" in line:
                print(f"  {line.strip()}", flush=True)
                break

    # Split entries
    ok, out = run_cmd(
        [sys.executable, str(SCRIPTS / "split_entries.py")],
        "Split entries"
    )

    # Generate headwords
    with open(dst, encoding="utf-8") as f:
        entries = json.load(f)
    headwords = sorted(set(e["term"] for e in entries))
    with open(REPO / "assets" / "headwords.json", "w", encoding="utf-8") as f:
        json.dump(headwords, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  {len(headwords)} headwords written", flush=True)

    return True


def parse_range(arg):
    """Parse letter range like 'A', 'A-Z', 'D-M'."""
    arg = arg.upper()
    if len(arg) == 1 and arg.isalpha():
        return [arg]
    m = __import__("re").match(r'^([A-Z])-([A-Z])$', arg)
    if m:
        start, end = ord(m.group(1)), ord(m.group(2))
        return [chr(c) for c in range(start, end + 1)]
    return [arg]


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_sonnet_review.py <letter|range>")
        print("  Examples: A, A-Z, D-M")
        sys.exit(1)

    letters = parse_range(sys.argv[1])
    print(f"Processing letters: {', '.join(letters)}", flush=True)

    total_accepted = 0
    letter_results = {}

    for letter in letters:
        accepted = process_letter(letter)
        letter_results[letter] = accepted
        total_accepted += accepted

    if total_accepted > 0:
        print(f"\n{'='*60}", flush=True)
        print(f"  RUNNING PIPELINE ({total_accepted} corrections applied)", flush=True)
        print(f"{'='*60}", flush=True)
        ok = run_pipeline()
        if not ok:
            print("PIPELINE FAILED", flush=True)
            sys.exit(1)

    # Summary
    print(f"\n{'='*60}", flush=True)
    print(f"  SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    for letter, count in letter_results.items():
        print(f"  {letter}: {count} corrections", flush=True)
    print(f"  Total: {total_accepted} corrections", flush=True)


if __name__ == "__main__":
    main()
