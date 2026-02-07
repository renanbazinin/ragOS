"""
Bulk-generate ~1000 AI exam questions using the RAG pipeline.

For every (topic × type × difficulty) combination, retrieves similar examples
from ChromaDB and asks Gemini to generate new questions.  Results are saved
as JSON files under aiGenerated/.

Usage:
    python generate_bulk.py              # Generate all ~1000 questions
    python generate_bulk.py --resume     # Skip already-generated files
    python generate_bulk.py --dry-run    # Print plan without calling Gemini
"""

import os
import sys
import json
import time
import traceback
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from query import search_questions, generate_question

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_db")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "aiGenerated")
COLLECTION_NAME = "os_exam_questions"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# How many questions to generate per combination (by category)
QUESTIONS_PER_FULL_TOPIC = 8      # Most important topics (13 topics × 9 combos = 117 × 8 = 936)
QUESTIONS_PER_MEDIUM_TOPIC = 6    # Important topics (10 topics × 6 combos = 60 × 6 = 360)
QUESTIONS_PER_LIGHT_TOPIC = 5     # Specialized topics (6 topics × 3 combos = 18 × 5 = 90)
QUESTIONS_PER_CROSS_TOPIC = 10    # Cross-topic combos (55 combos × 10 = 550)
# Total: 936 + 360 + 90 + 550 = 1,936 questions

# Delay between Gemini calls (seconds) to avoid rate-limiting
API_DELAY = 1.5

# ── Topics, types, difficulties ──────────────────────────────────────────────

TOPICS = [
    # Core process management
    "Processes",
    "Threads",
    "Context Switching",
    "System Calls",
    "Signals",
    # Scheduling
    "CPU Scheduling",
    "Scheduling",
    "Disk Scheduling",
    # Synchronization
    "Synchronization",
    "Mutexes",
    "Semaphores",
    "Condition Variables",
    "Atomic Operations",
    "Race Conditions",
    "Deadlocks",
    "Producer-Consumer",
    "Concurrency",
    # Memory
    "Memory Management",
    "Virtual Memory",
    "Paging",
    "Page Replacement",
    "TLB",
    "Copy-on-Write",
    # Storage & I/O
    "File Systems",
    "I/O",
    "RAID",
    # Other
    "IPC",
    "Networking",
    "Security",
]

TYPES = ["MultipleChoice", "Open", "CodeAnalysis"]

DIFFICULTIES = ["Easy", "Medium", "Hard"]

# ── Subject mapping (broad category over topic) ─────────────────────────────
# Every topic maps to one of 4 subjects
SUBJECTS = ["Virtualization", "Concurrency", "File Systems", "Disks"]

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

def get_subject(topic_hint: str) -> str:
    """Resolve a topic (or compound topic) to its subject."""
    # Direct match
    if topic_hint in TOPIC_TO_SUBJECT:
        return TOPIC_TO_SUBJECT[topic_hint]
    # Compound topic like "Processes and Threads" — use first part
    for t in TOPIC_TO_SUBJECT:
        if t in topic_hint:
            return TOPIC_TO_SUBJECT[t]
    return "Virtualization"  # fallback

# ── Which combos to generate ────────────────────────────────────────────────
# We weight the matrix so popular/important topics get more questions.

# Topics that get ALL 3 types × ALL 3 difficulties = 9 combos each
FULL_TOPICS = [
    "Processes", "Threads", "Synchronization", "Mutexes", "Semaphores",
    "Deadlocks", "Memory Management", "Virtual Memory", "Paging",
    "File Systems", "CPU Scheduling", "Concurrency", "Race Conditions",
]

# Topics that get 2 types × 3 difficulties = 6 combos each
MEDIUM_TOPICS = [
    "Context Switching", "System Calls", "Condition Variables",
    "Producer-Consumer", "Page Replacement", "TLB", "IPC",
    "Signals", "Copy-on-Write", "Scheduling",
]
MEDIUM_TYPES = ["MultipleChoice", "Open"]  # skip CodeAnalysis for these

# Topics that get 1 type × 3 difficulties = 3 combos each
LIGHT_TOPICS = [
    "Atomic Operations", "Disk Scheduling", "I/O", "RAID",
    "Networking", "Security",
]
LIGHT_TYPES = ["MultipleChoice"]

# ── Extra cross-topic combos for richer variety ──────────────────────────────
# These use compound topic hints so Gemini combines two areas

CROSS_TOPIC_COMBOS = [
    ("Synchronization and Deadlocks", "CodeAnalysis", "Hard"),
    ("Synchronization and Deadlocks", "Open", "Hard"),
    ("Paging and TLB", "MultipleChoice", "Medium"),
    ("Paging and TLB", "Open", "Hard"),
    ("Processes and Threads", "MultipleChoice", "Medium"),
    ("Processes and Threads", "Open", "Easy"),
    ("Processes and Threads", "CodeAnalysis", "Hard"),
    ("Semaphores and Producer-Consumer", "CodeAnalysis", "Medium"),
    ("Semaphores and Producer-Consumer", "CodeAnalysis", "Hard"),
    ("Semaphores and Producer-Consumer", "Open", "Medium"),
    ("Memory Management and Page Replacement", "MultipleChoice", "Medium"),
    ("Memory Management and Page Replacement", "Open", "Hard"),
    ("File Systems and I/O", "MultipleChoice", "Medium"),
    ("File Systems and I/O", "Open", "Hard"),
    ("Virtual Memory and Copy-on-Write", "Open", "Medium"),
    ("Virtual Memory and Copy-on-Write", "MultipleChoice", "Hard"),
    ("Race Conditions and Mutexes", "CodeAnalysis", "Medium"),
    ("Race Conditions and Mutexes", "CodeAnalysis", "Hard"),
    ("Concurrency and Condition Variables", "CodeAnalysis", "Medium"),
    ("Concurrency and Condition Variables", "Open", "Hard"),
    ("CPU Scheduling and Context Switching", "MultipleChoice", "Easy"),
    ("CPU Scheduling and Context Switching", "Open", "Medium"),
    ("Deadlocks and Synchronization", "MultipleChoice", "Medium"),
    ("Signals and System Calls", "MultipleChoice", "Medium"),
    ("Signals and System Calls", "Open", "Hard"),
    ("IPC and Processes", "Open", "Medium"),
    ("Threads and Synchronization", "CodeAnalysis", "Medium"),
    ("Threads and Synchronization", "CodeAnalysis", "Hard"),
    ("Scheduling and Deadlocks", "Open", "Hard"),
    ("RAID and File Systems", "MultipleChoice", "Medium"),
    # Extra combos to reach ~1000
    ("Processes and Memory Management", "MultipleChoice", "Easy"),
    ("Processes and Memory Management", "Open", "Medium"),
    ("Processes and Memory Management", "CodeAnalysis", "Hard"),
    ("Threads and Mutexes", "MultipleChoice", "Easy"),
    ("Threads and Mutexes", "CodeAnalysis", "Medium"),
    ("Threads and Mutexes", "Open", "Hard"),
    ("Semaphores and Deadlocks", "MultipleChoice", "Medium"),
    ("Semaphores and Deadlocks", "Open", "Hard"),
    ("Semaphores and Deadlocks", "CodeAnalysis", "Hard"),
    ("Virtual Memory and Paging", "MultipleChoice", "Easy"),
    ("Virtual Memory and Paging", "Open", "Medium"),
    ("Virtual Memory and Paging", "CodeAnalysis", "Hard"),
    ("File Systems and RAID", "MultipleChoice", "Easy"),
    ("File Systems and RAID", "Open", "Medium"),
    ("Scheduling and Processes", "MultipleChoice", "Easy"),
    ("Scheduling and Processes", "Open", "Medium"),
    ("Synchronization and Concurrency", "MultipleChoice", "Easy"),
    ("Synchronization and Concurrency", "CodeAnalysis", "Hard"),
    ("Memory Management and TLB", "MultipleChoice", "Medium"),
    ("Memory Management and TLB", "Open", "Hard"),
    ("Deadlocks and Mutexes", "CodeAnalysis", "Hard"),
    ("Deadlocks and Mutexes", "Open", "Medium"),
    ("IPC and Signals", "MultipleChoice", "Medium"),
    ("IPC and Signals", "Open", "Hard"),
    ("Context Switching and Threads", "MultipleChoice", "Easy"),
]


def build_plan() -> list[tuple[str, str, str]]:
    """Build the full list of (topic, type, difficulty) combos with optimized distribution."""
    plan = []

    # Full topics: 8 questions per combo
    for topic in FULL_TOPICS:
        for qtype in TYPES:
            for diff in DIFFICULTIES:
                for _ in range(QUESTIONS_PER_FULL_TOPIC):
                    plan.append((topic, qtype, diff))

    # Medium topics: 6 questions per combo
    for topic in MEDIUM_TOPICS:
        for qtype in MEDIUM_TYPES:
            for diff in DIFFICULTIES:
                for _ in range(QUESTIONS_PER_MEDIUM_TOPIC):
                    plan.append((topic, qtype, diff))

    # Light topics: 5 questions per combo
    for topic in LIGHT_TOPICS:
        for qtype in LIGHT_TYPES:
            for diff in DIFFICULTIES:
                for _ in range(QUESTIONS_PER_LIGHT_TOPIC):
                    plan.append((topic, qtype, diff))

    # Cross-topic combos: 10 questions each
    for combo in CROSS_TOPIC_COMBOS:
        for _ in range(QUESTIONS_PER_CROSS_TOPIC):
            plan.append(combo)

    return plan


def safe_filename(topic: str, qtype: str, diff: str, idx: int) -> str:
    """Create a filesystem-safe filename. idx is the global sequence number."""
    topic_slug = topic.replace(" ", "_").replace("/", "-")
    return f"{idx:04d}__{topic_slug}__{qtype}__{diff}.json"


def generate_and_save(
    collection,
    topic: str,
    qtype: str,
    difficulty: str,
    filepath: str,
) -> tuple[bool, dict]:
    """Generate one question and save it. Returns (success, usage_dict)."""
    # Retrieve similar examples
    examples = search_questions(
        collection,
        query_text=topic,
        n_results=3,
        question_type=qtype,
        difficulty=difficulty,
    )

    # If no exact match on type+difficulty, relax filters
    if len(examples) < 2:
        examples = search_questions(
            collection,
            query_text=topic,
            n_results=3,
            question_type=qtype,
        )
    if len(examples) < 2:
        examples = search_questions(
            collection,
            query_text=topic,
            n_results=3,
        )

    if not examples:
        print(f"    ⚠ No examples found for '{topic}' — skipping")
        return False, {}

    response = generate_question(
        example_questions=examples,
        topic_hint=topic,
        question_type=qtype,
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
    except:
        pass

    # Extract text
    raw = response.text if hasattr(response, 'text') else str(response)

    # Parse and validate
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            print(f"    ✗ Invalid JSON response — skipping")
            return False, usage

    # Wrap in our standard format
    subject = get_subject(topic)
    output = {
        "metadata": {
            "source": "ai_generated",
            "subject": subject,
            "topic_hint": topic,
            "requested_type": qtype,
            "requested_difficulty": difficulty,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "examples_used": len(examples),
            "token_usage": usage,
        },
        "question": parsed,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return True, usage


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    resume = "--resume" in sys.argv
    dry_run = "--dry-run" in sys.argv
    
    # Check for --limit flag
    limit = None
    for arg in sys.argv:
        if arg.startswith("--limit="):
            limit = int(arg.split("=")[1])

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    plan = build_plan()
    if limit:
        plan = plan[:limit]
    
    print(f"Plan: {len(plan)} questions to generate")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Resume mode: {resume}")
    if limit:
        print(f"Limit: {limit} questions")
    print()

    if dry_run:
        # Show distribution
        from collections import Counter
        type_counts = Counter(t for _, t, _ in plan)
        diff_counts = Counter(d for _, _, d in plan)
        topic_counts = Counter(t for t, _, _ in plan)
        print("By type:", dict(type_counts))
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
    print(f"Collection has {collection.count()} documents\n")

    success = 0
    skipped = 0
    failed = 0
    total_prompt_tokens = 0
    total_output_tokens = 0
    total_tokens = 0

    for i, (topic, qtype, diff) in enumerate(plan, 1):
        fname = safe_filename(topic, qtype, diff, i)
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
                pass  # re-generate bad files

        print(f"  [{i}/{len(plan)}] {topic} | {qtype} | {diff} …", end=" ", flush=True)

        try:
            ok, usage = generate_and_save(collection, topic, qtype, diff, fpath)
            if ok:
                success += 1
                # Track tokens
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

            # If rate-limited, wait longer
            if "429" in str(e) or "quota" in str(e).lower():
                wait = 30
                print(f"    Rate limited — waiting {wait}s …")
                time.sleep(wait)
                continue

        # Throttle API calls
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
        print(f"  Avg per question:     {total_tokens // success:,} tokens")
        print(f"\nCost Estimate (using Gemini pricing):")
        # Use generic pricing - will be more specific in output
        print(f"  Check the model used and apply appropriate pricing")
