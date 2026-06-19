import React from 'react';

interface Props {
  analysis: any;
  backtestId: string;
}

export const SignalDetailComp: React.FC<Props> = ({ analysis }) => {
  if (!analysis) return null;

  const { profit_distribution, action_stats, indicator_stats, strategy_version } = analysis;

  // MTF 策略的层级
  const mtfLevels = [
    { key: '4h_level', label: '4小时级别', color: '#38bdf8' },
    { key: '30m_level', label: '30分钟级别', color: '#a78bfa' },
    { key: '15m_level', label: '15分钟级别', color: '#34d399' },
    { key: 'daily_level', label: '日线级别', color: '#fbbf24' },
  ];

  // multi_indicator 策略的指标
  const multiIndicatorItems = [
    { key: 'fast_ema', label: '快线EMA', color: '#38bdf8' },
    { key: 'slow_ema', label: '慢线EMA', color: '#a78bfa' },
    { key: 'guide_line', label: '指导线', color: '#34d399' },
    { key: 'boundary', label: '界', color: '#fbbf24' },
    { key: 'bb_upper', label: '布林上限', color: '#f87171' },
    { key: 'bb_lower', label: '布林下限', color: '#60a5fa' },
    { key: 'adx', label: 'ADX', color: '#c084fc' },
    { key: 'is_ranging', label: '震荡检测', color: '#94a3b8' },
  ];

  const isMultiIndicator = strategy_version === 'multi_indicator';

  return (
    <div>
      {/* 盈亏分布 */}
      <div className="signal-panel">
        <h3 style={{ marginBottom: 16, color: '#38bdf8' }}>盈亏分布</h3>
        <div className="grid-4">
          {[
            { label: '盈利次数', value: profit_distribution.win_count, cls: 'positive' },
            { label: '亏损次数', value: profit_distribution.loss_count, cls: 'negative' },
            { label: '平均盈利', value: `$${profit_distribution.avg_win.toFixed(2)}`, cls: 'positive' },
            { label: '平均亏损', value: `$${profit_distribution.avg_loss.toFixed(2)}`, cls: 'negative' },
            { label: '最大盈利', value: `$${profit_distribution.max_win.toFixed(2)}`, cls: 'positive' },
            { label: '最大亏损', value: `$${profit_distribution.max_loss.toFixed(2)}`, cls: 'negative' },
            { label: '盈利率', value: `${(profit_distribution.profit_ratio * 100).toFixed(1)}%`, cls: 'positive' },
            { label: '盈亏比', value: (Math.abs(profit_distribution.avg_win / (profit_distribution.avg_loss || 1))).toFixed(2), cls: '' },
          ].map(c => (
            <div className="card" key={c.label}>
              <h3>{c.label}</h3>
              <div className={`value ${c.cls}`}>{c.value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* 指标触发统计 */}
      <div className="signal-panel">
        <h3 style={{ marginBottom: 16, color: '#38bdf8' }}>信号指标触发统计</h3>
        <p className="text-sm" style={{ marginBottom: 12 }}>
          展示每笔交易信号生成时各技术指标的触发频率
        </p>

        {/* multi_indicator 策略 */}
        {isMultiIndicator && indicator_stats && (
          <div className="signal-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
            {multiIndicatorItems.map(item => (
              <div className="signal-level" key={item.key}>
                <h4 style={{ color: item.color }}>{item.label}</h4>
                {indicator_stats[item.key] !== undefined && (
                  <div className="signal-item">
                    <span>触发次数</span>
                    <span className="count">{indicator_stats[item.key]}次</span>
                  </div>
                )}
                {!indicator_stats[item.key] && (
                  <span className="text-sm">无触发</span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* MTF 策略 */}
        {!isMultiIndicator && (
          <div className="signal-grid">
            {mtfLevels.map(level => (
              <div className="signal-level" key={level.key}>
                <h4 style={{ color: level.color }}>{level.label}</h4>
                {indicator_stats?.[level.key] && Object.entries(indicator_stats[level.key] as Record<string, number>).map(([name, count]) => (
                  <div className="signal-item" key={name}>
                    <span>{name}</span>
                    <span className="count">{count as number}次</span>
                  </div>
                ))}
                {(!indicator_stats?.[level.key] || Object.keys(indicator_stats[level.key]).length === 0) && (
                  <span className="text-sm">无触发</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 操作类型统计 */}
      <div className="signal-panel">
        <h3 style={{ marginBottom: 16, color: '#38bdf8' }}>操作类型统计</h3>
        <table>
          <thead>
            <tr>
              <th>操作类型</th>
              <th>次数</th>
              <th>总盈亏</th>
              <th>平均盈亏</th>
            </tr>
          </thead>
          <tbody>
            {action_stats && Object.entries(action_stats).map(([action, stats]: [string, any]) => (
              <tr key={action}>
                <td><span className="tag tag-early">{action}</span></td>
                <td>{stats.count}</td>
                <td className={stats.total_profit >= 0 ? 'positive' : 'negative'}>
                  ${stats.total_profit.toFixed(2)}
                </td>
                <td className={stats.avg_profit >= 0 ? 'positive' : 'negative'}>
                  ${stats.avg_profit.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};