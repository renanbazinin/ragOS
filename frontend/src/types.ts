export interface QuestionContent {
  text: string;
  code_snippet: string | null;
  options: string[] | null;
}

export interface SubQuestion {
  text: string;
  code_snippet?: string | null;
  options?: string[] | null;
  solution?: QuestionSolution | null;
}

export interface QuestionSolution {
  is_present_in_file: boolean;
  correct_option: string | null;
  explanation: string | null;
}

export interface QuestionJSON {
  id: number;
  type: string;
  topic: string[];
  content: QuestionContent;
  sub_questions: SubQuestion[] | null;
  points: number | null;
  solution: QuestionSolution | null;
  difficulty_estimation: string;
}

export interface SearchResult {
  id: string;
  distance: number;
  source_file: string;
  question_id: number;
  type: string;
  topics: string;
  difficulty: string;
  year: number;
  has_solution: boolean;
  full_json: string;
  document: string;
}

export interface SearchRequest {
  query: string;
  n_results?: number;
  question_type?: string | null;
  difficulty?: string | null;
  year?: number | null;
  topic?: string | null;
  has_solution?: boolean | null;
  has_code?: boolean | null;
}

export interface GenerateRequest {
  query: string;
  question_type?: string | null;
  difficulty?: string | null;
  n_examples?: number;
}

export interface GenerateResponse {
  generated_question: QuestionJSON | { raw: string };
  examples_used: number;
}

export interface Stats {
  total_questions: number;
  types: Record<string, number>;
  difficulties: Record<string, number>;
  years: Record<string, number>;
}

// ── Practice types ──────────────────────────────────────────────────────────

export interface AIQuestionItem {
  metadata: {
    source: string;
    topic_hint: string;
    requested_type: string;
    requested_difficulty: string;
    generated_at: string;
    examples_used: number;
    subject?: string;
    token_usage?: {
      prompt_tokens: number;
      output_tokens: number;
      total_tokens: number;
    };
  };
  question: QuestionJSON;
  _filename: string;
}

export interface AIQuestionsResponse {
  questions: AIQuestionItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AIStats {
  total: number;
  types: Record<string, number>;
  difficulties: Record<string, number>;
  topics: Record<string, number>;
  subjects: Record<string, number>;
}

export interface ExamSummary {
  filename: string;
  course_name: string;
  year: string;
  semester: string;
  moed: string;
  exam_date: string;
  question_count: number;
}

export interface ExamData {
  metadata: {
    course_name: string;
    year: string;
    semester: string;
    moed: string;
    exam_date: string;
    source_file: string;
  };
  questions: QuestionJSON[];
}

export interface ExamQuestion extends QuestionJSON {
  _source_exam?: string;
  _exam_year?: string;
  _exam_semester?: string;
  _exam_moed?: string;
  _exam_date?: string;
}

export interface AllExamQuestionsResponse {
  questions: ExamQuestion[];
  total: number;
  stats: {
    total_available: number;
    returned: number;
    exams_count: number;
    types: Record<string, number>;
    difficulties: Record<string, number>;
    topics: Record<string, number>;
    years: Record<string, number>;
  };
}

export interface ExamFilterOptions {
  topics: Record<string, number>;
  types: Record<string, number>;
  difficulties: Record<string, number>;
  years: string[];
  subjects: Record<string, number>;
}

// ── Theory types ────────────────────────────────────────────────────────────

export interface TheoryQuestionItem {
  id: number;
  type: string;
  subject: string;
  topic: string[];
  difficulty_estimation: string;
  content: QuestionContent;
  solution: QuestionSolution | null;
  _source_file: string;
  _topic_hint: string;
  _requested_type: string;
  _requested_difficulty: string;
  _generated_at: string;
  _subject: string;
  _context_lectures: number[];
}

export interface TheoryQuestionsResponse {
  questions: TheoryQuestionItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface TheoryStats {
  total: number;
  subjects: Record<string, number>;
  difficulties: Record<string, number>;
  topics: Record<string, number>;
}
