import { useState } from 'react';
import { Settings, X, FolderOpen, Save, Check, AlertCircle } from 'lucide-react';
import type { QuestionJSON } from './types';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  savedQuestions: QuestionJSON[];
  onClearSaved: () => void;
}

export default function SettingsModal({ isOpen, onClose, savedQuestions, onClearSaved }: Props) {
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [statusMsg, setStatusMsg] = useState('');

  if (!isOpen) return null;

  const exportAllAsJSON = async () => {
    if (savedQuestions.length === 0) {
      setSaveStatus('error');
      setStatusMsg('No saved questions to export.');
      return;
    }

    const data = JSON.stringify(
      {
        exported_at: new Date().toISOString(),
        total: savedQuestions.length,
        questions: savedQuestions,
      },
      null,
      2
    );

    // Try File System Access API first (Chromium browsers)
    if ('showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: `ragos_questions_${Date.now()}.json`,
          types: [
            {
              description: 'JSON File',
              accept: { 'application/json': ['.json'] },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(data);
        await writable.close();
        setSaveStatus('success');
        setStatusMsg(`Saved ${savedQuestions.length} question(s) to file.`);
      } catch (err: any) {
        if (err?.name === 'AbortError') return; // user cancelled
        setSaveStatus('error');
        setStatusMsg('Failed to save: ' + err.message);
      }
    } else {
      // Fallback: download via anchor
      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `ragos_questions_${Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setSaveStatus('success');
      setStatusMsg(`Downloaded ${savedQuestions.length} question(s).`);
    }
  };

  const exportSingleQuestion = async (q: QuestionJSON, index: number) => {
    const data = JSON.stringify(q, null, 2);

    if ('showSaveFilePicker' in window) {
      try {
        const handle = await (window as any).showSaveFilePicker({
          suggestedName: `question_${q.type}_${index + 1}.json`,
          types: [
            {
              description: 'JSON File',
              accept: { 'application/json': ['.json'] },
            },
          ],
        });
        const writable = await handle.createWritable();
        await writable.write(data);
        await writable.close();
      } catch (err: any) {
        if (err?.name !== 'AbortError') {
          setSaveStatus('error');
          setStatusMsg('Failed: ' + err.message);
        }
      }
    } else {
      const blob = new Blob([data], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `question_${q.type}_${index + 1}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2><Settings size={20} /> Settings</h2>
          <button className="modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="modal-body">
          {/* Save section */}
          <div className="settings-section">
            <h3><FolderOpen size={18} /> Saved Questions</h3>
            <p className="settings-desc">
              Generated questions you saved are stored in your browser session.
              Export them to a JSON file on your computer.
            </p>

            <div className="saved-count">
              <span>{savedQuestions.length} question{savedQuestions.length !== 1 ? 's' : ''} saved</span>
            </div>

            {savedQuestions.length > 0 && (
              <div className="saved-list">
                {savedQuestions.map((q, i) => (
                  <div key={i} className="saved-item">
                    <div className="saved-item-info" dir="auto">
                      <span className="badge type-badge">{q.type}</span>
                      <span className="badge diff-badge">{q.difficulty_estimation}</span>
                      <span className="saved-preview">
                        {q.content.text.substring(0, 80)}…
                      </span>
                    </div>
                    <button
                      className="save-single-btn"
                      onClick={() => exportSingleQuestion(q, i)}
                      title="Save this question"
                    >
                      <Save size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="settings-actions">
              <button
                className="btn-primary"
                onClick={exportAllAsJSON}
                disabled={savedQuestions.length === 0}
              >
                <Save size={16} /> Export All to File
              </button>
              <button
                className="btn-danger"
                onClick={() => {
                  onClearSaved();
                  setSaveStatus('success');
                  setStatusMsg('All saved questions cleared.');
                }}
                disabled={savedQuestions.length === 0}
              >
                Clear All
              </button>
            </div>

            {saveStatus !== 'idle' && (
              <div className={`settings-status ${saveStatus}`}>
                {saveStatus === 'success' ? <Check size={16} /> : <AlertCircle size={16} />}
                {statusMsg}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
