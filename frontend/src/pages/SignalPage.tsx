import React, { useState, useEffect } from 'react';
import { api, BacktestSummary } from '../api';
import { SignalDetailComp } from '../components/SignalDetail';

interface Props {
  results: BacktestSummary[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export const SignalPage: React.FC<Props> = ({ results, selectedId, onSelect }) => {
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    api.getSignalAnalysis(selectedId).then(setAnalysis).catch(console.error).finally(() => setLoading(false));
  }, [selectedId]);

  return (
    <div>
      <div className="flex-row mb-16">
        <span className="text-sm">选择回测结果:</span>
        {results.map(r => (
          <button key={r.id} className={`btn-sm ${selectedId === r.id ? 'active' : ''}`}
            onClick={() => onSelect(r.id)}
            style={selectedId === r.id ? { background: '#0ea5e9', color: 'white' } : {}}>
            {r.start_date} ~ {r.end_date}
          </button>
        ))}
      </div>

      {loading && <div className="text-center mb-16"><span className="loading" /> 加载信号分析...</div>}

      {analysis && <SignalDetailComp analysis={analysis} backtestId={selectedId} />}
    </div>
  );
};