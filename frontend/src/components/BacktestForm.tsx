import React, { useState, useEffect } from 'react';
import { api } from '../api';

interface Props {
  onRun: (params: any) => void;
  taskStatus: string;
}

export const BacktestForm: React.FC<Props> = ({ onRun, taskStatus }) => {
  const [params, setParams] = useState({
    symbol: 'ETHUSDC', interval: '4h', initial_balance: 10000,
    leverage: 10, investment_ratio: 0.5, strategy_version: 'mtf',
    enable_early_entry: true, enable_early_short_entry: true,
    early_entry_min_confidence: 0.6, min_early_entry_conditions: 2,
    start_date: '', end_date: '', use_live_data: false,
    // multi_indicator 专属参数
    fast_ema_period: 2, slow_ema_period: 42, adx_threshold: 20, bb_width_threshold: 0.05,
  });
  const [daterange, setDaterange] = useState<any>(null);
  const isRunning = taskStatus === 'pending' || taskStatus === 'running';

  useEffect(() => {
    api.getDaterange().then(setDaterange).catch(() => {});
  }, []);

  const update = (key: string, value: any) => setParams(p => ({ ...p, [key]: value }));

  return (
    <div className="form-section">
      <h3 style={{ marginBottom: 16, color: '#38bdf8' }}>回测配置</h3>
      <div className="form-grid">
        <div className="form-group">
          <label>交易对</label>
          <select value={params.symbol} onChange={e => update('symbol', e.target.value)}>
            <option>ETHUSDC</option>
          </select>
        </div>
        <div className="form-group">
          <label>K线周期</label>
          <select value={params.interval} onChange={e => update('interval', e.target.value)}>
            <option>5m</option><option>15m</option><option>30m</option><option>1h</option>
            <option>4h</option><option>1d</option>
          </select>
        </div>
        <div className="form-group">
          <label>策略版本</label>
          <select value={params.strategy_version} onChange={e => update('strategy_version', e.target.value)}>
            <option value="v1">V1 背驰策略</option>
            <option value="v2">V2 分型驱动</option>
            <option value="mtf">MTF 多周期共振</option>
            <option value="multi_indicator">多指标趋势跟踪</option>
          </select>
        </div>
        <div className="form-group">
          <label>初始资金 ($)</label>
          <input type="number" value={params.initial_balance} onChange={e => update('initial_balance', Number(e.target.value))} />
        </div>
        <div className="form-group">
          <label>杠杆倍数</label>
          <input type="number" value={params.leverage} min={1} max={125} onChange={e => update('leverage', Number(e.target.value))} />
        </div>
        <div className="form-group">
          <label>投入比例</label>
          <input type="number" value={params.investment_ratio} step={0.05} min={0.01} max={1} onChange={e => update('investment_ratio', Number(e.target.value))} />
        </div>
        <div className="form-group">
          <label>开始日期</label>
          <input type="date" value={params.start_date} onChange={e => update('start_date', e.target.value)}
            min={daterange?.start || ''} max={daterange?.end || ''} />
          {daterange && <span className="text-sm">可用: {daterange.start} ~ {daterange.end}</span>}
        </div>
        <div className="form-group">
          <label>结束日期</label>
          <input type="date" value={params.end_date} onChange={e => update('end_date', e.target.value)}
            min={daterange?.start || ''} max={daterange?.end || ''} />
        </div>
        <div className="form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={params.use_live_data}
              onChange={e => update('use_live_data', e.target.checked)} />
            使用实时数据
          </label>
          {params.use_live_data && <span className="text-sm" style={{ color: '#34d399' }}>回测前下载最新数据</span>}
        </div>
      </div>
      {params.strategy_version === 'mtf' && (
        <div className="form-grid" style={{ marginTop: 16 }}>
          <div className="form-group">
            <label>提前做多</label>
            <select value={params.enable_early_entry ? 'true' : 'false'}
              onChange={e => update('enable_early_entry', e.target.value === 'true')}>
              <option value="true">启用</option><option value="false">禁用</option>
            </select>
          </div>
          <div className="form-group">
            <label>提前做空</label>
            <select value={params.enable_early_short_entry ? 'true' : 'false'}
              onChange={e => update('enable_early_short_entry', e.target.value === 'true')}>
              <option value="true">启用</option><option value="false">禁用</option>
            </select>
          </div>
          <div className="form-group">
            <label>提前入场最低置信度</label>
            <input type="number" value={params.early_entry_min_confidence} step={0.1} min={0.1} max={1}
              onChange={e => update('early_entry_min_confidence', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>提前入场最少条件数</label>
            <input type="number" value={params.min_early_entry_conditions} min={1} max={3}
              onChange={e => update('min_early_entry_conditions', Number(e.target.value))} />
          </div>
        </div>
      )}
      {params.strategy_version === 'multi_indicator' && (
        <div className="form-grid" style={{ marginTop: 16 }}>
          <div className="form-group">
            <label>快线EMA周期</label>
            <input type="number" value={params.fast_ema_period} min={1} max={10}
              onChange={e => update('fast_ema_period', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>慢线EMA周期</label>
            <input type="number" value={params.slow_ema_period} min={10} max={100}
              onChange={e => update('slow_ema_period', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>ADX震荡阈值</label>
            <input type="number" value={params.adx_threshold} min={10} max={40}
              onChange={e => update('adx_threshold', Number(e.target.value))} />
          </div>
          <div className="form-group">
            <label>布林宽度阈值</label>
            <input type="number" value={params.bb_width_threshold} step={0.01} min={0.01} max={0.2}
              onChange={e => update('bb_width_threshold', Number(e.target.value))} />
          </div>
        </div>
      )}
      <div style={{ marginTop: 20 }}>
        <button className="btn btn-primary" onClick={() => onRun(params)} disabled={isRunning}>
          {isRunning ? '运行中...' : '运行回测'}
        </button>
      </div>
    </div>
  );
};