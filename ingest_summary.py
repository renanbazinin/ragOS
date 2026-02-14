"""
Ingest summaryBOOK lecture notes into a dedicated ChromaDB collection.

Reads .txt files from summaryBOOK/, splits them into overlapping chunks,
tags each chunk with its subject category (Virtualization / Concurrency /
File Systems / Disks) and lecture number, then stores embeddings in ChromaDB.

Usage:
    python ingest_summary.py                # Ingest all lecture notes
    python ingest_summary.py --reset        # Delete collection & re-ingest
"""

import os
import sys
import re
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SUMMARY_DIR = os.path.join(PROJECT_DIR, "summaryBOOK")
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_summary")
COLLECTION_NAME = "os_summary_chunks"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # Hebrew + English

# Chunk settings
CHUNK_SIZE = 800       # characters per chunk (approx)
CHUNK_OVERLAP = 200    # overlap between consecutive chunks

# ── Lecture → Subject mapping ────────────────────────────────────────────────

LECTURE_SUBJECT: dict[int, str] = {
    # Virtualization (lectures 2–9)
    2: "Virtualization",
    3: "Virtualization",
    4: "Virtualization",
    5: "Virtualization",
    6: "Virtualization",
    7: "Virtualization",
    8: "Virtualization",
    9: "Virtualization",
    # Concurrency (lectures 10–16)
    10: "Concurrency",
    11: "Concurrency",
    12: "Concurrency",
    13: "Concurrency",
    14: "Concurrency",
    15: "Concurrency",
    16: "Concurrency",
    # Disks (lectures 17–19)
    17: "Disks",
    18: "Disks",
    19: "Disks",
    # File Systems (lectures 20–22)
    20: "File Systems",
    21: "File Systems",
    22: "File Systems",
}

LECTURE_TOPIC: dict[int, list[str]] = {
    2:  ["Processes", "OS History"],
    3:  ["CPU Scheduling", "Scheduling Algorithms"],
    4:  ["System Calls", "POSIX API", "Process Trees"],
    5:  ["Signals", "Zombie Processes", "Process Lifecycle"],
    6:  ["Memory Management", "Free Lists", "Fragmentation"],
    7:  ["Paging", "Page Tables", "MMU", "Virtual Memory"],
    8:  ["Multi-level Page Tables", "Paging"],
    9:  ["Review", "Processes", "Scheduling", "Paging"],
    10: ["Threads", "Concurrency", "Multi-core"],
    11: ["Locks", "Synchronization", "Threads"],
    12: ["Locks", "Spinning", "Ticket Locks"],
    13: ["TAS", "TTAS", "Cache Coherence", "Atomic Operations"],
    14: ["Condition Variables", "Producer-Consumer", "Semaphores"],
    15: ["Deadlocks", "Lock Ordering"],
    16: ["Review", "Concurrency", "Deadlocks", "Starvation"],
    17: ["I/O Devices", "Device Model", "Persistence"],
    18: ["Hard Disk", "Disk Performance", "Sequential vs Random"],
    19: ["RAID", "Striping", "Mirroring"],
    20: ["File Systems", "Inodes", "Data Blocks", "Bitmaps"],
    21: ["Crash Consistency", "Journaling", "File Systems"],
    22: ["Log-structured FS", "Inode Map", "File Systems"],
}


# ── Chunking ─────────────────────────────────────────────────────────────────


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    # Split by paragraphs first
    paragraphs = re.split(r"\n{2,}", text)
    
    chunks = []
    current = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        if len(current) + len(para) + 1 <= chunk_size:
            current = current + "\n\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            # If a single paragraph is longer than chunk_size, split it
            if len(para) > chunk_size:
                words = para.split()
                current = ""
                for w in words:
                    if len(current) + len(w) + 1 <= chunk_size:
                        current = current + " " + w if current else w
                    else:
                        chunks.append(current)
                        # Keep overlap from end of previous chunk
                        overlap_words = current.split()[-overlap // 6:] if current else []
                        current = " ".join(overlap_words) + " " + w if overlap_words else w
            else:
                # Start new chunk with overlap from previous
                if chunks:
                    prev = chunks[-1]
                    overlap_text = prev[-overlap:] if len(prev) > overlap else prev
                    # Find a clean word boundary
                    space_idx = overlap_text.find(" ")
                    if space_idx > 0:
                        overlap_text = overlap_text[space_idx + 1:]
                    current = overlap_text + "\n\n" + para
                else:
                    current = para
    
    if current.strip():
        chunks.append(current)
    
    return chunks


def extract_lecture_number(filename: str) -> int:
    """Extract lecture number from filename like '2.txt' -> 2."""
    stem = filename.replace(".txt", "")
    try:
        return int(stem)
    except ValueError:
        return 0


# ── Ingestion ────────────────────────────────────────────────────────────────


def ingest_lecture(collection, filepath: str) -> int:
    """Ingest a single lecture file. Returns chunk count."""
    filename = os.path.basename(filepath)
    lecture_num = extract_lecture_number(filename)
    
    if lecture_num == 0:
        print(f"  Skipping non-lecture file: {filename}")
        return 0
    
    subject = LECTURE_SUBJECT.get(lecture_num, "Unknown")
    topics = LECTURE_TOPIC.get(lecture_num, [])
    
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
    
    chunks = chunk_text(text)
    
    if not chunks:
        print(f"  No content found in {filename}")
        return 0
    
    ids = []
    documents = []
    metadatas = []
    
    for i, chunk in enumerate(chunks):
        doc_id = f"lecture{lecture_num}_chunk{i}"
        ids.append(doc_id)
        documents.append(chunk)
        metadatas.append({
            "source_file": filename,
            "lecture_number": lecture_num,
            "subject": subject,
            "topics": ",".join(topics),
            "chunk_index": i,
            "total_chunks": len(chunks),
        })
    
    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    reset = "--reset" in sys.argv

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted collection '{COLLECTION_NAME}'")
        except Exception:
            pass

    print(f"Loading embedding model: {EMBEDDING_MODEL} ...")
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL, device="cpu",
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # Find all .txt files in summaryBOOK
    txt_files = sorted(
        os.path.join(SUMMARY_DIR, f)
        for f in os.listdir(SUMMARY_DIR)
        if f.endswith(".txt")
    )

    if not txt_files:
        print("No .txt files found in summaryBOOK/")
        sys.exit(1)

    print(f"Found {len(txt_files)} lecture files to ingest.\n")

    total_chunks = 0
    for i, fpath in enumerate(txt_files, 1):
        fname = os.path.basename(fpath)
        count = ingest_lecture(collection, fpath)
        total_chunks += count
        print(f"  [{i}/{len(txt_files)}] {fname}: {count} chunks (subject: {LECTURE_SUBJECT.get(extract_lecture_number(fname), '?')})")

    print(f"\nDone. Indexed {total_chunks} chunks across {len(txt_files)} lectures.")
    print(f"Collection size: {collection.count()}")
