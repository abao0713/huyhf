import React, { useState, useEffect } from 'react';
import { api, BacktestSummary, BacktestDetail } from '../api';
import { BacktestForm } from '../components/BacktestForm';
import { DashboardCards } from '../components/DashboardCards';
import { EquityChart } from '../components/EquityChart';
import { TradeTable } from '../components/TradeTable';

interface Props {
  results: BacktestSummary[];
  selectedId: string;
  onSelect: (id: string) => void;
  onRefresh: () => void;
}

export const BacktestPage: React.FC<Props> = ({ results, selectedId, onSelect, onRefresh }) => {
  const [detail, setDetail] = useState<BacktestDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [taskId, setTaskId] = useState<string>('');
  const [taskStatus, setTaskStatus] = useState<string>('');

  useEffect(() => {
    if (!selectedId) return;
    setLoading(true);
    api.getBacktest(selectedId).then(setDetail).catch(console.error).finally(() => setLoading(false));
  }, [selectedId]);

  // Poll task status
  useEffect(() => {
    if (!taskId || taskStatus === 'completed' || taskStatus === 'failed') return;
    const timer = setInterval(async () => {
      try {
        const s = await api.getTaskStatus(taskId);
        setTaskStatus(s.status);
        if (s.status === 'completed') {
          await onRefresh();
          if (s.result?.id) onSelect(s.result.id);
        }
      } catch {}
    }, 2000);
    return () => clearInterval(timer);
  }, [taskId, taskStatus]);

  const handleRun = async (params: any) => {
    try {
      const res = await api.runBacktest(params);
      setTaskId(res.task_id);
      setTaskStatus('pending');
    } catch (e: any) {
      alert('回测启动失败: ' + e.message);
    }
  };

  return (
    <div>
      <BacktestForm onRun={handleRun} taskStatus={taskStatus} />

      {taskStatus && taskStatus !== 'completed' && (
        <div className="card mb-16">
          <div className="flex-row">
            <span className="loading" />
            <span>回测{taskStatus === 'running' ? '运行中' : '排队中'}... (任务ID: {taskId})</span>
          </div>
        </div>
      )}

      <div className="mb-16">
        <div className="text-sm mb-16">历史回测结果 ({results.length})</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {results.map(r => (
            <button key={r.id} className={`btn-sm ${selectedId === r.id ? 'active' : ''}`}
              onClick={() => { onSelect(r.id); setTaskStatus(''); }}
              style={selectedId === r.id ? { background: '#0ea5e9', color: 'white' } : {}}>
              {r.start_date} ~ {r.end_date}
              <span className="text-sm" style={{ marginLeft: 8, opacity: 0.6 }}>
                {r.strategy_version || 'v1'} | {r.total_trades}笔 | {r.total_return_pct.toFixed(0)}%
              </span>
            </button>
          ))}
          {results.length === 0 && <span className="text-sm">暂无回测结果，请运行新回测</span>}
        </div>
      </div>

      {loading && <div className="text-center mb-16"><span className="loading" /> 加载中...</div>}

      {detail && (
        <>
          <DashboardCards detail={detail} />
          <EquityChart timestamps={detail.timestamps} equity={detail.equity_curve} />
          <TradeTable trades={detail.trades} />
        </>
      )}
    </div>
  );
};