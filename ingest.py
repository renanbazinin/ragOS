"""
Ingest parsed OS exam questions into ChromaDB vector database.

Reads JSON files from output/, builds embeddings using a multilingual
sentence-transformer model, and stores them in a local ChromaDB collection
for semantic search.

Usage:
    python ingest.py                        # Ingest all JSONs from output/
    python ingest.py output/os24SA.json     # Ingest a single file
    python ingest.py --reset                # Delete collection & re-ingest all
"""

import os
import re
import sys
import json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_db")
COLLECTION_NAME = "os_exam_questions"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"  # Hebrew + English

# ── Helpers ──────────────────────────────────────────────────────────────────


def year_from_filename(source_file: str) -> int:
    """Extract year from filename like 'os24SA.pdf' -> 2024."""
    stem = source_file.replace(".pdf", "").replace(".json", "")
    match = re.match(r"^os(\d{2})", stem)
    if match:
        return 2000 + int(match.group(1))
    return 0


def build_document_text(question: dict) -> str:
    """Build the text that will be embedded for semantic search.

    Concatenates question text, code, options, and sub-questions
    into a single searchable string.
    """
    parts = []

    # Main question text
    parts.append(question["content"].get("text", ""))

    # Code snippet
    if question["content"].get("code_snippet"):
        parts.append(question["content"]["code_snippet"])

    # MC options
    if question["content"].get("options"):
        parts.extend(question["content"]["options"])

    # Sub-questions
    if question.get("sub_questions"):
        for sq in question["sub_questions"]:
            parts.append(sq.get("text", ""))
            if sq.get("code_snippet"):
                parts.append(sq["code_snippet"])
            if sq.get("options"):
                parts.extend(sq["options"])

    return "\n".join(p for p in parts if p)


def extract_metadata(file_meta: dict, question: dict) -> dict:
    """Build flat metadata dict for ChromaDB storage."""

    # Year: try metadata first, fall back to filename
    year_str = file_meta.get("year", "")
    try:
        year = int(year_str)
    except (ValueError, TypeError):
        year = year_from_filename(file_meta.get("source_file", ""))

    # has_code: check main content AND sub-questions
    has_code = bool(question["content"].get("code_snippet"))
    if not has_code and question.get("sub_questions"):
        has_code = any(sq.get("code_snippet") for sq in question["sub_questions"])

    # has_solution: check root AND sub-question level
    sol = question.get("solution", {})
    has_solution = bool(sol and sol.get("is_present_in_file"))
    if not has_solution and question.get("sub_questions"):
        has_solution = any(
            sq.get("solution", {}).get("is_present_in_file", False)
            for sq in question["sub_questions"]
            if isinstance(sq.get("solution"), dict)
        )

    topics = question.get("topic", [])

    return {
        "source_file": file_meta.get("source_file", ""),
        "year": year,
        "semester": file_meta.get("semester", ""),
        "moed": file_meta.get("moed", ""),
        "question_id": question.get("id", 0),
        "type": question.get("type", "Unknown"),
        "topics": ",".join(topics) if topics else "",
        "difficulty": question.get("difficulty_estimation", "Unknown") or "Unknown",
        "has_code": has_code,
        "has_solution": has_solution,
        "full_json": json.dumps(question, ensure_ascii=False),
    }


def make_doc_id(file_meta: dict, question: dict) -> str:
    """Deterministic document ID: e.g. 'os24SA_q6'."""
    stem = file_meta.get("source_file", "unknown")
    stem = stem.replace(".pdf", "").replace(".json", "")
    return f"{stem}_q{question['id']}"


# ── Ingestion ────────────────────────────────────────────────────────────────


def ingest_file(collection, filepath: str) -> int:
    """Ingest a single JSON file into the collection. Returns question count."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    file_meta = data.get("metadata", {})
    questions = data.get("questions", [])

    ids = []
    documents = []
    metadatas = []

    for q in questions:
        ids.append(make_doc_id(file_meta, q))
        documents.append(build_document_text(q))
        metadatas.append(extract_metadata(file_meta, q))

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

    return len(questions)


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    reset = "--reset" in sys.argv
    specific_files = [a for a in sys.argv[1:] if a != "--reset"]

    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted collection '{COLLECTION_NAME}'")
        except Exception:
            pass

    # Load embedding model (first run downloads ~471 MB)
    print(f"Loading embedding model: {EMBEDDING_MODEL} ...")
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL,
        device="cpu",
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
        metadata={"hnsw:space": "cosine"},
    )

    # Determine files to process
    if specific_files:
        json_files = [os.path.abspath(f) for f in specific_files]
    else:
        json_files = sorted(
            os.path.join(OUTPUT_DIR, f)
            for f in os.listdir(OUTPUT_DIR)
            if f.endswith(".json")
        )

    if not json_files:
        print("No JSON files found.")
        sys.exit(1)

    print(f"Found {len(json_files)} file(s) to ingest.\n")

    total = 0
    for i, fpath in enumerate(json_files, 1):
        fname = os.path.basename(fpath)
        count = ingest_file(collection, fpath)
        total += count
        print(f"  [{i}/{len(json_files)}] {fname}: {count} questions")

    print(f"\nDone. Indexed {total} questions.")
    print(f"Collection size: {collection.count()}")
