import React from 'react';

interface Props {
  detail: any;
}

const formatNum = (n: number) => {
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M';
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(2) + 'K';
  return n.toFixed(2);
};

export const DashboardCards: React.FC<Props> = ({ detail }) => {
  if (!detail) return null;

  const strategyLabel: Record<string, string> = {
    v1: 'V1 背驰策略',
    v2: 'V2 分型驱动',
    mtf: 'MTF 多周期共振',
    multi_indicator: '多指标趋势跟踪',
  };

  const cards = [
    { label: '策略版本', value: strategyLabel[detail.strategy_version || 'v1'] || detail.strategy_version || 'V1', cls: '' },
    { label: '最终权益', value: `$${formatNum(detail.final_equity)}`, cls: '' },
    { label: '净利润', value: `$${formatNum(detail.net_profit)}`, cls: detail.net_profit >= 0 ? 'positive' : 'negative' },
    { label: '总收益率', value: `${detail.total_return_pct?.toFixed(2)}%`, cls: detail.total_return_pct >= 0 ? 'positive' : 'negative' },
    { label: '最大回撤', value: `${detail.max_drawdown_pct?.toFixed(2)}%`, cls: 'negative' },
    { label: '夏普比率', value: detail.sharpe_ratio?.toFixed(2), cls: '' },
    { label: '总交易次数', value: detail.total_trades, cls: '' },
    { label: '胜率', value: `${detail.win_rate_pct?.toFixed(2)}%`, cls: detail.win_rate_pct >= 50 ? 'positive' : '' },
    { label: '平均盈亏', value: `$${formatNum(detail.avg_trade_profit)}`, cls: detail.avg_trade_profit >= 0 ? 'positive' : 'negative' },
  ];

  // 资金费用卡片
  if (detail.funding_fee_summary) {
    cards.push({
      label: '资金费用',
      value: `$${formatNum(detail.funding_fee_summary.net_fee)} (${detail.funding_fee_summary.settlement_count}次)`,
      cls: detail.funding_fee_summary.net_fee >= 0 ? 'positive' : 'negative',
    });
  }

  return (
    <div className="grid-4">
      {cards.map(c => (
        <div className="card" key={c.label}>
          <h3>{c.label}</h3>
          <div className={`value ${c.cls}`}>{c.value}</div>
        </div>
      ))}
    </div>
  );
};