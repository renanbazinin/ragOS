import { useState } from 'react';
import { Eye, EyeOff, CheckCircle, XCircle } from 'lucide-react';
import type { QuestionJSON } from './types';
import { FormattedText } from './FormattedText';

interface Props {
  question: QuestionJSON;
  index: number;
  source?: string;
}

const difficultyColor: Record<string, string> = {
  Easy: '#22c55e',
  Medium: '#f59e0b',
  Hard: '#ef4444',
};

export default function PracticeCard({ question, index, source }: Props) {
  const [showSolution, setShowSolution] = useState(false);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const difficulty = question.difficulty_estimation || 'Unknown';
  const content = question.content || { text: '', code_snippet: null, options: null };
  const isMultipleChoice = question.type === 'MultipleChoice' && content.options;

  const handleSubmit = () => {
    setSubmitted(true);
    setShowSolution(true);
  };

  const isCorrect = () => {
    if (!question.solution?.correct_option || selectedOption === null) return false;
    const correctLetter = question.solution.correct_option.trim();
    const optionLetter = question.content.options?.[selectedOption]?.trim().charAt(0);
    return correctLetter === optionLetter;
  };

  return (
    <div className={`practice-card ${submitted ? (isMultipleChoice && isCorrect() ? 'correct' : submitted && isMultipleChoice ? 'incorrect' : '') : ''}`}>
      <div className="practice-card-header">
        <span className="practice-index">#{index}</span>
        <div className="card-meta">
          <span className="badge type-badge">{question.type}</span>
          <span
            className="badge diff-badge"
            style={{ backgroundColor: difficultyColor[difficulty] || '#6b7280' }}
          >
            {difficulty}
          </span>
          {source && <span className="badge source-badge">{source}</span>}
        </div>
      </div>

      {question.topic && Array.isArray(question.topic) && question.topic.length > 0 && (
        <div className="card-topics">
          {question.topic.map((t) => (
            <span key={t} className="topic-mini">{t}</span>
          ))}
        </div>
      )}

      <div className="card-body" dir="auto">
        <p className="question-text">{content.text}</p>

        {content.code_snippet && (
          <pre className="code-block"><code>{content.code_snippet}</code></pre>
        )}

        {/* Multiple choice with interactive selection */}
        {isMultipleChoice && (
          <ul className="options-list interactive">
            {content.options!.map((opt, i) => {
              let optionClass = 'option-item';
              if (submitted && question.solution?.correct_option) {
                const optLetter = opt.trim().charAt(0);
                if (optLetter === question.solution.correct_option.trim()) {
                  optionClass += ' option-correct';
                } else if (i === selectedOption) {
                  optionClass += ' option-wrong';
                }
              } else if (i === selectedOption) {
                optionClass += ' option-selected';
              }
              return (
                <li
                  key={i}
                  dir="auto"
                  className={optionClass}
                  onClick={() => !submitted && setSelectedOption(i)}
                >
                  {submitted && question.solution?.correct_option && (
                    <span className="option-icon">
                      {opt.trim().charAt(0) === question.solution.correct_option.trim()
                        ? <CheckCircle size={16} />
                        : i === selectedOption
                          ? <XCircle size={16} />
                          : null
                      }
                    </span>
                  )}
                  {opt}
                </li>
              );
            })}
          </ul>
        )}

        {/* Non-multiple-choice: just show options if any */}
        {!isMultipleChoice && content.options && (
          <ul className="options-list">
            {content.options.map((opt, i) => (
              <li key={i} dir="auto">{opt}</li>
            ))}
          </ul>
        )}

        {/* Sub-questions */}
        {question.sub_questions && question.sub_questions.length > 0 && (
          <div className="sub-questions">
            <strong>Sub-questions:</strong>
            {question.sub_questions.map((sq, i) => (
              <div key={i} className="sub-question" dir="auto">
                <p>{typeof sq === 'object' && 'text' in sq ? sq.text : String(sq)}</p>
                {typeof sq === 'object' && sq.code_snippet && (
                  <pre className="code-block"><code>{sq.code_snippet}</code></pre>
                )}
                {typeof sq === 'object' && sq.options && (
                  <ul className="options-list">
                    {sq.options.map((o, j) => <li key={j} dir="auto">{o}</li>)}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Action buttons */}
        <div className="practice-actions">
          {isMultipleChoice && !submitted && (
            <button
              className="submit-btn"
              onClick={handleSubmit}
              disabled={selectedOption === null}
            >
              Check Answer
            </button>
          )}

          {question.solution && (question.solution.is_present_in_file || question.solution.explanation) && (
            <button className="solution-toggle" onClick={() => setShowSolution(!showSolution)}>
              {showSolution ? <EyeOff size={16} /> : <Eye size={16} />}
              {showSolution ? 'Hide Solution' : 'Show Solution'}
            </button>
          )}
        </div>

        {/* Solution */}
        {showSolution && question.solution && (
          <div className="solution-box">
            {question.solution.correct_option && (
              <div className="solution-field">
                <span className="solution-label">Answer</span>
                <div className="solution-value" dir="rtl">{question.solution.correct_option}</div>
              </div>
            )}
            {question.solution.explanation && (
              <div className="solution-field">
                <span className="solution-label">Explanation</span>
                <FormattedText text={question.solution.explanation} className="solution-value" />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
