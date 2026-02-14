import { useState, useMemo } from 'react';
import { Eye, EyeOff, CheckCircle, XCircle, Shuffle } from 'lucide-react';
import type { QuestionJSON } from './types';
import { FormattedText } from './FormattedText';

interface Props {
  question: QuestionJSON;
  index: number;
  source?: string;
}

const HEBREW_LETTERS = ['א', 'ב', 'ג', 'ד', 'ה', 'ו'];

const difficultyColor: Record<string, string> = {
  Easy: '#22c55e',
  Medium: '#f59e0b',
  Hard: '#ef4444',
};

/** Fisher-Yates shuffle returning a new array of indices */
function shuffleIndices(len: number): number[] {
  const arr = Array.from({ length: len }, (_, i) => i);
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

export default function PracticeCard({ question, index, source }: Props) {
  const [showSolution, setShowSolution] = useState(false);
  const [selectedOption, setSelectedOption] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [answerShuffleKey, setAnswerShuffleKey] = useState(0);

  const difficulty = question.difficulty_estimation || 'Unknown';
  const content = question.content || { text: '', code_snippet: null, options: null };
  const isMultipleChoice = question.type === 'MultipleChoice' && content.options;

  // Compute shuffled order of options (re-shuffles when answerShuffleKey changes)
  const optionOrder = useMemo(() => {
    if (!content.options) return [];
    return answerShuffleKey === 0
      ? content.options.map((_, i) => i) // original order on first render
      : shuffleIndices(content.options.length);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [answerShuffleKey, content.options?.length]);

  // Build display options with re-labeled Hebrew letters
  const displayOptions = useMemo(() => {
    if (!content.options || optionOrder.length === 0) return null;
    return optionOrder.map((origIdx, newIdx) => {
      const origText = content.options![origIdx];
      // Strip existing letter prefix (e.g. "א. ") and re-label
      const stripped = origText.replace(/^[א-ו][.)]\s*/, '');
      return {
        text: `${HEBREW_LETTERS[newIdx]}. ${stripped}`,
        origIdx,
        letter: HEBREW_LETTERS[newIdx],
      };
    });
  }, [content.options, optionOrder]);

  // Find the correct original index from the solution letter
  const correctOrigIdx = useMemo(() => {
    if (!question.solution?.correct_option || !content.options) return -1;
    const correctLetter = question.solution.correct_option.trim().charAt(0);
    return content.options.findIndex(opt => opt.trim().charAt(0) === correctLetter);
  }, [question.solution, content.options]);

  const handleSubmit = () => {
    setSubmitted(true);
    setShowSolution(true);
  };

  const handleShuffleAnswers = () => {
    if (submitted) return;
    setSelectedOption(null);
    setAnswerShuffleKey(k => k + 1);
  };

  const isCorrect = () => {
    if (correctOrigIdx < 0 || selectedOption === null || !displayOptions) return false;
    return displayOptions[selectedOption].origIdx === correctOrigIdx;
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
        <FormattedText text={content.text} className="question-text" />

        {content.code_snippet && (
          <pre className="code-block"><code>{content.code_snippet}</code></pre>
        )}

        {/* Multiple choice with interactive selection */}
        {isMultipleChoice && displayOptions && (
          <ul className="options-list interactive">
            {displayOptions.map((d, i) => {
              let optionClass = 'option-item';
              if (submitted) {
                if (d.origIdx === correctOrigIdx) {
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
                  {submitted && (
                    <span className="option-icon">
                      {d.origIdx === correctOrigIdx
                        ? <CheckCircle size={16} />
                        : i === selectedOption
                          ? <XCircle size={16} />
                          : null
                      }
                    </span>
                  )}
                  {d.text}
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
                <FormattedText text={typeof sq === 'object' && 'text' in sq ? sq.text : String(sq)} />
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
            <>
              <button
                className="submit-btn"
                onClick={handleSubmit}
                disabled={selectedOption === null}
              >
                Check Answer
              </button>
              <button className="shuffle-btn" onClick={handleShuffleAnswers} title="Shuffle answer options">
                <Shuffle size={16} /> Shuffle Answers
              </button>
            </>
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
