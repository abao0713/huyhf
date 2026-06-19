import React, { useState, useEffect } from 'react';
import { api, BacktestSummary } from './api';
import { BacktestPage } from './pages/BacktestPage';
import { SignalPage } from './pages/SignalPage';

const App: React.FC = () => {
  const [tab, setTab] = useState<'backtest' | 'signal'>('backtest');
  const [results, setResults] = useState<BacktestSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string>('');

  const loadList = async () => {
    setLoading(true);
    try {
      const data = await api.listBacktests();
      setResults(data.results || []);
      if (data.results?.length > 0 && !selectedId) {
        setSelectedId(data.results[0].id);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  useEffect(() => { loadList(); }, []);

  return (
    <div className="app">
      <div className="header">
        <h1>交易系统回测面板</h1>
        <div className="nav">
          <button className={tab === 'backtest' ? 'active' : ''} onClick={() => setTab('backtest')}>回测面板</button>
          <button className={tab === 'signal' ? 'active' : ''} onClick={() => setTab('signal')}>信号分析</button>
          <button className="btn-sm" onClick={loadList} disabled={loading}>
            {loading ? <><span className="loading" />加载中</> : '刷新列表'}
          </button>
        </div>
      </div>

      {tab === 'backtest' ? (
        <BacktestPage results={results} selectedId={selectedId} onSelect={setSelectedId} onRefresh={loadList} />
      ) : (
        <SignalPage results={results} selectedId={selectedId} onSelect={setSelectedId} />
      )}
    </div>
  );
};

export default App;