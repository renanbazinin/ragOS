"""
Exam PDF Parser using Google Gemini Multimodal API.

Sends entire PDFs to Gemini and asks it to return structured JSON.
Handles Hebrew text, code blocks, multiple-choice and open questions,
and separate answer keys — all via the model's vision capabilities.

Usage:
    python parse_exam.py                      # Parse all PDFs in tests/
    python parse_exam.py tests/os24SA.pdf     # Parse a single PDF
"""

import os
import sys
import re
import time
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.5-flash"  # fast + cheap; switch to "gemini-2.5-pro" for harder PDFs
TESTS_DIR = os.path.join(os.path.dirname(__file__), "tests")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")

# ── Filename metadata extraction ─────────────────────────────────────────────

SEMESTER_MAP = {"A": "Semester A", "B": "Semester B", "S": "Summer"}
MOED_MAP = {"A": "Moed A", "B": "Moed B", "C": "Moed C"}


def parse_filename(filename: str) -> dict:
    """
    Extract metadata from filenames like 'os24SA.pdf'.
      os  = course (Operating Systems)
      24  = year (2024)
      S   = semester (Summer / A / B)
      A   = moed (A / B / C)
    """
    stem = filename.replace(".pdf", "")
    match = re.match(r"^os(\d{2})([ABS])([ABC])$", stem)
    if not match:
        return {
            "course_name": "Operating Systems",
            "year": "",
            "semester": "",
            "moed": "",
            "source_file": filename,
        }
    year_short, sem_code, moed_code = match.groups()
    return {
        "course_name": "Operating Systems",
        "year": f"20{year_short}",
        "semester": SEMESTER_MAP.get(sem_code, sem_code),
        "moed": MOED_MAP.get(moed_code, moed_code),
        "source_file": filename,
    }


# ── JSON Schema (included in the prompt so Gemini knows the target) ──────────

JSON_SCHEMA = """\
{
  "metadata": {
    "course_name": "string",
    "year": "string",
    "semester": "string",       // e.g. "Semester A", "Summer"
    "moed": "string",           // e.g. "Moed A", "Moed B"
    "exam_date": "string|null", // if visible in the PDF
    "source_file": "string"
  },
  "questions": [
    {
      "id": "number",                        // sequential question number
      "type": "MultipleChoice | Open | CodeAnalysis",
      "topic": ["string"],                   // best-guess OS topics
      "content": {
        "text": "string",                    // full question text (keep Hebrew)
        "code_snippet": "string|null",       // extracted code block if any
        "options": ["string"] | null         // MC options, null for open
      },
      "sub_questions": [                     // only if the question has sub-parts
        {
          "id": "string",                    // e.g. "a", "b", "1.1"
          "text": "string",
          "code_snippet": "string|null",
          "options": ["string"] | null
        }
      ] | null,
      "points": "number|null",              // if listed in the exam
      "solution": {
        "is_present_in_file": "boolean",
        "correct_option": "string|null",    // for MC
        "explanation": "string|null"        // full solution text
      },
      "difficulty_estimation": "Easy | Medium | Hard"
    }
  ]
}"""

# ── System instruction for Gemini ────────────────────────────────────────────

SYSTEM_INSTRUCTION = """\
You are an expert Teaching Assistant for a university Operating Systems course.
Your job is to convert an exam PDF into a structured JSON object.

CRITICAL RULES:
1. **Extract EVERY question** — including all sub-parts (a, b, c …).
2. **Locate the answer key / proposed solution (הצעת פתרון / תשובות)**
   at the END of the document and PAIR each answer with its question.
   If no answers exist, set solution.is_present_in_file = false and leave
   correct_option / explanation as null.
3. **Hebrew text** must be preserved exactly as written.
4. **Code blocks** go into code_snippet, NOT inside text.
5. **Topic tags** — assign 1-3 relevant OS topics per question from this list
   (pick the best matches):
   Processes, Threads, Scheduling, Synchronization, Deadlocks,
   Memory Management, Virtual Memory, Paging, File Systems,
   I/O, Disk Scheduling, Concurrency, Atomic Operations,
   Semaphores, Mutexes, Signals, IPC, System Calls, CPU Scheduling,
   Page Replacement, Segmentation, Linking, Security, Networking.
6. Output **only** valid JSON — no markdown fences, no commentary.
"""

# ── Core parser ──────────────────────────────────────────────────────────────

genai.configure(api_key=API_KEY)


def parse_exam_pdf(pdf_path: str) -> dict:
    """Upload a PDF to Gemini, extract structured exam JSON."""
    filename = os.path.basename(pdf_path)
    file_meta = parse_filename(filename)

    print(f"  Uploading {filename} …")
    uploaded = genai.upload_file(path=pdf_path, display_name=filename)

    # Wait for server-side processing
    while uploaded.state.name == "PROCESSING":
        time.sleep(2)
        uploaded = genai.get_file(uploaded.name)
    if uploaded.state.name == "FAILED":
        raise RuntimeError(f"Gemini file upload failed for {filename}")

    print(f"  Generating JSON for {filename} …")

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    prompt = f"""\
Parse this exam PDF and return a single JSON object matching this schema:

{JSON_SCHEMA}

Pre-filled metadata from the filename (override exam_date if you find it in the PDF):
{json.dumps(file_meta, ensure_ascii=False, indent=2)}

Return ONLY the JSON object — no extra text."""

    response = model.generate_content(
        [uploaded, prompt],
        generation_config={
            "temperature": 0.1,
            "response_mime_type": "application/json",
        },
    )

    # Clean up remote file
    try:
        genai.delete_file(uploaded.name)
    except Exception:
        pass

    # Parse the response
    raw = response.text.strip()
    # Strip markdown fences if model added them despite instructions
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    return json.loads(raw)


# ── Batch runner ─────────────────────────────────────────────────────────────


def run_batch(pdf_paths: list[str]):
    """Parse multiple PDFs and save each as a JSON file under output/."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    results = {"success": [], "failed": []}

    for i, path in enumerate(pdf_paths, 1):
        name = os.path.basename(path)
        print(f"\n[{i}/{len(pdf_paths)}] {name}")

        try:
            data = parse_exam_pdf(path)
            out_name = name.replace(".pdf", ".json")
            out_path = os.path.join(OUTPUT_DIR, out_name)
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  [OK] Saved -> output/{out_name}")
            results["success"].append(name)
        except Exception as e:
            print(f"  [FAIL] {e}")
            results["failed"].append({"file": name, "error": str(e)})

        # Small delay between calls to avoid rate-limiting
        if i < len(pdf_paths):
            time.sleep(1)

    print("\n" + "=" * 50)
    print(f"Done: {len(results['success'])} succeeded, {len(results['failed'])} failed")
    if results["failed"]:
        print("Failed files:")
        for f in results["failed"]:
            print(f"  - {f['file']}: {f['error']}")


# ── CLI entry point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse specific files
        paths = [os.path.abspath(p) for p in sys.argv[1:]]
    else:
        # Parse all PDFs in tests/
        paths = sorted(
            os.path.join(TESTS_DIR, f)
            for f in os.listdir(TESTS_DIR)
            if f.endswith(".pdf")
        )

    if not paths:
        print("No PDF files found.")
        sys.exit(1)

    print(f"Found {len(paths)} PDF(s) to parse.")
    run_batch(paths)
