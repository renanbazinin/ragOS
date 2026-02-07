"""
Fix AI-generated question files that are missing the "subject" field.

Uses the local TOPIC_TO_SUBJECT mapping (no API calls needed).
Scans aiGenerated/ for ALL files missing "subject" and classifies them
into one of: Virtualization, Concurrency, File Systems, Disks.

Usage:
    python fix_subjects.py              # Fix all missing
    python fix_subjects.py --dry-run    # Show what would be fixed
"""

import os
import sys
import json
import glob

AI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aiGenerated")

TOPIC_TO_SUBJECT: dict[str, str] = {
    # Virtualization
    "Processes": "Virtualization",
    "Threads": "Virtualization",
    "Context Switching": "Virtualization",
    "System Calls": "Virtualization",
    "Signals": "Virtualization",
    "CPU Scheduling": "Virtualization",
    "Scheduling": "Virtualization",
    "Memory Management": "Virtualization",
    "Virtual Memory": "Virtualization",
    "Paging": "Virtualization",
    "Page Replacement": "Virtualization",
    "TLB": "Virtualization",
    "Copy-on-Write": "Virtualization",
    "IPC": "Virtualization",
    # Concurrency
    "Synchronization": "Concurrency",
    "Mutexes": "Concurrency",
    "Semaphores": "Concurrency",
    "Condition Variables": "Concurrency",
    "Atomic Operations": "Concurrency",
    "Race Conditions": "Concurrency",
    "Deadlocks": "Concurrency",
    "Producer-Consumer": "Concurrency",
    "Concurrency": "Concurrency",
    # File Systems
    "File Systems": "File Systems",
    "Networking": "File Systems",
    "Security": "File Systems",
    # Disks
    "Disk Scheduling": "Disks",
    "I/O": "Disks",
    "RAID": "Disks",
}


def get_subject(topic_hint: str, topics: list[str] | None = None) -> str:
    """Resolve a topic (or list of topics) to its subject using local mapping."""
    # Try topic_hint directly
    if topic_hint in TOPIC_TO_SUBJECT:
        return TOPIC_TO_SUBJECT[topic_hint]
    # Compound topic like "Memory_Management" → "Memory Management"
    normalized = topic_hint.replace("_", " ")
    if normalized in TOPIC_TO_SUBJECT:
        return TOPIC_TO_SUBJECT[normalized]
    # Try substring match on topic_hint
    for t in TOPIC_TO_SUBJECT:
        if t.lower() in topic_hint.lower():
            return TOPIC_TO_SUBJECT[t]
    # Try topics list
    if topics:
        for topic in topics:
            if topic in TOPIC_TO_SUBJECT:
                return TOPIC_TO_SUBJECT[topic]
            for t in TOPIC_TO_SUBJECT:
                if t.lower() in topic.lower():
                    return TOPIC_TO_SUBJECT[t]
    return "Virtualization"  # fallback


def main():
    dry_run = "--dry-run" in sys.argv

    files = sorted(glob.glob(os.path.join(AI_DIR, "*.json")))
    missing = []

    for filepath in files:
        fname = os.path.basename(filepath)
        # Extract index and topic from filename like "0123__Topic__Type__Diff.json"
        parts = fname.split("__")
        try:
            idx = int(parts[0])
        except (ValueError, IndexError):
            continue

        topic_hint = parts[1].replace("_", " ") if len(parts) > 1 else ""

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue

        meta = data.get("metadata", {})
        if "subject" not in meta:
            # Get topic list from question data
            question = data.get("question", {})
            if isinstance(question, dict):
                topics = question.get("topic", [topic_hint])
            elif isinstance(question, list) and question:
                topics = question[0].get("topic", [topic_hint])
            else:
                topics = [topic_hint]

            missing.append((filepath, fname, idx, topic_hint, topics))

    print(f"Found {len(missing)} files missing 'subject'")

    if not missing:
        print("Nothing to fix!")
        return

    if dry_run:
        for _, fname, idx, topic_hint, topics in missing:
            subject = get_subject(topic_hint, topics if isinstance(topics, list) else [topics])
            print(f"  [{idx:04d}] {fname} → {subject}")
        print(f"\nRun without --dry-run to fix these {len(missing)} files.")
        return

    fixed = 0
    errors = 0

    for filepath, fname, idx, topic_hint, topics in missing:
        try:
            subject = get_subject(topic_hint, topics if isinstance(topics, list) else [topics])
            print(f"  [{idx:04d}] {fname} → {subject}")

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            data["metadata"]["subject"] = subject

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            fixed += 1

        except Exception as e:
            print(f"  [{idx:04d}] ✗ Error: {e}")
            errors += 1

    print(f"\nDone: {fixed} fixed, {errors} errors")


if __name__ == "__main__":
    main()
