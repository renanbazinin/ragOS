import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  BookOpen, Filter, ChevronDown, ChevronUp, ChevronLeft, ChevronRight,
  Shuffle, ArrowLeft, Cpu, Layers, HardDrive, FolderOpen
} from 'lucide-react';
import { getTheoryQuestions, getTheoryStats } from './localData';
import type { TheoryQuestionItem, TheoryStats } from './types';
import PracticeCard from './PracticeCard';

const SUBJECTS = ['Virtualization', 'Concurrency', 'File Systems', 'Disks'] as const;

const subjectIcons: Record<string, React.ReactNode> = {
  'Virtualization': <Cpu size={20} />,
  'Concurrency': <Layers size={20} />,
  'File Systems': <FolderOpen size={20} />,
  'Disks': <HardDrive size={20} />,
};

const subjectColors: Record<string, string> = {
  'Virtualization': '#6366f1',
  'Concurrency': '#f59e0b',
  'File Systems': '#22c55e',
  'Disks': '#ef4444',
};

export default function TheoryPage() {
  // Data
  const [questions, setQuestions] = useState<TheoryQuestionItem[]>([]);
  const [stats, setStats] = useState<TheoryStats | null>(null);
  const [loading, setLoading] = useState(false);

  // Pagination
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [filterSubject, setFilterSubject] = useState('');
  const [filterDifficulty, setFilterDifficulty] = useState('');
  const [filterTopics, setFilterTopics] = useState<string[]>([]);
  const [shuffled, setShuffled] = useState(false);

  // Load stats on mount
  useEffect(() => {
    getTheoryStats().then(setStats).catch(() => {});
  }, []);

  // Load questions
  const loadQuestions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await getTheoryQuestions({
        subject: filterSubject || undefined,
        topics: filterTopics.length > 0 ? filterTopics : undefined,
        difficulty: filterDifficulty || undefined,
        page,
        page_size: 20,
        shuffle: shuffled,
      });
      setQuestions(res.questions);
      setTotalPages(res.total_pages);
      setTotal(res.total);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [filterSubject, filterTopics, filterDifficulty, page, shuffled]);

  useEffect(() => {
    loadQuestions();
  }, [loadQuestions]);

  const displayQuestions = questions;

  // Available topics for the selected subject
  const filteredTopicsList = stats
    ? Object.entries(stats.topics).filter(([_topic]) => {
        if (!filterSubject) return true;
        // Show topics that exist in options
        return true;
      })
    : [];

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <img src={`${import.meta.env.BASE_URL}logo.svg`} alt="ragOS" width="32" height="32" style={{ marginRight: '-4px' }} />
            <h1>ragOS</h1>
            <span className="subtitle">Theory Questions</span>
          </div>
          <Link to="/" className="nav-link">
            <ArrowLeft size={18} />
            Home
          </Link>
          <Link to="/practice" className="nav-link">
            <BookOpen size={18} />
            Practice
          </Link>
        </div>
      </header>

      <main className="main">
        {/* Subject Cards */}
        <div className="theory-subjects">
          {SUBJECTS.map(subject => {
            const count = stats?.subjects[subject] ?? 0;
            const isActive = filterSubject === subject;
            return (
              <button
                key={subject}
                className={`subject-card ${isActive ? 'active' : ''}`}
                style={{
                  borderColor: isActive ? subjectColors[subject] : undefined,
                  backgroundColor: isActive ? `${subjectColors[subject]}15` : undefined,
                }}
                onClick={() => {
                  setFilterSubject(isActive ? '' : subject);
                  setFilterTopics([]);
                  setPage(1);
                }}
              >
                <div className="subject-icon" style={{ color: subjectColors[subject] }}>
                  {subjectIcons[subject]}
                </div>
                <div className="subject-info">
                  <span className="subject-name">{subject}</span>
                  <span className="subject-count">{count} questions</span>
                </div>
              </button>
            );
          })}
        </div>

        {/* Stats bar */}
        {stats && (
          <div className="practice-stats">
            <div className="stat-item">
              <span className="stat-value">{stats.total}</span>
              <span className="stat-label">Total Theory</span>
            </div>
            {Object.entries(stats.difficulties).map(([diff, count]) => (
              <div
                key={diff}
                className={`stat-item clickable ${filterDifficulty === diff ? 'stat-active' : ''}`}
                onClick={() => { setFilterDifficulty(filterDifficulty === diff ? '' : diff); setPage(1); }}
              >
                <span className="stat-value">{count}</span>
                <span className="stat-label">{diff}</span>
              </div>
            ))}
          </div>
        )}

        {/* Toolbar */}
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

          {(filterSubject || filterDifficulty || filterTopics.length > 0) && (
            <button className="clear-filters-btn" onClick={() => {
              setFilterSubject('');
              setFilterDifficulty('');
              setFilterTopics([]);
              setPage(1);
            }}>
              Clear Filters
            </button>
          )}
        </div>

        {/* Expanded Filters */}
        {showFilters && (
          <div className="filters">
            <div className="filter-group">
              <label>Subject</label>
              <select value={filterSubject} onChange={(e) => { setFilterSubject(e.target.value); setFilterTopics([]); setPage(1); }}>
                <option value="">All Subjects</option>
                {SUBJECTS.map(s => (
                  <option key={s} value={s}>{s} ({stats?.subjects[s] ?? 0})</option>
                ))}
              </select>
            </div>
            <div className="filter-group">
              <label>Difficulty</label>
              <select value={filterDifficulty} onChange={(e) => { setFilterDifficulty(e.target.value); setPage(1); }}>
                <option value="">All</option>
                <option value="Easy">Easy</option>
                <option value="Medium">Medium</option>
                <option value="Hard">Hard</option>
              </select>
            </div>
            <div className="filter-group">
              <label>Topics {filterTopics.length > 0 && `(${filterTopics.length})`}</label>
              <div className="multi-select-dropdown">
                <div className="multi-select-header" onClick={(e) => {
                  const el = (e.currentTarget.nextElementSibling as HTMLElement);
                  el.style.display = el.style.display === 'block' ? 'none' : 'block';
                }}>
                  {filterTopics.length === 0 ? 'All Topics' : filterTopics.join(', ')}
                  <ChevronDown size={14} />
                </div>
                <div className="multi-select-options" style={{ display: 'none' }}>
                  {filterTopics.length > 0 && (
                    <div className="multi-select-item clear-item" onClick={() => setFilterTopics([])}>
                      ✕ Clear all
                    </div>
                  )}
                  {filteredTopicsList.map(([t, count]) => (
                    <label key={t} className="multi-select-item">
                      <input
                        type="checkbox"
                        checked={filterTopics.includes(t)}
                        onChange={() => {
                          setFilterTopics(prev =>
                            prev.includes(t) ? prev.filter(x => x !== t) : [...prev, t]
                          );
                        }}
                      />
                      {t} ({count})
                    </label>
                  ))}
                </div>
              </div>
            </div>
            <button className="filter-apply-btn" onClick={() => { setPage(1); loadQuestions(); }}>Apply</button>
          </div>
        )}

        {/* Questions list */}
        {loading ? (
          <div className="loading">Loading theory questions...</div>
        ) : (
          <>
            <div className="results-header">
              <span>{total} questions found</span>
              <span>Page {page} of {totalPages}</span>
            </div>
            <div className="results-grid">
              {displayQuestions.map((q, i) => (
                <PracticeCard
                  key={`theory-${page}-${i}`}
                  question={q as any}
                  index={(page - 1) * 20 + i + 1}
                  source={q._subject || q.subject || 'Theory'}
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
      </main>
    </div>
  );
}
