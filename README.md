# ragOS

A RAG-powered study tool for Operating Systems exam preparation.

## Features

- **Search** past exam questions using semantic search (ChromaDB + SentenceTransformers)
- **Generate** new AI-powered practice questions with Google Gemini
- **Practice** mode with interactive multiple choice, shuffling, and filtering
- **Mix & Shuffle** questions from all past exams with filters (topic, type, difficulty, year)
- **Bulk Generation** of thousands of AI questions across all OS topics

## Stack

- **Backend:** Python, FastAPI, ChromaDB, SentenceTransformers, Google Gemini API
- **Frontend:** React 19, TypeScript, Vite, React Router

## Setup

### Backend
```bash
pip install -r requirements.txt
python -m uvicorn api:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Project Structure

- `api.py` — FastAPI REST backend
- `query.py` — RAG search & generation functions
- `ingest.py` — Ingest exam JSONs into ChromaDB
- `parse_exam.py` — Parse exam PDFs to JSON
- `generate_bulk.py` — Bulk AI question generator
- `output/` — Parsed exam JSON files
- `aiGenerated/` — AI-generated question files
- `frontend/` — React/Vite frontend
