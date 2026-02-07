import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { BookOpen, Brain, FileText, Filter, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Shuffle, ArrowLeft, Layers, Hash, ListChecks } from 'lucide-react';
import { getAIQuestions, getAIStats, getExams, getExam, getAllExamQuestions, getExamFilterOptions } from './api';
import type { AIQuestionItem, AIStats, ExamSummary, ExamData, QuestionJSON, ExamQuestion, AllExamQuestionsResponse, ExamFilterOptions } from './types';
import PracticeCard from './PracticeCard';

type PracticeTab = 'ai' | 'exams';
type ExamMode = 'browse' | 'single' | 'mix';

export default function PracticePage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Tab
  const [tab, setTab] = useState<PracticeTab>(
    (searchParams.get('tab') as PracticeTab) || 'ai'
  );

  // AI Questions state
  const [aiQuestions, setAiQuestions] = useState<AIQuestionItem[]>([]);
  const [aiStats, setAiStats] = useState<AIStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [filterTopic, setFilterTopic] = useState('');
  const [filterType, setFilterType] = useState('');
  const [filterDifficulty, setFilterDifficulty] = useState('');

  // Exams state
  const [exams, setExams] = useState<ExamSummary[]>([]);
  const [selectedExam, setSelectedExam] = useState<ExamData | null>(null);
  const [selectedExamName, setSelectedExamName] = useState('');
  const [examsLoading, setExamsLoading] = useState(false);
  const [examMode, setExamMode] = useState<ExamMode>('browse');

  // Mix All Exams state
  const [mixQuestions, setMixQuestions] = useState<ExamQuestion[]>([]);
  const [mixStats, setMixStats] = useState<AllExamQuestionsResponse['stats'] | null>(null);
  const [mixLoading, setMixLoading] = useState(false);
  const [examFilterType, setExamFilterType] = useState('');
  const [examFilterDifficulty, setExamFilterDifficulty] = useState('');
  const [examFilterYear, setExamFilterYear] = useState('');
  const [examFilterTopic, setExamFilterTopic] = useState('');
  const [examLimit, setExamLimit] = useState<number>(50);
  const [showExamFilters, setShowExamFilters] = useState(false);
  const [selectedExamFiles, setSelectedExamFiles] = useState<string[]>([]);
  const [examShowSelectExams, setExamShowSelectExams] = useState(false);
  const [examFilterOptions, setExamFilterOptions] = useState<ExamFilterOptions | null>(null);

  // Shuffle mode
  const [shuffled, setShuffled] = useState(false);

  // Load AI stats and exam data on mount
  useEffect(() => {
    getAIStats().then(setAiStats).catch(() => {});
    getExams().then(setExams).catch(() => {});
    getExamFilterOptions().then(setExamFilterOptions).catch(() => {});
  }, []);

  // Load AI questions
  const loadAIQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getAIQuestions({
        topic: filterTopic || undefined,
        question_type: filterType || undefined,
        difficulty: filterDifficulty || undefined,
        page,
        page_size: 20,
      });
      setAiQuestions(res.questions);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filterTopic, filterType, filterDifficulty, page]);

  useEffect(() => {
    if (tab === 'ai') {
      loadAIQuestions();
    }
  }, [tab, loadAIQuestions]);

  // Load exam
  const loadExam = async (filename: string) => {
    setExamsLoading(true);
    try {
      const data = await getExam(filename);
      setSelectedExam(data);
      setSelectedExamName(filename);
    } catch {
      // ignore
    } finally {
      setExamsLoading(false);
    }
  };

  const handleTabChange = (newTab: PracticeTab) => {
    setTab(newTab);
    setSearchParams({ tab: newTab });
  };

  const handleFilter = () => {
    setPage(1);
    loadAIQuestions();
  };

  // Load mixed questions from all/selected exams
  const loadMixedQuestions = useCallback(async () => {
    setMixLoading(true);
    try {
      const res = await getAllExamQuestions({
        question_type: examFilterType || undefined,
        difficulty: examFilterDifficulty || undefined,
        year: examFilterYear || undefined,
        topic: examFilterTopic || undefined,
        filenames: selectedExamFiles.length > 0 ? selectedExamFiles : undefined,
        limit: examLimit,
        shuffle: true,
      });
      setMixQuestions(res.questions);
      setMixStats(res.stats);
    } catch {
      // ignore
    } finally {
      setMixLoading(false);
    }
  }, [examFilterType, examFilterDifficulty, examFilterYear, examFilterTopic, selectedExamFiles, examLimit]);

  const toggleExamFileSelection = (filename: string) => {
    setSelectedExamFiles(prev =>
      prev.includes(filename)
        ? prev.filter(f => f !== filename)
        : [...prev, filename]
    );
  };

  const getDisplayQuestions = (): QuestionJSON[] => {
    let questions: QuestionJSON[];
    if (tab === 'ai') {
      questions = aiQuestions.map(q => q.question);
    } else if (examMode === 'mix') {
      questions = mixQuestions;
    } else if (selectedExam) {
      questions = selectedExam.questions;
    } else {
      return [];
    }
    if (shuffled) {
      return [...questions].sort(() => Math.random() - 0.5);
    }
    return questions;
  };

  const displayQuestions = getDisplayQuestions();

  // Extract unique years from exams for filter dropdown
  const examYears = [...new Set(exams.map(e => e.year).filter(Boolean))].sort();

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <BookOpen size={28} />
            <h1>ragOS</h1>
            <span className="subtitle">Practice Mode</span>
          </div>
          <Link to="/" className="nav-link">
            <ArrowLeft size={18} />
            Back to Search
          </Link>
        </div>
      </header>

      <main className="main">
        {/* Practice Tabs */}
        <div className="tabs">
          <button
            className={`tab ${tab === 'ai' ? 'active' : ''}`}
            onClick={() => handleTabChange('ai')}
          >
            <Brain size={18} />
            AI Generated ({aiStats?.total ?? '...'})
          </button>
          <button
            className={`tab ${tab === 'exams' ? 'active' : ''}`}
            onClick={() => handleTabChange('exams')}
          >
            <FileText size={18} />
            Past Exams ({exams.length})
          </button>
        </div>

        {/* ── AI Generated Tab ── */}
        {tab === 'ai' && (
          <>
            {/* Stats summary */}
            {aiStats && (
              <div className="practice-stats">
                <div className="stat-item">
                  <span className="stat-value">{aiStats.total}</span>
                  <span className="stat-label">Total Questions</span>
                </div>
                {Object.entries(aiStats.types).map(([type, count]) => (
                  <div key={type} className="stat-item clickable" onClick={() => { setFilterType(type); setPage(1); }}>
                    <span className="stat-value">{count}</span>
                    <span className="stat-label">{type}</span>
                  </div>
                ))}
                {Object.entries(aiStats.difficulties).map(([diff, count]) => (
                  <div key={diff} className="stat-item clickable" onClick={() => { setFilterDifficulty(diff); setPage(1); }}>
                    <span className="stat-value">{count}</span>
                    <span className="stat-label">{diff}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Filters */}
            <div className="practice-toolbar">
              <button
                type="button"
                className="filter-toggle"
                onClick={() => setShowFilters(!showFilters)}
              >
                <Filter size={16} />
                Filters
                {showFilters ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>

              <button
                className={`shuffle-btn ${shuffled ? 'active' : ''}`}
                onClick={() => setShuffled(!shuffled)}
              >
                <Shuffle size={16} />
                Shuffle
              </button>

              {(filterTopic || filterType || filterDifficulty) && (
                <button className="clear-filters-btn" onClick={() => {
                  setFilterTopic('');
                  setFilterType('');
                  setFilterDifficulty('');
                  setPage(1);
                }}>
                  Clear Filters
                </button>
              )}
            </div>

            {showFilters && (
              <div className="filters">
                <div className="filter-group">
                  <label>Topic</label>
                  <select value={filterTopic} onChange={(e) => setFilterTopic(e.target.value)}>
                    <option value="">All Topics</option>
                    {aiStats && Object.keys(aiStats.topics).map(t => (
                      <option key={t} value={t}>{t} ({aiStats.topics[t]})</option>
                    ))}
                  </select>
                </div>
                <div className="filter-group">
                  <label>Type</label>
                  <select value={filterType} onChange={(e) => setFilterType(e.target.value)}>
                    <option value="">All Types</option>
                    <option value="MultipleChoice">Multiple Choice</option>
                    <option value="Open">Open</option>
                    <option value="CodeAnalysis">Code Analysis</option>
                  </select>
                </div>
                <div className="filter-group">
                  <label>Difficulty</label>
                  <select value={filterDifficulty} onChange={(e) => setFilterDifficulty(e.target.value)}>
                    <option value="">All</option>
                    <option value="Easy">Easy</option>
                    <option value="Medium">Medium</option>
                    <option value="Hard">Hard</option>
                  </select>
                </div>
                <button className="filter-apply-btn" onClick={handleFilter}>Apply</button>
              </div>
            )}

            {/* Questions list */}
            {loading ? (
              <div className="loading">Loading questions...</div>
            ) : (
              <>
                <div className="results-header">
                  <span>{total} questions found</span>
                  <span>Page {page} of {totalPages}</span>
                </div>
                <div className="results-grid">
                  {displayQuestions.map((q, i) => (
                    <PracticeCard
                      key={`${page}-${i}`}
                      question={q}
                      index={(page - 1) * 20 + i + 1}
                      source="AI Generated"
                    />
                  ))}
                </div>

                {/* Pagination */}
                {totalPages > 1 && (
                  <div className="pagination">
                    <button
                      disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}
                    >
                      <ChevronLeft size={18} />
                      Previous
                    </button>
                    <div className="page-numbers">
                      {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
                        let pageNum: number;
                        if (totalPages <= 7) {
                          pageNum = i + 1;
                        } else if (page <= 4) {
                          pageNum = i + 1;
                        } else if (page >= totalPages - 3) {
                          pageNum = totalPages - 6 + i;
                        } else {
                          pageNum = page - 3 + i;
                        }
                        return (
                          <button
                            key={pageNum}
                            className={`page-btn ${pageNum === page ? 'active' : ''}`}
                            onClick={() => setPage(pageNum)}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                    </div>
                    <button
                      disabled={page >= totalPages}
                      onClick={() => setPage(p => p + 1)}
                    >
                      Next
                      <ChevronRight size={18} />
                    </button>
                  </div>
                )}
              </>
            )}
          </>
        )}

        {/* ── Exams Tab ── */}
        {tab === 'exams' && (
          <>
            {/* Mode selector bar */}
            {examMode !== 'single' && (
              <div className="exam-mode-bar">
                <button
                  className={`exam-mode-btn ${examMode === 'browse' ? 'active' : ''}`}
                  onClick={() => setExamMode('browse')}
                >
                  <FileText size={16} />
                  Browse Exams
                </button>
                <button
                  className={`exam-mode-btn ${examMode === 'mix' ? 'active' : ''}`}
                  onClick={() => { setExamMode('mix'); if (mixQuestions.length === 0) loadMixedQuestions(); }}
                >
                  <Layers size={16} />
                  Mix &amp; Shuffle
                </button>
              </div>
            )}

            {/* ─── Browse Mode ─── */}
            {examMode === 'browse' && (
              <>
                {/* Select exams for mix */}
                <div className="browse-toolbar">
                  <button
                    className={`toggle-select-btn ${examShowSelectExams ? 'active' : ''}`}
                    onClick={() => setExamShowSelectExams(!examShowSelectExams)}
                  >
                    <ListChecks size={16} />
                    {examShowSelectExams ? 'Done Selecting' : 'Select for Mix'}
                  </button>
                  {selectedExamFiles.length > 0 && (
                    <>
                      <span className="selected-count">{selectedExamFiles.length} selected</span>
                      <button
                        className="mix-selected-btn"
                        onClick={() => { setExamMode('mix'); loadMixedQuestions(); }}
                      >
                        <Shuffle size={16} />
                        Mix Selected ({selectedExamFiles.length})
                      </button>
                      <button
                        className="clear-filters-btn"
                        onClick={() => setSelectedExamFiles([])}
                      >
                        Clear
                      </button>
                    </>
                  )}
                </div>

                <div className="exams-grid">
                  {exams.map((exam) => (
                    <div
                      key={exam.filename}
                      className={`exam-card ${examShowSelectExams ? 'selectable' : ''} ${selectedExamFiles.includes(exam.filename) ? 'selected' : ''}`}
                      onClick={() => {
                        if (examShowSelectExams) {
                          toggleExamFileSelection(exam.filename);
                        } else {
                          loadExam(exam.filename);
                          setExamMode('single');
                        }
                      }}
                    >
                      {examShowSelectExams && (
                        <div className="exam-checkbox">
                          <input
                            type="checkbox"
                            checked={selectedExamFiles.includes(exam.filename)}
                            onChange={() => toggleExamFileSelection(exam.filename)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </div>
                      )}
                      <div className="exam-card-header">
                        <FileText size={24} />
                        <h3>{exam.filename.replace('.json', '')}</h3>
                      </div>
                      <div className="exam-card-meta">
                        {exam.year && <span>{exam.year}</span>}
                        {exam.semester && <span>{exam.semester}</span>}
                        {exam.moed && <span>{exam.moed}</span>}
                      </div>
                      {exam.exam_date && (
                        <div className="exam-date">{exam.exam_date}</div>
                      )}
                      <div className="exam-count">
                        {exam.question_count} questions
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* ─── Single Exam Mode ─── */}
            {examMode === 'single' && selectedExam && (
              <>
                <div className="exam-header-bar">
                  <button className="back-btn" onClick={() => { setSelectedExam(null); setSelectedExamName(''); setExamMode('browse'); }}>
                    <ArrowLeft size={18} />
                    Back to Exams
                  </button>
                  <h2>
                    {selectedExamName.replace('.json', '')}
                    {selectedExam.metadata?.year && ` — ${selectedExam.metadata.year}`}
                    {selectedExam.metadata?.moed && ` ${selectedExam.metadata.moed}`}
                  </h2>
                  <button
                    className={`shuffle-btn ${shuffled ? 'active' : ''}`}
                    onClick={() => setShuffled(!shuffled)}
                  >
                    <Shuffle size={16} />
                    Shuffle
                  </button>
                </div>

                {examsLoading ? (
                  <div className="loading">Loading exam...</div>
                ) : (
                  <div className="results-grid">
                    {displayQuestions.map((q, i) => (
                      <PracticeCard
                        key={i}
                        question={q}
                        index={i + 1}
                        source={selectedExamName.replace('.json', '')}
                      />
                    ))}
                  </div>
                )}
              </>
            )}

            {/* ─── Mix Mode ─── */}
            {examMode === 'mix' && (
              <>
                <div className="exam-header-bar">
                  <button className="back-btn" onClick={() => { setExamMode('browse'); setMixQuestions([]); setMixStats(null); }}>
                    <ArrowLeft size={18} />
                    Back to Browse
                  </button>
                  <h2>
                    <Layers size={20} />
                    Mixed Questions
                    {selectedExamFiles.length > 0
                      ? ` (${selectedExamFiles.length} exams)`
                      : ' (All Exams)'}
                  </h2>
                  <button
                    className={`filter-toggle ${showExamFilters ? 'active' : ''}`}
                    onClick={() => setShowExamFilters(!showExamFilters)}
                  >
                    <Filter size={16} />
                    Filters
                    {showExamFilters ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </button>
                </div>

                {/* Mix Filters */}
                {showExamFilters && (
                  <div className="filters mix-filters">
                    <div className="filter-group">
                      <label>Year</label>
                      <select value={examFilterYear} onChange={(e) => setExamFilterYear(e.target.value)}>
                        <option value="">All Years</option>
                        {examYears.map(y => (
                          <option key={y} value={y}>{y}</option>
                        ))}
                      </select>
                    </div>
                    <div className="filter-group">
                      <label>Type</label>
                      <select value={examFilterType} onChange={(e) => setExamFilterType(e.target.value)}>
                        <option value="">All Types</option>
                        <option value="MultipleChoice">Multiple Choice</option>
                        <option value="Open">Open</option>
                        <option value="CodeAnalysis">Code Analysis</option>
                      </select>
                    </div>
                    <div className="filter-group">
                      <label>Difficulty</label>
                      <select value={examFilterDifficulty} onChange={(e) => setExamFilterDifficulty(e.target.value)}>
                        <option value="">All</option>
                        <option value="Easy">Easy</option>
                        <option value="Medium">Medium</option>
                        <option value="Hard">Hard</option>
                      </select>
                    </div>
                    <div className="filter-group">
                      <label>Topic</label>
                      <select value={examFilterTopic} onChange={(e) => setExamFilterTopic(e.target.value)}>
                        <option value="">All Topics</option>
                        {examFilterOptions && Object.entries(examFilterOptions.topics).map(([t, count]) => (
                          <option key={t} value={t}>{t} ({count})</option>
                        ))}
                      </select>
                    </div>
                    <div className="filter-group">
                      <label>
                        <Hash size={14} />
                        Limit ({examLimit})
                      </label>
                      <input
                        type="range"
                        min={5}
                        max={500}
                        step={5}
                        value={examLimit}
                        onChange={(e) => setExamLimit(Number(e.target.value))}
                        className="limit-slider"
                      />
                    </div>
                    <button className="filter-apply-btn" onClick={loadMixedQuestions}>
                      <Shuffle size={16} />
                      Shuffle &amp; Apply
                    </button>
                    {(examFilterType || examFilterDifficulty || examFilterYear || examFilterTopic) && (
                      <button className="clear-filters-btn" onClick={() => {
                        setExamFilterType('');
                        setExamFilterDifficulty('');
                        setExamFilterYear('');
                        setExamFilterTopic('');
                      }}>
                        Clear Filters
                      </button>
                    )}
                  </div>
                )}

                {/* Mix Stats */}
                {mixStats && (
                  <div className="practice-stats mix-stats">
                    <div className="stat-item">
                      <span className="stat-value">{mixStats.total_available}</span>
                      <span className="stat-label">Available</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-value">{mixStats.returned}</span>
                      <span className="stat-label">Showing</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-value">{mixStats.exams_count}</span>
                      <span className="stat-label">Exams</span>
                    </div>
                    {mixStats.types && Object.entries(mixStats.types).map(([type, count]) => (
                      <div key={type} className="stat-item clickable" onClick={() => { setExamFilterType(type); }}>
                        <span className="stat-value">{count}</span>
                        <span className="stat-label">{type}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Re-shuffle button */}
                <div className="mix-toolbar">
                  <button className="shuffle-btn active" onClick={loadMixedQuestions}>
                    <Shuffle size={16} />
                    Re-shuffle
                  </button>
                  <span className="mix-count">{mixQuestions.length} questions loaded</span>
                </div>

                {/* Mixed questions list */}
                {mixLoading ? (
                  <div className="loading">Loading mixed questions...</div>
                ) : (
                  <div className="results-grid">
                    {displayQuestions.map((q, i) => {
                      const eq = q as ExamQuestion;
                      return (
                        <PracticeCard
                          key={`mix-${i}`}
                          question={q}
                          index={i + 1}
                          source={eq._source_exam ? eq._source_exam.replace('.json', '') : 'Exam'}
                        />
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}
