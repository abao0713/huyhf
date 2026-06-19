import React, { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';

interface Props {
  timestamps: string[];
  equity: number[];
}

export const EquityChart: React.FC<Props> = ({ timestamps, equity }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !timestamps?.length) return;
    const initialBalance = equity[0];
    const trace1 = {
      x: timestamps,
      y: equity,
      type: 'scatter',
      mode: 'lines',
      name: '权益曲线',
      line: { color: '#0ea5e9', width: 2 },
      fill: 'tozeroy',
      fillcolor: 'rgba(14, 165, 233, 0.1)',
    };
    const trace2 = {
      x: [timestamps[0], timestamps[timestamps.length - 1]],
      y: [initialBalance, initialBalance],
      type: 'scatter',
      mode: 'lines',
      name: '初始资金',
      line: { color: '#64748b', width: 1, dash: 'dash' },
    };
    const layout = {
      paper_bgcolor: '#1e293b',
      plot_bgcolor: '#1e293b',
      font: { color: '#94a3b8', size: 12 },
      margin: { l: 60, r: 20, t: 20, b: 60 },
      xaxis: { gridcolor: '#334155', zeroline: false },
      yaxis: { gridcolor: '#334155', zeroline: false, tickprefix: '$' },
      showlegend: true,
      legend: { x: 0, y: 1.1, orientation: 'h' },
      hovermode: 'x unified',
      height: 400,
    };
    Plotly.newPlot(ref.current!, [trace1, trace2], layout, { responsive: true, displayModeBar: false });
  }, [timestamps, equity]);

  return <div className="chart-container"><div ref={ref} style={{ width: '100%' }} /></div>;
};