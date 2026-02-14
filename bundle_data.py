"""Bundle output/, aiGenerated/, and aiTheory/ JSON files into frontend/public/data/ for static serving."""
import json, glob, os

ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(ROOT, "output")
AI_DIR = os.path.join(ROOT, "aiGenerated")
THEORY_DIR = os.path.join(ROOT, "aiTheory")
DATA_DIR = os.path.join(ROOT, "frontend", "public", "data")

os.makedirs(DATA_DIR, exist_ok=True)

# ── Bundle exams ──
exams = []
for filepath in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.json"))):
    fname = os.path.basename(filepath)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        exams.append({"filename": fname, **data})
    except (json.JSONDecodeError, IOError) as e:
        print(f"  SKIP {fname}: {e}")

with open(os.path.join(DATA_DIR, "exams.json"), "w", encoding="utf-8") as f:
    json.dump(exams, f, ensure_ascii=False)
print(f"✓ Bundled {len(exams)} exams → frontend/public/data/exams.json ({os.path.getsize(os.path.join(DATA_DIR, 'exams.json')) // 1024} KB)")

# ── Bundle AI questions ──
ai_questions = []
for filepath in sorted(glob.glob(os.path.join(AI_DIR, "*.json"))):
    fname = os.path.basename(filepath)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("metadata", {})
        questions = data.get("question", data.get("questions", []))
        if isinstance(questions, dict):
            questions = [questions]
        if isinstance(questions, list):
            for q in questions:
                ai_questions.append({
                    **q,
                    "_source_file": fname,
                    "_topic_hint": meta.get("topic_hint", ""),
                    "_requested_type": meta.get("requested_type", ""),
                    "_requested_difficulty": meta.get("requested_difficulty", ""),
                    "_generated_at": meta.get("generated_at", ""),
                    "_subject": meta.get("subject", ""),
                })
    except (json.JSONDecodeError, IOError) as e:
        print(f"  SKIP {fname}: {e}")

with open(os.path.join(DATA_DIR, "ai-questions.json"), "w", encoding="utf-8") as f:
    json.dump(ai_questions, f, ensure_ascii=False)
print(f"✓ Bundled {len(ai_questions)} AI questions → frontend/public/data/ai-questions.json ({os.path.getsize(os.path.join(DATA_DIR, 'ai-questions.json')) // 1024} KB)")

# ── Bundle Theory questions ──
theory_questions = []
for filepath in sorted(glob.glob(os.path.join(THEORY_DIR, "*.json"))):
    fname = os.path.basename(filepath)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        meta = data.get("metadata", {})
        question = data.get("question", {})
        if isinstance(question, dict) and question:
            theory_questions.append({
                **question,
                "_source_file": fname,
                "_topic_hint": meta.get("topic_hint", ""),
                "_requested_type": meta.get("requested_type", "MultipleChoice"),
                "_requested_difficulty": meta.get("requested_difficulty", ""),
                "_generated_at": meta.get("generated_at", ""),
                "_subject": meta.get("subject", ""),
                "_context_lectures": meta.get("context_lectures", []),
            })
    except (json.JSONDecodeError, IOError) as e:
        print(f"  SKIP {fname}: {e}")

with open(os.path.join(DATA_DIR, "theory-questions.json"), "w", encoding="utf-8") as f:
    json.dump(theory_questions, f, ensure_ascii=False)
print(f"✓ Bundled {len(theory_questions)} Theory questions → frontend/public/data/theory-questions.json ({os.path.getsize(os.path.join(DATA_DIR, 'theory-questions.json')) // 1024} KB)")
