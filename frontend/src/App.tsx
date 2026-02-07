import { useState, useEffect, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Search, Sparkles, Filter, ChevronDown, ChevronUp, Settings, Brain } from 'lucide-react';
import { searchQuestions, generateQuestion, getTopics, getStats } from './api';
import type { SearchResult, QuestionJSON, Stats } from './types';
import QuestionCard from './QuestionCard';
import GeneratedCard from './GeneratedCard';
import StatsPanel from './StatsPanel';
import SettingsModal from './SettingsModal';
import './App.css';

function App() {
  // Search state
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [questionType, setQuestionType] = useState<string>('');
  const [difficulty, setDifficulty] = useState<string>('');
  const [year, setYear] = useState<string>('');
  const [nResults, setNResults] = useState(5);

  // Generate state
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<QuestionJSON | null>(null);

  // Metadata
  const [topics, setTopics] = useState<string[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState('');

  // Active tab
  const [tab, setTab] = useState<'search' | 'generate'>('search');

  // Settings
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [savedQuestions, setSavedQuestions] = useState<QuestionJSON[]>(() => {
    try {
      const stored = localStorage.getItem('ragos_saved');
      return stored ? JSON.parse(stored) : [];
    } catch { return []; }
  });

  // Persist saved questions
  useEffect(() => {
    localStorage.setItem('ragos_saved', JSON.stringify(savedQuestions));
  }, [savedQuestions]);

  const handleSaveQuestion = (q: QuestionJSON) => {
    setSavedQuestions((prev) => [...prev, q]);
  };

  useEffect(() => {
    getTopics().then(setTopics).catch(() => {});
    getStats().then(setStats).catch(() => {});
  }, []);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setError('');
    setSearching(true);
    try {
      const res = await searchQuestions({
        query,
        n_results: nResults,
        question_type: questionType || null,
        difficulty: difficulty || null,
        year: year ? parseInt(year) : null,
      });
      setResults(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setSearching(false);
    }
  };

  const handleGenerate = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setError('');
    setGenerating(true);
    setGenerated(null);
    try {
      const res = await generateQuestion({
        query,
        question_type: questionType || null,
        difficulty: difficulty || null,
      });
      if ('raw' in res.generated_question) {
        setError('Generated output was not valid JSON: ' + (res.generated_question as { raw: string }).raw);
      } else {
        setGenerated(res.generated_question as QuestionJSON);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <img src={`${import.meta.env.BASE_URL}logo.svg`} alt="ragOS" width="32" height="32" style={{ marginRight: '-4px' }} />
            <h1>ragOS</h1>
            <span className="subtitle">OS Exam Question Generator</span>
          </div>
          {stats && (
            <div className="header-stats">
              <span>{stats.total_questions} questions indexed</span>
            </div>
          )}
          <button className="settings-btn" onClick={() => setSettingsOpen(true)} title="Settings">
            <Settings size={22} />
            {savedQuestions.length > 0 && (
              <span className="settings-badge">{savedQuestions.length}</span>
            )}
          </button>
          <Link to="/practice" className="nav-link practice-link">
            <Brain size={20} />
            Practice
          </Link>
        </div>
      </header>

      <main className="main">
        {/* Stats Panel */}
        {stats && <StatsPanel stats={stats} />}

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${tab === 'search' ? 'active' : ''}`}
            onClick={() => setTab('search')}
          >
            <Search size={18} />
            Search Questions
          </button>
          <button
            className={`tab ${tab === 'generate' ? 'active' : ''}`}
            onClick={() => setTab('generate')}
          >
            <Sparkles size={18} />
            Generate New Question
          </button>
        </div>

        {/* Search / Generate Form */}
        <form
          className="search-form"
          onSubmit={tab === 'search' ? handleSearch : handleGenerate}
        >
          <div className="search-bar">
            <input
              type="text"
              placeholder={tab === 'search'
                ? 'Search questions… (e.g. "deadlock", "semaphore", "paging")'
                : 'Topic for new question… (e.g. "mutex implementation")'
              }
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              dir="auto"
            />
            <button type="submit" disabled={searching || generating || !query.trim()}>
              {tab === 'search' ? (
                searching ? 'Searching…' : <><Search size={18} /> Search</>
              ) : (
                generating ? 'Generating…' : <><Sparkles size={18} /> Generate</>
              )}
            </button>
          </div>

          {/* Filter toggle */}
          <button
            type="button"
            className="filter-toggle"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter size={16} />
            Filters
            {showFilters ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>

          {showFilters && (
            <div className="filters">
              <div className="filter-group">
                <label>Type</label>
                <select value={questionType} onChange={(e) => setQuestionType(e.target.value)}>
                  <option value="">All Types</option>
                  <option value="MultipleChoice">Multiple Choice</option>
                  <option value="Open">Open</option>
                  <option value="CodeAnalysis">Code Analysis</option>
                </select>
              </div>
              <div className="filter-group">
                <label>Difficulty</label>
                <select value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                  <option value="">All</option>
                  <option value="Easy">Easy</option>
                  <option value="Medium">Medium</option>
                  <option value="Hard">Hard</option>
                </select>
              </div>
              <div className="filter-group">
                <label>Year</label>
                <select value={year} onChange={(e) => setYear(e.target.value)}>
                  <option value="">All Years</option>
                  {Array.from({ length: 7 }, (_, i) => 2020 + i).map(y => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
              {tab === 'search' && (
                <div className="filter-group">
                  <label>Results</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={nResults}
                    onChange={(e) => setNResults(parseInt(e.target.value) || 5)}
                  />
                </div>
              )}
            </div>
          )}
        </form>

        {/* Error */}
        {error && <div className="error">{error}</div>}

        {/* Results */}
        {tab === 'search' && results.length > 0 && (
          <div className="results">
            <h2>
              <Search size={20} />
              {results.length} Result{results.length !== 1 ? 's' : ''}
            </h2>
            <div className="results-grid">
              {results.map((r) => (
                <QuestionCard key={r.id} result={r} />
              ))}
            </div>
          </div>
        )}

        {/* Generated Question */}
        {tab === 'generate' && generated && (
          <div className="results">
            <h2>
              <Sparkles size={20} />
              Generated Question
            </h2>
            <GeneratedCard question={generated} onSave={handleSaveQuestion} />
          </div>
        )}

        {/* Topics Cloud */}
        {topics.length > 0 && (
          <div className="topics-section">
            <h3>Available Topics</h3>
            <div className="topics-cloud">
              {topics.map((t) => (
                <button
                  key={t}
                  className="topic-tag"
                  onClick={() => { setQuery(t); }}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        )}
      </main>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        savedQuestions={savedQuestions}
        onClearSaved={() => setSavedQuestions([])}
      />
    </div>
  );
}

export default App;
