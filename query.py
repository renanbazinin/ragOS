"""
Search OS exam questions and optionally generate new ones with Gemini.

Queries the ChromaDB vector database built by ingest.py, supports
metadata filtering, and can use retrieved questions as few-shot examples
for Gemini to generate novel exam questions.

Usage:
    python query.py "synchronization deadlock"                         # Semantic search
    python query.py "paging" --type MultipleChoice --difficulty Hard   # With filters
    python query.py "semaphores" --generate                            # Search + generate
    python query.py "mutex" --generate --type CodeAnalysis             # Generate specific type
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
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_db")
COLLECTION_NAME = "os_exam_questions"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

API_KEY = os.getenv("GEMINI_API_KEY", "")
# Allow overriding the Gemini model via environment variable for pilots
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── Search ───────────────────────────────────────────────────────────────────


def search_questions(
    collection,
    query_text: str,
    n_results: int = 5,
    question_type: str = None,
    difficulty: str = None,
    year: int = None,
    topic: str = None,
    has_solution: bool = None,
    has_code: bool = None,
) -> list[dict]:
    """Semantic search with optional metadata filters."""

    where_clauses = []
    if question_type:
        where_clauses.append({"type": {"$eq": question_type}})
    if difficulty:
        where_clauses.append({"difficulty": {"$eq": difficulty}})
    if year:
        where_clauses.append({"year": {"$eq": year}})
    if topic:
        where_clauses.append({"topics": {"$contains": topic}})
    if has_solution is not None:
        where_clauses.append({"has_solution": {"$eq": has_solution}})
    if has_code is not None:
        where_clauses.append({"has_code": {"$eq": has_code}})

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

    questions = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        questions.append({
            "id": results["ids"][0][i],
            "distance": results["distances"][0][i],
            "source_file": meta["source_file"],
            "question_id": meta["question_id"],
            "type": meta["type"],
            "topics": meta["topics"],
            "difficulty": meta["difficulty"],
            "year": meta["year"],
            "has_solution": meta["has_solution"],
            "full_json": meta["full_json"],
            "document": results["documents"][0][i],
        })

    return questions


# ── Display ──────────────────────────────────────────────────────────────────


def display_results(questions: list[dict]):
    """Print search results (cp1255-safe)."""
    if not questions:
        print("No results found.")
        return

    for i, q in enumerate(questions, 1):
        print(f"\n--- Result {i} (distance: {q['distance']:.4f}) ---")
        print(f"  Source: {q['source_file']} Q{q['question_id']}")
        print(f"  Type: {q['type']} | Difficulty: {q['difficulty']} | Year: {q['year']}")
        print(f"  Topics: {q['topics']}")
        print(f"  Has solution: {q['has_solution']}")
        # Preview: first 300 chars, newlines collapsed
        preview = q["document"][:300].replace("\n", " ")
        print(f"  Preview: {preview}...")


# ── Generation ───────────────────────────────────────────────────────────────


def generate_question(
    example_questions: list[dict],
    topic_hint: str,
    question_type: str = None,
    difficulty: str = None,
) -> str:
    """Generate a new exam question using retrieved examples as few-shot context."""

    genai.configure(api_key=API_KEY)

    # Collect example JSONs (up to 3)
    examples = [q["full_json"] for q in example_questions[:3]]

    # Infer type/difficulty from examples if not specified
    if not question_type:
        types = [q["type"] for q in example_questions[:3]]
        question_type = max(set(types), key=types.count)
    if not difficulty:
        diffs = [q["difficulty"] for q in example_questions[:3]]
        difficulty = max(set(diffs), key=diffs.count)

    prompt = f"""You are an expert Operating Systems course instructor creating exam questions.

Based on the following {len(examples)} example exam questions, create ONE new, original question.

REQUIREMENTS:
1. The question must be about: {topic_hint}
2. Question type: {question_type}
3. Difficulty: {difficulty}
4. Write the question text in Hebrew (as in the examples).
5. If it involves code, use C/C++ (as in the examples).
6. Include a complete solution with explanation.
7. Output ONLY valid JSON matching this schema (no markdown, no commentary):

{{
  "id": 1,
  "type": "{question_type}",
  "topic": ["string"],
  "content": {{
    "text": "Hebrew question text",
    "code_snippet": "C code or null",
    "options": ["option1", ...] or null
  }},
  "sub_questions": null,
  "points": null,
  "solution": {{
    "is_present_in_file": true,
    "correct_option": "string or null",
    "explanation": "Hebrew explanation"
  }},
  "difficulty_estimation": "{difficulty}"
}}

EXAMPLE QUESTIONS (for reference on style and depth):
"""

    for i, ej in enumerate(examples, 1):
        prompt += f"\n--- Example {i} ---\n{ej}\n"

    prompt += "\n--- YOUR NEW QUESTION (JSON only) ---"

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction="You are an expert OS course exam writer. Output only valid JSON.",
    )

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.7,
            "response_mime_type": "application/json",
        },
    )

    # Return the full response object so callers can inspect usage/metadata.
    return response


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search OS exam questions")
    parser.add_argument("query", help="Search query (Hebrew or English)")
    parser.add_argument("-n", "--num-results", type=int, default=5)
    parser.add_argument("--type", choices=["MultipleChoice", "Open", "CodeAnalysis"],
                        dest="qtype")
    parser.add_argument("--difficulty", choices=["Easy", "Medium", "Hard"])
    parser.add_argument("--year", type=int)
    parser.add_argument("--topic", help="Topic filter (substring match)")
    parser.add_argument("--has-solution", action="store_true", default=None)
    parser.add_argument("--has-code", action="store_true", default=None)
    parser.add_argument("--generate", action="store_true",
                        help="Generate a new question based on search results")
    parser.add_argument("--raw", action="store_true",
                        help="Output raw JSON of results")

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
    results = search_questions(
        collection,
        query_text=args.query,
        n_results=args.num_results,
        question_type=args.qtype,
        difficulty=args.difficulty,
        year=args.year,
        topic=args.topic,
        has_solution=True if args.has_solution else None,
        has_code=True if args.has_code else None,
    )

    if args.raw:
        for q in results:
            print(q["full_json"])
            print()
    else:
        display_results(results)

    # Generate
    if args.generate:
        if not results:
            print("\nNo examples found -- cannot generate.")
            sys.exit(1)

        print("\n" + "=" * 50)
        print("Generating new question with Gemini ...")
        generated = generate_question(
            results,
            topic_hint=args.query,
            question_type=args.qtype,
            difficulty=args.difficulty,
        )
        print("\n=== GENERATED QUESTION ===")

        # The generator now returns a response object. Extract text and metadata
        gen_text = None
        try:
            if hasattr(generated, "text"):
                gen_text = generated.text
            else:
                gen_text = str(generated)

            # Pretty-print the JSON from the text
            parsed = json.loads(gen_text)
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
        except json.JSONDecodeError:
            print(gen_text or generated)

        # Print response metadata/usage if available (helpful for token accounting)
        print("\n=== RESPONSE METADATA ===")
        try:
            if hasattr(generated, "metadata"):
                print(json.dumps(generated.metadata, ensure_ascii=False, indent=2))
            elif hasattr(generated, "__dict__"):
                # Fallback: show serializable parts of __dict__
                meta = {k: v for k, v in vars(generated).items() if not callable(v)}
                try:
                    print(json.dumps(meta, ensure_ascii=False, indent=2))
                except TypeError:
                    print(meta)
            else:
                print(str(generated))
        except Exception as e:
            print("(failed to print metadata)", e)
