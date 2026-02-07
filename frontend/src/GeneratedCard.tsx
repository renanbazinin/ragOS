import { useState } from 'react';
import { Sparkles, Eye, EyeOff, Copy, Check, Save } from 'lucide-react';
import type { QuestionJSON } from './types';
import { FormattedText } from './FormattedText';

interface Props {
  question: QuestionJSON;
  onSave?: (q: QuestionJSON) => void;
}

export default function GeneratedCard({ question, onSave }: Props) {
  const [showSolution, setShowSolution] = useState(false);
  const [copied, setCopied] = useState(false);
  const [saved, setSaved] = useState(false);

  const copyJSON = async () => {
    await navigator.clipboard.writeText(JSON.stringify(question, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="generated-card">
      <div className="card-header">
        <div className="card-meta">
          <span className="badge type-badge">{question.type}</span>
          <span className="badge diff-badge">{question.difficulty_estimation}</span>
          <span className="badge generated-badge">
            <Sparkles size={14} /> AI Generated
          </span>
        </div>
        <button className="copy-btn" onClick={copyJSON} title="Copy JSON">
          {copied ? <Check size={16} /> : <Copy size={16} />}
          {copied ? 'Copied!' : 'Copy JSON'}
        </button>
        {onSave && (
          <button
            className={`save-btn ${saved ? 'saved' : ''}`}
            onClick={() => { onSave(question); setSaved(true); }}
            disabled={saved}
            title="Save to collection"
          >
            {saved ? <Check size={16} /> : <Save size={16} />}
            {saved ? 'Saved!' : 'Save'}
          </button>
        )}
      </div>

      {question.topic && question.topic.length > 0 && (
        <div className="card-topics">
          {question.topic.map((t) => (
            <span key={t} className="topic-mini">{t}</span>
          ))}
        </div>
      )}

      <div className="card-body" dir="auto">
        <p className="question-text">{question.content.text}</p>

        {question.content.code_snippet && (
          <pre className="code-block"><code>{question.content.code_snippet}</code></pre>
        )}

        {question.content.options && (
          <ul className="options-list">
            {question.content.options.map((opt, i) => (
              <li key={i} dir="auto">{opt}</li>
            ))}
          </ul>
        )}

        {question.sub_questions && question.sub_questions.length > 0 && (
          <div className="sub-questions">
            <strong>Sub-questions:</strong>
            {question.sub_questions.map((sq, i) => (
              <div key={i} className="sub-question" dir="auto">
                <p>{sq.text}</p>
                {sq.code_snippet && (
                  <pre className="code-block"><code>{sq.code_snippet}</code></pre>
                )}
              </div>
            ))}
          </div>
        )}

        {question.solution && (
          <>
            <button className="solution-toggle" onClick={() => setShowSolution(!showSolution)}>
              {showSolution ? <EyeOff size={16} /> : <Eye size={16} />}
              {showSolution ? 'Hide Solution' : 'Show Solution'}
            </button>
            {showSolution && (
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
          </>
        )}
      </div>
    </div>
  );
}
