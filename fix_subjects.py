"""
Fix AI-generated question files that are missing the "subject" field.

Scans aiGenerated/ for files up to index 0460, and for any missing
the "subject" metadata field, asks Gemini 2.5 Flash to classify the
topic into one of: Virtualization, Concurrency, File Systems, Disks.

Usage:
    python fix_subjects.py              # Fix all missing
    python fix_subjects.py --dry-run    # Show what would be fixed without calling Gemini
"""

import os
import sys
import json
import time
import glob
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash"
AI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aiGenerated")
MAX_INDEX = 460
API_DELAY = 0.5  # seconds between calls

SUBJECTS = ["Virtualization", "Concurrency", "File Systems", "Disks"]

PROMPT_TEMPLATE = """You are classifying Operating Systems exam topics into exactly one of these 4 subjects:
1. Virtualization — Processes, Threads, CPU Scheduling, Memory Management, Virtual Memory, Paging, TLB, Page Replacement, Context Switching, System Calls, Signals, IPC, Copy-on-Write
2. Concurrency — Synchronization, Mutexes, Semaphores, Condition Variables, Deadlocks, Race Conditions, Atomic Operations, Producer-Consumer, Concurrency
3. File Systems — File Systems, Networking, Security
4. Disks — Disk Scheduling, I/O, RAID

The topic(s) for this question: {topics}

Reply with ONLY one of these exact words: Virtualization, Concurrency, File Systems, Disks"""


def classify_topic(topics: list[str] | str) -> str:
    """Ask Gemini to classify topics into a subject."""
    if isinstance(topics, list):
        topic_str = ", ".join(topics)
    else:
        topic_str = str(topics)

    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(MODEL)
    response = model.generate_content(PROMPT_TEMPLATE.format(topics=topic_str))
    answer = response.text.strip()

    # Validate response is one of the 4 subjects
    for s in SUBJECTS:
        if s.lower() in answer.lower():
            return s

    print(f"    ⚠ Unexpected response: '{answer}' — defaulting to Virtualization")
    return "Virtualization"


def main():
    dry_run = "--dry-run" in sys.argv

    if not API_KEY and not dry_run:
        print("ERROR: GEMINI_API_KEY not set in .env")
        sys.exit(1)

    files = sorted(glob.glob(os.path.join(AI_DIR, "*.json")))
    missing = []

    for filepath in files:
        fname = os.path.basename(filepath)
        # Extract index from filename like "0123__Topic__Type__Diff.json"
        try:
            idx = int(fname.split("__")[0])
        except (ValueError, IndexError):
            continue

        if idx > MAX_INDEX:
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        meta = data.get("metadata", {})
        if "subject" not in meta:
            # Get topic from metadata or question
            topic_hint = meta.get("topic_hint", "")
            question = data.get("question", {})
            if isinstance(question, dict):
                topics = question.get("topic", [topic_hint])
            elif isinstance(question, list) and question:
                topics = question[0].get("topic", [topic_hint])
            else:
                topics = [topic_hint]

            missing.append((filepath, fname, idx, topics))

    print(f"Found {len(missing)} files missing 'subject' (out of files up to index {MAX_INDEX})")

    if not missing:
        print("Nothing to fix!")
        return

    if dry_run:
        for _, fname, idx, topics in missing:
            print(f"  [{idx:04d}] {fname} — topics: {topics}")
        print(f"\nRun without --dry-run to fix these {len(missing)} files.")
        return

    fixed = 0
    errors = 0

    for filepath, fname, idx, topics in missing:
        print(f"  [{idx:04d}] {fname} — topics: {topics}")
        try:
            subject = classify_topic(topics)
            print(f"         → {subject}")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["metadata"]["subject"] = subject

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            fixed += 1
            time.sleep(API_DELAY)

        except Exception as e:
            print(f"         ✗ Error: {e}")
            errors += 1

    print(f"\nDone: {fixed} fixed, {errors} errors")


if __name__ == "__main__":
    main()
