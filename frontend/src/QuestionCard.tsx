import { useState } from 'react';
import { CheckCircle, Eye, EyeOff, FileText } from 'lucide-react';
import type { SearchResult, QuestionJSON } from './types';
import { FormattedText } from './FormattedText';

interface Props {
  result: SearchResult;
}

const difficultyColor: Record<string, string> = {
  Easy: '#22c55e',
  Medium: '#f59e0b',
  Hard: '#ef4444',
};

export default function QuestionCard({ result }: Props) {
  const [expanded, setExpanded] = useState(false);

  let parsed: QuestionJSON | null = null;
  try {
    parsed = JSON.parse(result.full_json);
  } catch {
    // ignore
  }

  return (
    <div className="question-card">
      <div className="card-header">
        <div className="card-meta">
          <span className="badge type-badge">{result.type}</span>
          <span
            className="badge diff-badge"
            style={{ backgroundColor: difficultyColor[result.difficulty] || '#6b7280' }}
          >
            {result.difficulty}
          </span>
          <span className="badge year-badge">{result.year}</span>
          {result.has_solution && (
            <span className="badge solution-badge" title="Has solution">
              <CheckCircle size={14} /> Solution
            </span>
          )}
        </div>
        <span className="source-label">
          <FileText size={14} /> {result.source_file} — Q{result.question_id}
        </span>
      </div>

      {/* Topics */}
      {result.topics && (
        <div className="card-topics">
          {result.topics.split(',').map((t) => (
            <span key={t} className="topic-mini">{t.trim()}</span>
          ))}
        </div>
      )}

      {/* Similarity */}
      <div className="similarity">
        Similarity: {((1 - result.distance) * 100).toFixed(1)}%
      </div>

      {/* Question text */}
      {parsed && (
        <div className="card-body" dir="auto">
          <p className="question-text">{parsed.content.text}</p>

          {parsed.content.code_snippet && (
            <pre className="code-block"><code>{parsed.content.code_snippet}</code></pre>
          )}

          {parsed.content.options && (
            <ul className="options-list">
              {parsed.content.options.map((opt, i) => (
                <li key={i} dir="auto">{opt}</li>
              ))}
            </ul>
          )}

          {/* Sub-questions */}
          {parsed.sub_questions && parsed.sub_questions.length > 0 && (
            <div className="sub-questions">
              <strong>Sub-questions:</strong>
              {parsed.sub_questions.map((sq, i) => (
                <div key={i} className="sub-question" dir="auto">
                  <p>{sq.text}</p>
                  {sq.code_snippet && (
                    <pre className="code-block"><code>{sq.code_snippet}</code></pre>
                  )}
                  {sq.options && (
                    <ul className="options-list">
                      {sq.options.map((o, j) => <li key={j} dir="auto">{o}</li>)}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Solution toggle */}
          {parsed.solution && parsed.solution.is_present_in_file && (
            <>
              <button className="solution-toggle" onClick={() => setExpanded(!expanded)}>
                {expanded ? <EyeOff size={16} /> : <Eye size={16} />}
                {expanded ? 'Hide Solution' : 'Show Solution'}
              </button>
              {expanded && (
                <div className="solution-box">
                  {parsed.solution.correct_option && (
                    <div className="solution-field">
                      <span className="solution-label">Answer</span>
                      <div className="solution-value" dir="rtl">{parsed.solution.correct_option}</div>
                    </div>
                  )}
                  {parsed.solution.explanation && (
                    <div className="solution-field">
                      <span className="solution-label">Explanation</span>
                      <FormattedText text={parsed.solution.explanation} className="solution-value" />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
