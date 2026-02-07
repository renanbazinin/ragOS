import type { SearchRequest, SearchResult, GenerateRequest, GenerateResponse, Stats, AIQuestionsResponse, AIStats, ExamSummary, ExamData, AllExamQuestionsResponse, ExamFilterOptions } from './types';

const API_BASE = 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

export async function searchQuestions(req: SearchRequest): Promise<SearchResult[]> {
  return request<SearchResult[]>('/search', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function generateQuestion(req: GenerateRequest): Promise<GenerateResponse> {
  return request<GenerateResponse>('/generate', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

export async function getTopics(): Promise<string[]> {
  return request<string[]>('/topics');
}

export async function getStats(): Promise<Stats> {
  return request<Stats>('/stats');
}

export async function healthCheck(): Promise<{ status: string; documents: number }> {
  return request('/health');
}

// ── Practice API ────────────────────────────────────────────────────────────

export async function getAIQuestions(params: {
  topic?: string;
  question_type?: string;
  difficulty?: string;
  page?: number;
  page_size?: number;
}): Promise<AIQuestionsResponse> {
  const searchParams = new URLSearchParams();
  if (params.topic) searchParams.set('topic', params.topic);
  if (params.question_type) searchParams.set('question_type', params.question_type);
  if (params.difficulty) searchParams.set('difficulty', params.difficulty);
  if (params.page) searchParams.set('page', String(params.page));
  if (params.page_size) searchParams.set('page_size', String(params.page_size));
  const qs = searchParams.toString();
  return request<AIQuestionsResponse>(`/practice/ai-questions${qs ? '?' + qs : ''}`);
}

export async function getAIStats(): Promise<AIStats> {
  return request<AIStats>('/practice/ai-stats');
}

export async function getExams(): Promise<ExamSummary[]> {
  return request<ExamSummary[]>('/practice/exams');
}

export async function getExam(filename: string): Promise<ExamData> {
  return request<ExamData>(`/practice/exam/${filename}`);
}

export async function getExamFilterOptions(): Promise<ExamFilterOptions> {
  return request<ExamFilterOptions>('/practice/exams/filter-options');
}

export async function getAllExamQuestions(params: {
  question_type?: string;
  difficulty?: string;
  year?: string;
  topic?: string;
  filenames?: string[];
  limit?: number;
  shuffle?: boolean;
}): Promise<AllExamQuestionsResponse> {
  const searchParams = new URLSearchParams();
  if (params.question_type) searchParams.set('question_type', params.question_type);
  if (params.difficulty) searchParams.set('difficulty', params.difficulty);
  if (params.year) searchParams.set('year', params.year);
  if (params.topic) searchParams.set('topic', params.topic);
  if (params.filenames && params.filenames.length > 0) searchParams.set('filenames', params.filenames.join(','));
  if (params.limit) searchParams.set('limit', String(params.limit));
  if (params.shuffle) searchParams.set('shuffle', 'true');
  const qs = searchParams.toString();
  return request<AllExamQuestionsResponse>(`/practice/exams/all-questions${qs ? '?' + qs : ''}`);
}
