"""
FastAPI backend that exposes the RAG search & generation pipeline as REST endpoints.
"""

import os
import json
import glob
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from query import search_questions, generate_question

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.path.join(PROJECT_DIR, "chroma_db")
AI_GENERATED_DIR = os.path.join(PROJECT_DIR, "aiGenerated")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
COLLECTION_NAME = "os_exam_questions"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# Global reference – set during lifespan
collection = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the embedding model and open the ChromaDB collection once at startup."""
    global collection
    print("Loading embedding model …")
    embed_fn = SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL, device="cpu"
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(
        name=COLLECTION_NAME, embedding_function=embed_fn
    )
    print(f"Collection loaded — {collection.count()} documents")
    yield
    print("Shutting down …")


app = FastAPI(title="ragOS API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ────────────────────────────────────────────────


class SearchRequest(BaseModel):
    query: str
    n_results: int = Field(default=5, ge=1, le=20)
    question_type: str | None = None
    difficulty: str | None = None
    year: int | None = None
    topic: str | None = None
    has_solution: bool | None = None
    has_code: bool | None = None


class GenerateRequest(BaseModel):
    query: str
    question_type: str | None = None
    difficulty: str | None = None
    n_examples: int = Field(default=3, ge=1, le=5)


class QuestionOut(BaseModel):
    id: str
    distance: float
    source_file: str
    question_id: int
    type: str
    topics: str
    difficulty: str
    year: int
    has_solution: bool
    full_json: str  # raw JSON of the question
    document: str  # embedded text


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "documents": collection.count() if collection else 0}


@app.post("/search", response_model=list[QuestionOut])
async def api_search(req: SearchRequest):
    results = search_questions(
        collection,
        query_text=req.query,
        n_results=req.n_results,
        question_type=req.question_type,
        difficulty=req.difficulty,
        year=req.year,
        topic=req.topic,
        has_solution=req.has_solution,
        has_code=req.has_code,
    )
    return results


@app.post("/generate")
async def api_generate(req: GenerateRequest):
    # First, retrieve example questions via semantic search
    examples = search_questions(
        collection,
        query_text=req.query,
        n_results=req.n_examples,
        question_type=req.question_type,
        difficulty=req.difficulty,
    )
    if not examples:
        raise HTTPException(status_code=404, detail="No example questions found for that query.")

    raw = generate_question(
        example_questions=examples,
        topic_hint=req.query,
        question_type=req.question_type,
        difficulty=req.difficulty,
    )

    # Try to parse so the client gets clean JSON
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"raw": raw}

    return {"generated_question": parsed, "examples_used": len(examples)}


@app.get("/topics")
async def list_topics():
    """Return all unique topics stored in the collection."""
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    topics_set: set[str] = set()
    for meta in all_meta:
        for t in meta.get("topics", "").split(","):
            t = t.strip()
            if t:
                topics_set.add(t)
    return sorted(topics_set)


@app.get("/stats")
async def stats():
    """Return aggregate stats about the collection."""
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    types: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    years: dict[int, int] = {}
    for m in all_meta:
        t = m.get("type", "Unknown")
        types[t] = types.get(t, 0) + 1
        d = m.get("difficulty", "Unknown")
        difficulties[d] = difficulties.get(d, 0) + 1
        y = m.get("year", 0)
        years[y] = years.get(y, 0) + 1
    return {
        "total_questions": len(all_meta),
        "types": types,
        "difficulties": difficulties,
        "years": dict(sorted(years.items())),
    }


# ── Practice endpoints ───────────────────────────────────────────────────────


@app.get("/practice/ai-questions")
async def list_ai_questions(
    topic: Optional[str] = None,
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """List AI-generated questions from aiGenerated/ folder with optional filters."""
    questions = _load_ai_questions()

    # Apply filters
    # Filter out malformed entries
    questions = [q for q in questions if isinstance(q.get("question"), dict)]

    if topic:
        topic_lower = topic.lower()
        def _topic_match(q: dict) -> bool:
            tl = q["question"].get("topic", [])
            if isinstance(tl, str):
                tl = [tl]
            return (
                any(topic_lower in t.lower() for t in tl if isinstance(t, str))
                or topic_lower in q.get("metadata", {}).get("topic_hint", "").lower()
            )
        questions = [q for q in questions if _topic_match(q)]
    if question_type:
        questions = [q for q in questions if q["question"].get("type") == question_type]
    if difficulty:
        questions = [
            q for q in questions
            if q["question"].get("difficulty_estimation") == difficulty
            or q.get("metadata", {}).get("requested_difficulty") == difficulty
        ]

    total = len(questions)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "questions": questions[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@app.get("/practice/ai-stats")
async def ai_stats():
    """Stats for AI-generated questions."""
    questions = _load_ai_questions()
    types: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    topics: dict[str, int] = {}

    for item in questions:
        q = item.get("question", {})
        if not isinstance(q, dict):
            continue
        t = q.get("type", "Unknown")
        types[t] = types.get(t, 0) + 1
        d = q.get("difficulty_estimation", q.get("difficulty", "Unknown"))
        difficulties[d] = difficulties.get(d, 0) + 1
        topic_list = q.get("topic", [])
        if isinstance(topic_list, str):
            topic_list = [topic_list]
        for topic in topic_list:
            if isinstance(topic, str):
                topics[topic] = topics.get(topic, 0) + 1

    return {
        "total": len(questions),
        "types": types,
        "difficulties": difficulties,
        "topics": dict(sorted(topics.items(), key=lambda x: -x[1])),
    }


@app.get("/practice/exams")
async def list_exams():
    """List all available exam files from output/ folder."""
    exams = []
    for filepath in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json"))):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            exams.append({
                "filename": os.path.basename(filepath),
                "course_name": meta.get("course_name", ""),
                "year": meta.get("year", ""),
                "semester": meta.get("semester", ""),
                "moed": meta.get("moed", ""),
                "exam_date": meta.get("exam_date", ""),
                "question_count": len(data.get("questions", [])),
            })
        except (json.JSONDecodeError, IOError):
            continue
    return exams


@app.get("/practice/exam/{filename}")
async def get_exam(filename: str):
    """Get all questions from a specific exam file."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Exam not found")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except (json.JSONDecodeError, IOError) as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/practice/exams/filter-options")
async def exam_filter_options():
    """Return all unique topics, types, difficulties, years across all exam questions."""
    topics: dict[str, int] = {}
    types: dict[str, int] = {}
    difficulties: dict[str, int] = {}
    years: set[str] = set()

    for filepath in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json"))):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            y = meta.get("year", "")
            if y:
                years.add(str(y))
            for q in data.get("questions", []):
                t = q.get("type", "Unknown")
                types[t] = types.get(t, 0) + 1
                d = q.get("difficulty_estimation", q.get("difficulty", "Unknown"))
                difficulties[d] = difficulties.get(d, 0) + 1
                tl = q.get("topic", [])
                if isinstance(tl, str):
                    tl = [tl]
                for tp in tl:
                    if tp:
                        topics[tp] = topics.get(tp, 0) + 1
        except (json.JSONDecodeError, IOError):
            continue

    return {
        "topics": dict(sorted(topics.items(), key=lambda x: -x[1])),
        "types": dict(sorted(types.items(), key=lambda x: -x[1])),
        "difficulties": dict(sorted(difficulties.items(), key=lambda x: -x[1])),
        "years": sorted(years),
    }


@app.get("/practice/exams/all-questions")
async def all_exam_questions(
    question_type: Optional[str] = None,
    difficulty: Optional[str] = None,
    year: Optional[str] = None,
    topic: Optional[str] = None,
    filenames: Optional[str] = None,  # comma-separated exam filenames
    limit: Optional[int] = Query(default=None, ge=1, le=500),
    shuffle: bool = False,
):
    """Return merged questions from all (or selected) exams, with filters."""
    import random
    all_questions: list[dict] = []

    target_files = None
    if filenames:
        target_files = set(f.strip() for f in filenames.split(","))

    for filepath in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json"))):
        fname = os.path.basename(filepath)
        if target_files and fname not in target_files:
            continue
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("metadata", {})
            for q in data.get("questions", []):
                q["_source_exam"] = fname.replace(".json", "")
                q["_exam_year"] = meta.get("year", "")
                q["_exam_semester"] = meta.get("semester", "")
                q["_exam_moed"] = meta.get("moed", "")
                q["_exam_date"] = meta.get("exam_date", "")
                all_questions.append(q)
        except (json.JSONDecodeError, IOError):
            continue

    # Apply filters
    if question_type:
        all_questions = [q for q in all_questions if q.get("type") == question_type]
    if difficulty:
        all_questions = [
            q for q in all_questions
            if q.get("difficulty_estimation", q.get("difficulty", "")) == difficulty
        ]
    if year:
        all_questions = [q for q in all_questions if year in q.get("_exam_year", "")]
    if topic:
        topic_lower = topic.lower()
        all_questions = [
            q for q in all_questions
            if any(
                topic_lower in t.lower()
                for t in (q.get("topic", []) if isinstance(q.get("topic"), list) else [str(q.get("topic", ""))])
            )
        ]

    if shuffle:
        random.shuffle(all_questions)

    total_available = len(all_questions)
    exams_set = set(q.get("_source_exam", "") for q in all_questions)

    if limit:
        all_questions = all_questions[:limit]

    # Gather stats for the filtered set
    type_counts: dict[str, int] = {}
    diff_counts: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    year_counts: dict[str, int] = {}
    for q in all_questions:
        t = q.get("type", "Unknown")
        type_counts[t] = type_counts.get(t, 0) + 1
        d = q.get("difficulty_estimation", q.get("difficulty", "Unknown"))
        diff_counts[d] = diff_counts.get(d, 0) + 1
        tl = q.get("topic", [])
        if isinstance(tl, str):
            tl = [tl]
        for tp in tl:
            topic_counts[tp] = topic_counts.get(tp, 0) + 1
        ey = q.get("_exam_year", "")
        if ey:
            year_counts[ey] = year_counts.get(ey, 0) + 1

    return {
        "questions": all_questions,
        "total": len(all_questions),
        "stats": {
            "total_available": total_available,
            "returned": len(all_questions),
            "exams_count": len(exams_set - {""}),
            "types": type_counts,
            "difficulties": diff_counts,
            "topics": dict(sorted(topic_counts.items(), key=lambda x: -x[1])),
            "years": dict(sorted(year_counts.items())),
        },
    }


def _load_ai_questions() -> list[dict]:
    """Load all AI-generated question files."""
    questions = []
    if not os.path.isdir(AI_GENERATED_DIR):
        return questions
    for filepath in sorted(glob.glob(os.path.join(AI_GENERATED_DIR, "*.json"))):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_filename"] = os.path.basename(filepath)
            questions.append(data)
        except (json.JSONDecodeError, IOError):
            continue
    return questions
