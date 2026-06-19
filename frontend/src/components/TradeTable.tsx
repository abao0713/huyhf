import React, { useState } from 'react';
import { TradeRecord } from '../api';

interface Props {
  trades: TradeRecord[];
}

const ACTION_TAGS: Record<string, string> = {
  BUY: 'tag-buy', SELL: 'tag-sell',
  EARLY_ENTRY: 'tag-early', PROBE_ENTRY: 'tag-early', CONFIRM_ENTRY: 'tag-early',
  CLOSE_LONG: 'tag-close', CLOSE_SHORT: 'tag-close',
  PARTIAL_CLOSE_LONG: 'tag-partial', PARTIAL_CLOSE_SHORT: 'tag-partial',
};

const formatPrice = (p: number) => p?.toFixed(4);

export const TradeTable: React.FC<Props> = ({ trades }) => {
  const [filter, setFilter] = useState('ALL');
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const filtered = filter === 'ALL' ? trades : trades.filter(t => t.action === filter);
  const actions = ['ALL', ...new Set(trades.map(t => t.action))];
  const hasIndicators = trades.some(t => t.indicators && Object.keys(t.indicators).length > 0);

  if (!trades?.length) return <div className="text-sm text-center">暂无交易记录</div>;

  return (
    <div className="table-container">
      <div style={{ padding: '12px 16px', display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {actions.map(a => (
          <button key={a} className={`btn-sm ${filter === a ? 'active' : ''}`}
            onClick={() => setFilter(a)}
            style={filter === a ? { background: '#0ea5e9', color: 'white' } : {}}>
            {a} ({a === 'ALL' ? trades.length : trades.filter(t => t.action === a).length})
          </button>
        ))}
      </div>
      <table>
        <thead>
          <tr>
            <th>时间</th>
            <th>操作</th>
            <th>价格</th>
            <th>数量</th>
            <th>盈亏</th>
            <th>收益率</th>
            <th>原因</th>
            {hasIndicators && <th>指标</th>}
          </tr>
        </thead>
        <tbody>
          {filtered.map((t, i) => (
            <React.Fragment key={i}>
              <tr onClick={() => hasIndicators && setExpandedRow(expandedRow === i ? null : i)}
                style={{ cursor: hasIndicators ? 'pointer' : 'default' }}>
                <td style={{ fontSize: 12 }}>{t.timestamp?.replace('T', ' ')}</td>
                <td><span className={`tag ${ACTION_TAGS[t.action] || 'tag-early'}`}>{t.action}</span></td>
                <td>{formatPrice(t.price)}</td>
                <td>{t.amount?.toFixed(4)}</td>
                <td className={t.profit >= 0 ? 'positive' : 'negative'}>
                  {t.profit !== 0 ? `$${t.profit.toFixed(2)}` : '-'}
                </td>
                <td className={t.profit_pct >= 0 ? 'positive' : 'negative'}>
                  {t.profit_pct !== 0 ? `${t.profit_pct.toFixed(2)}%` : '-'}
                </td>
                <td style={{ fontSize: 12, color: '#94a3b8', maxWidth: 300 }}>{t.reason}</td>
                {hasIndicators && (
                  <td>
                    {t.indicators && Object.keys(t.indicators).length > 0 && (
                      <span style={{ color: '#38bdf8', fontSize: 12 }}>
                        {expandedRow === i ? '▼' : '▶'} {Object.keys(t.indicators).length}项
                      </span>
                    )}
                  </td>
                )}
              </tr>
              {expandedRow === i && t.indicators && (
                <tr style={{ background: '#1e293b' }}>
                  <td colSpan={hasIndicators ? 8 : 7} style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
                      {Object.entries(t.indicators).map(([key, value]: [string, any]) => (
                        <div key={key} style={{ fontSize: 12 }}>
                          <span style={{ color: '#94a3b8' }}>{key}: </span>
                          <span style={{ color: '#e2e8f0' }}>
                            {typeof value === 'number' ? value.toFixed(2) : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              )}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
};