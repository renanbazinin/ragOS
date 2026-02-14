"""
Query the summaryBOOK ChromaDB and generate theory-based multiple-choice
questions from lecture content.

Searches the summary chunk collection, retrieves relevant lecture material,
and asks Gemini to create a multiple-choice question grounded in that theory.

Usage:
    python query_summary.py "scheduling algorithms"
    python query_summary.py "paging" --subject Virtualization --difficulty Hard
    python query_summary.py "deadlocks" --generate
"""

import os
import sys
import json
import argparse
import chromadb
from dotenv import load_dotenv
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import google.generativeai as genai

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_summary")
COLLECTION_NAME = "os_summary_chunks"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

SUBJECTS = ["Virtualization", "Concurrency", "File Systems", "Disks"]

# ── Search ───────────────────────────────────────────────────────────────────


def search_summary(
    collection,
    query_text: str,
    n_results: int = 5,
    subject: str = None,
    lecture_number: int = None,
) -> list[dict]:
    """Semantic search over lecture summary chunks with optional filters."""

    where_clauses = []
    if subject:
        where_clauses.append({"subject": {"$eq": subject}})
    if lecture_number:
        where_clauses.append({"lecture_number": {"$eq": lecture_number}})

    where = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
        where=where,
        include=["metadatas", "distances", "documents"],
    )

    chunks = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        chunks.append({
            "id": results["ids"][0][i],
            "distance": results["distances"][0][i],
            "source_file": meta["source_file"],
            "lecture_number": meta["lecture_number"],
            "subject": meta["subject"],
            "topics": meta["topics"],
            "chunk_index": meta["chunk_index"],
            "document": results["documents"][0][i],
        })

    return chunks


# ── Display ──────────────────────────────────────────────────────────────────


def display_results(chunks: list[dict]):
    """Print search results."""
    if not chunks:
        print("No results found.")
        return

    for i, c in enumerate(chunks, 1):
        print(f"\n--- Result {i} (distance: {c['distance']:.4f}) ---")
        print(f"  Source: Lecture {c['lecture_number']} ({c['source_file']})")
        print(f"  Subject: {c['subject']} | Topics: {c['topics']}")
        preview = c["document"][:300].replace("\n", " ")
        print(f"  Preview: {preview}...")


# ── Generation ───────────────────────────────────────────────────────────────


def generate_mc_question(
    context_chunks: list[dict],
    topic_hint: str,
    subject: str,
    difficulty: str = "Medium",
) -> object:
    """Generate a multiple-choice theory question from lecture summary context."""

    genai.configure(api_key=API_KEY)

    # Build context from retrieved chunks
    context_text = ""
    for i, chunk in enumerate(context_chunks[:5], 1):
        context_text += f"\n--- Lecture {chunk['lecture_number']} (chunk {chunk['chunk_index']}) ---\n"
        context_text += chunk["document"] + "\n"

    prompt = f"""You are an expert Operating Systems course instructor creating exam questions.

You are given lecture material from an OS course. Based ONLY on the provided material,
create ONE original multiple-choice question.

REQUIREMENTS:
1. Subject category: {subject}
2. Topic focus: {topic_hint}
3. Difficulty: {difficulty}
4. The question must be a THEORY question about OS concepts.
5. Write the question text in Hebrew (as in the lecture material).
6. Provide exactly 4 answer options (labeled א, ב, ג, ד).
7. Only ONE option is correct.
8. If a code snippet helps illustrate the concept, include one in C/C++ or pseudo-code.
   Otherwise set code_snippet to null.
9. Include a detailed explanation of the correct answer in Hebrew.
10. The question must be answerable from the provided lecture material.
11. Output ONLY valid JSON matching this schema (no markdown, no commentary):

{{
  "id": 1,
  "type": "MultipleChoice",
  "subject": "{subject}",
  "topic": ["{topic_hint}"],
  "difficulty_estimation": "{difficulty}",
  "content": {{
    "text": "Hebrew question text",
    "code_snippet": "C/C++ code snippet or null",
    "options": [
      "א. option text",
      "ב. option text",
      "ג. option text",
      "ד. option text"
    ]
  }},
  "solution": {{
    "correct_option": "א/ב/ג/ד",
    "explanation": "Detailed Hebrew explanation referencing the theory"
  }}
}}

LECTURE MATERIAL (use this as your knowledge source):
{context_text}

--- YOUR NEW QUESTION (JSON only) ---"""

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=(
            "You are an expert OS course exam writer. "
            "Create theory-based multiple-choice questions grounded in the provided lecture material. "
            "Output only valid JSON."
        ),
    )

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7,
            "response_mime_type": "application/json",
        },
    )

    return response


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search OS lecture summaries & generate questions")
    parser.add_argument("query", help="Search query (Hebrew or English)")
    parser.add_argument("-n", "--num-results", type=int, default=5)
    parser.add_argument("--subject", choices=SUBJECTS, help="Filter by subject category")
    parser.add_argument("--lecture", type=int, help="Filter by lecture number")
    parser.add_argument("--difficulty", choices=["Easy", "Medium", "Hard"], default="Medium")
    parser.add_argument("--generate", action="store_true",
                        help="Generate a new MC question from retrieved context")
    parser.add_argument("--raw", action="store_true", help="Output raw chunk text")

    args = parser.parse_args()

    # Initialize ChromaDB
    print("Loading embedding model ...")
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL, device="cpu"
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embed_fn,
    )

    # Search
    results = search_summary(
        collection,
        query_text=args.query,
        n_results=args.num_results,
        subject=args.subject,
        lecture_number=args.lecture,
    )

    if args.raw:
        for c in results:
            print(c["document"])
            print()
    else:
        display_results(results)

    # Generate
    if args.generate:
        if not results:
            print("\nNo context found — cannot generate.")
            sys.exit(1)

        subject = args.subject or (results[0]["subject"] if results else "Virtualization")

        print(f"\n{'='*50}")
        print(f"Generating MC question ({args.difficulty}) about '{args.query}' ...")
        response = generate_mc_question(
            context_chunks=results,
            topic_hint=args.query,
            subject=subject,
            difficulty=args.difficulty,
        )

        print("\n=== GENERATED QUESTION ===")
        try:
            gen_text = response.text if hasattr(response, "text") else str(response)
            parsed = json.loads(gen_text)
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(gen_text or response)
