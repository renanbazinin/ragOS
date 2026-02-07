import { BarChart3 } from 'lucide-react';
import type { Stats } from './types';

interface Props {
  stats: Stats;
}

export default function StatsPanel({ stats }: Props) {
  return (
    <div className="stats-panel">
      <div className="stat-card">
        <BarChart3 size={20} />
        <div>
          <span className="stat-value">{stats.total_questions}</span>
          <span className="stat-label">Total Questions</span>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-breakdown">
          {Object.entries(stats.types).map(([type, count]) => (
            <div key={type} className="stat-row">
              <span className="stat-key">{type}</span>
              <span className="stat-count">{count}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-breakdown">
          {Object.entries(stats.difficulties).map(([diff, count]) => (
            <div key={diff} className="stat-row">
              <span className="stat-key">{diff}</span>
              <span className="stat-count">{count}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-breakdown">
          {Object.entries(stats.years).map(([yr, count]) => (
            <div key={yr} className="stat-row">
              <span className="stat-key">{yr}</span>
              <span className="stat-count">{count}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
