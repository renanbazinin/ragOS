"""
Bulk-generate theory-based multiple-choice questions from lecture summaries.

For every (subject × topic × difficulty) combination, retrieves relevant
lecture chunks from ChromaDB and asks Gemini to create MC questions grounded
in the actual lecture material.  Results are saved as JSON under aiTheory/.

Usage:
    python generate_theory.py              # Generate all questions
    python generate_theory.py --resume     # Skip already-generated files
    python generate_theory.py --dry-run    # Print plan without calling Gemini
    python generate_theory.py --limit=10   # Generate only first 10
"""

import os
import sys
import json
import time
import re
import random
import traceback
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from query_summary import search_summary, generate_mc_question

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_summary")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "aiTheory")
COLLECTION_NAME = "os_summary_chunks"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

API_DELAY = 1.5  # seconds between Gemini calls

# ── Topic matrix per subject ────────────────────────────────────────────────
# Each subject has topics, and for every (topic × difficulty) we generate
# a configurable number of questions.

SUBJECT_TOPICS: dict[str, list[str]] = {
    "Virtualization": [
        "Processes",
        "Process Lifecycle",
        "Context Switching",
        "System Calls",
        "Signals",
        "CPU Scheduling",
        "Scheduling Algorithms",
        "Memory Management",
        "Fragmentation",
        "Virtual Memory",
        "Paging",
        "Page Tables",
        "Multi-level Page Tables",
        "TLB",
        "Copy-on-Write",
        "Address Space",
    ],
    "Concurrency": [
        "Threads",
        "Multi-core Processors",
        "Locks",
        "Mutexes",
        "Synchronization",
        "Spinlocks",
        "Ticket Locks",
        "TAS and TTAS",
        "Cache Coherence",
        "Atomic Operations",
        "Condition Variables",
        "Producer-Consumer",
        "Semaphores",
        "Deadlocks",
        "Race Conditions",
        "Starvation",
    ],
    "File Systems": [
        "File System Structure",
        "Inodes",
        "Data Blocks and Bitmaps",
        "Superblock",
        "Directory Structure",
        "Crash Consistency",
        "Journaling",
        "Log-structured File System",
        "Inode Map",
    ],
    "Disks": [
        "I/O Devices",
        "Device Model",
        "Hard Disk Performance",
        "Sequential vs Random Access",
        "Disk Scheduling",
        "RAID",
        "RAID-0 Striping",
        "RAID-1 Mirroring",
    ],
}

DIFFICULTIES = ["Easy", "Medium", "Hard"]

# How many questions per (topic × difficulty) combo
QUESTIONS_PER_COMBO: dict[str, int] = {
    "Virtualization": 3,   # 16 topics × 3 diffs × 3 = 144
    "Concurrency":    3,   # 16 topics × 3 diffs × 3 = 144
    "File Systems":   4,   # 9 topics  × 3 diffs × 4 = 108
    "Disks":          4,   # 8 topics  × 3 diffs × 4 = 96
}
# Total: ~492 theory MC questions

# ── Cross-topic combos for richer variety ────────────────────────────────────

CROSS_TOPICS: list[tuple[str, str, str]] = [
    # (query_hint, subject, difficulty)
    ("Processes and Scheduling", "Virtualization", "Medium"),
    ("Processes and Scheduling", "Virtualization", "Hard"),
    ("Paging and TLB", "Virtualization", "Medium"),
    ("Paging and TLB", "Virtualization", "Hard"),
    ("Virtual Memory and Page Tables", "Virtualization", "Medium"),
    ("Memory Management and Paging", "Virtualization", "Hard"),
    ("Context Switching and Processes", "Virtualization", "Easy"),
    ("Signals and System Calls", "Virtualization", "Medium"),
    ("Threads and Locks", "Concurrency", "Medium"),
    ("Threads and Locks", "Concurrency", "Hard"),
    ("Deadlocks and Synchronization", "Concurrency", "Hard"),
    ("Semaphores and Producer-Consumer", "Concurrency", "Medium"),
    ("Semaphores and Producer-Consumer", "Concurrency", "Hard"),
    ("Race Conditions and Mutexes", "Concurrency", "Medium"),
    ("Condition Variables and Locks", "Concurrency", "Hard"),
    ("Spinlocks and Cache Coherence", "Concurrency", "Hard"),
    ("Atomic Operations and Synchronization", "Concurrency", "Medium"),
    ("Starvation and Deadlocks", "Concurrency", "Hard"),
    ("Inodes and Data Blocks", "File Systems", "Medium"),
    ("Crash Consistency and Journaling", "File Systems", "Hard"),
    ("Log-structured FS and Inode Map", "File Systems", "Hard"),
    ("File System Structure and Directories", "File Systems", "Easy"),
    ("RAID and Disk Performance", "Disks", "Medium"),
    ("RAID and Disk Performance", "Disks", "Hard"),
    ("I/O Devices and Device Model", "Disks", "Easy"),
    ("Sequential vs Random and Disk Scheduling", "Disks", "Medium"),
]

CROSS_TOPIC_QUESTIONS = 3  # questions per cross-topic combo


# ── Plan builder ─────────────────────────────────────────────────────────────


def build_plan() -> list[tuple[str, str, str]]:
    """Build full list of (topic_hint, subject, difficulty) combos."""
    plan = []

    # Regular per-topic combos
    for subject, topics in SUBJECT_TOPICS.items():
        qpc = QUESTIONS_PER_COMBO[subject]
        for topic in topics:
            for diff in DIFFICULTIES:
                for _ in range(qpc):
                    plan.append((topic, subject, diff))

    # Cross-topic combos
    for combo in CROSS_TOPICS:
        for _ in range(CROSS_TOPIC_QUESTIONS):
            plan.append(combo)

    return plan


def safe_filename(topic: str, subject: str, diff: str, idx: int) -> str:
    """Create a filesystem-safe filename."""
    topic_slug = topic.replace(" ", "_").replace("/", "-")
    subject_slug = subject.replace(" ", "_")
    return f"{idx:04d}__{subject_slug}__{topic_slug}__MC__{diff}.json"


# ── Answer shuffling ─────────────────────────────────────────────────────────

HEBREW_LETTERS = ['א', 'ב', 'ג', 'ד', 'ה', 'ו']


def shuffle_options(parsed: dict) -> dict:
    """Shuffle MC options and update correct_option to match the new order."""
    content = parsed.get("content", {})
    solution = parsed.get("solution", {})
    options = content.get("options")
    correct = solution.get("correct_option", "") if solution else ""

    if not options or len(options) < 2 or not correct:
        return parsed

    # Find which option index is correct by matching the Hebrew letter prefix
    correct_letter = correct.strip().rstrip('.')
    correct_idx = None
    for i, opt in enumerate(options):
        opt_letter = opt.strip().split('.')[0].strip()
        if opt_letter == correct_letter:
            correct_idx = i
            break

    if correct_idx is None:
        # Fallback: try matching by position (א=0, ב=1, ג=2, ד=3)
        if correct_letter in HEBREW_LETTERS:
            correct_idx = HEBREW_LETTERS.index(correct_letter)
        if correct_idx is None or correct_idx >= len(options):
            return parsed

    # Strip existing letter prefixes, keep just the text
    stripped = []
    for opt in options:
        text = opt.strip()
        # Remove patterns like "א. ", "א) ", "1. ", etc.
        for prefix_pattern in [r'^[א-ו]\.\s*', r'^[א-ו]\)\s*', r'^[א-ו]\s+']:
            new_text = re.sub(prefix_pattern, '', text)
            if new_text != text:
                text = new_text
                break
        stripped.append(text)

    # Create indexed pairs and shuffle
    indexed = list(enumerate(stripped))
    random.shuffle(indexed)

    # Re-label with Hebrew letters and find new correct position
    new_options = []
    new_correct_letter = correct_letter
    for new_idx, (orig_idx, text) in enumerate(indexed):
        letter = HEBREW_LETTERS[new_idx]
        new_options.append(f"{letter}. {text}")
        if orig_idx == correct_idx:
            new_correct_letter = letter

    parsed["content"]["options"] = new_options
    parsed["solution"]["correct_option"] = new_correct_letter
    return parsed


# ── Generate & Save ─────────────────────────────────────────────────────────


def generate_and_save(
    collection,
    topic: str,
    subject: str,
    difficulty: str,
    filepath: str,
) -> tuple[bool, dict]:
    """Generate one MC question from summary context and save. Returns (success, usage)."""

    # Retrieve relevant lecture chunks
    chunks = search_summary(
        collection,
        query_text=topic,
        n_results=5,
        subject=subject,
    )

    # Fallback: relax subject filter if too few results
    if len(chunks) < 2:
        chunks = search_summary(
            collection,
            query_text=topic,
            n_results=5,
        )

    if not chunks:
        print(f"    ⚠ No context found for '{topic}' ({subject}) — skipping")
        return False, {}

    response = generate_mc_question(
        context_chunks=chunks,
        topic_hint=topic,
        subject=subject,
        difficulty=difficulty,
    )

    # Extract usage metadata
    usage = {}
    try:
        if hasattr(response, 'usage_metadata'):
            usage = {
                'prompt_tokens': response.usage_metadata.prompt_token_count,
                'output_tokens': response.usage_metadata.candidates_token_count,
                'total_tokens': response.usage_metadata.total_token_count,
            }
    except Exception:
        pass

    # Extract text
    raw = response.text if hasattr(response, 'text') else str(response)

    # Parse JSON
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError:
                print(f"    ✗ Invalid JSON response — skipping")
                return False, usage
        else:
            print(f"    ✗ Invalid JSON response — skipping")
            return False, usage

    # Shuffle answer options so correct answer isn't always first
    parsed = shuffle_options(parsed)

    # Wrap in standard format
    output = {
        "metadata": {
            "source": "ai_generated_from_summary",
            "subject": subject,
            "topic_hint": topic,
            "requested_type": "MultipleChoice",
            "requested_difficulty": difficulty,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "context_chunks_used": len(chunks),
            "context_lectures": list(set(c["lecture_number"] for c in chunks)),
            "token_usage": usage,
        },
        "question": parsed,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return True, usage


# ── Reshuffle existing files ─────────────────────────────────────────────────

def reshuffle_existing_files():
    """Reshuffle answer options in all existing aiTheory JSON files."""
    import glob
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json")))
    if not files:
        print("No files found in aiTheory/")
        return

    print(f"Reshuffling answers in {len(files)} files...")
    shuffled_count = 0
    for fpath in files:
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            q = data.get("question", {})
            if q.get("content", {}).get("options") and q.get("solution", {}).get("correct_option"):
                data["question"] = shuffle_options(q)
                with open(fpath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                shuffled_count += 1
        except (json.JSONDecodeError, IOError) as e:
            print(f"  SKIP {os.path.basename(fpath)}: {e}")

    print(f"Done. Reshuffled {shuffled_count}/{len(files)} files.")


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Handle --shuffle mode: reshuffle existing files and exit
    if "--shuffle" in sys.argv:
        reshuffle_existing_files()
        sys.exit(0)

    resume = "--resume" in sys.argv
    dry_run = "--dry-run" in sys.argv

    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    plan = build_plan()
    if limit:
        plan = plan[:limit]

    print(f"═══════════════════════════════════════════════════")
    print(f"  Theory MC Question Generator (from summaryBOOK)")
    print(f"═══════════════════════════════════════════════════")
    print(f"  Plan: {len(plan)} questions to generate")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"  Resume mode: {resume}")
    if limit:
        print(f"  Limit: {limit} questions")
    print()

    if dry_run:
        from collections import Counter
        subj_counts = Counter(s for _, s, _ in plan)
        diff_counts = Counter(d for _, _, d in plan)
        topic_counts = Counter(t for t, _, _ in plan)

        print("By subject:", dict(subj_counts))
        print("By difficulty:", dict(diff_counts))
        print("\nBy topic:")
        for t, c in sorted(topic_counts.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")
        print(f"\nTotal: {len(plan)}")
        sys.exit(0)

    # Initialize ChromaDB
    print("Loading embedding model …")
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL, device="cpu"
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(
        name=COLLECTION_NAME, embedding_function=embed_fn
    )
    print(f"Collection has {collection.count()} chunks\n")

    success = 0
    skipped = 0
    failed = 0
    total_prompt_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    for i, (topic, subject, diff) in enumerate(plan, 1):
        fname = safe_filename(topic, subject, diff, i)
        fpath = os.path.join(OUTPUT_DIR, fname)

        # Resume: skip if file exists and is valid
        if resume and os.path.isfile(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    json.load(f)
                skipped += 1
                print(f"  [{i}/{len(plan)}] SKIP (exists): {fname}")
                continue
            except (json.JSONDecodeError, IOError):
                pass

        print(f"  [{i}/{len(plan)}] [{subject}] {topic} | MC | {diff} …", end=" ", flush=True)

        try:
            ok, usage = generate_and_save(collection, topic, subject, diff, fpath)
            if ok:
                success += 1
                if usage:
                    total_prompt_tokens += usage.get('prompt_tokens', 0)
                    total_output_tokens += usage.get('output_tokens', 0)
                    total_tokens += usage.get('total_tokens', 0)
                    print(f"✓ (tokens: {usage.get('total_tokens', 0)})")
                else:
                    print("✓")
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {e}")
            traceback.print_exc()

            if "429" in str(e) or "quota" in str(e).lower():
                wait = 30
                print(f"    Rate limited — waiting {wait}s …")
                time.sleep(wait)
                continue

        time.sleep(API_DELAY)

        # Progress summary every 50 questions
        if i % 50 == 0:
            print(f"\n  ── Progress: {success} ok / {failed} failed / {skipped} skipped / {len(plan)} total ──\n")

    print(f"\n{'='*50}")
    print(f"Done!")
    print(f"  Generated: {success}")
    print(f"  Skipped:   {skipped}")
    print(f"  Failed:    {failed}")
    print(f"  Total:     {success + skipped + failed}/{len(plan)}")
    print(f"  Output:    {OUTPUT_DIR}")
    print(f"\n{'='*50}")
    print(f"Token Usage Summary:")
    print(f"  Total Prompt Tokens:  {total_prompt_tokens:,}")
    print(f"  Total Output Tokens:  {total_output_tokens:,}")
    print(f"  Total Tokens:         {total_tokens:,}")
    if success > 0:
        print(f"  Avg per question:     {total_tokens // max(success, 1):,} tokens")
