const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, options);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface BacktestSummary {
  id: string; filename: string; created: string; symbol: string;
  start_date: string; end_date: string; net_profit: number;
  total_return_pct: number; total_trades: number; win_rate_pct: number;
  max_drawdown_pct: number; sharpe_ratio: number;
  strategy_version?: string;
}

export interface BacktestDetail {
  initial_balance: number; final_equity: number; net_profit: number;
  total_return_pct: number; max_drawdown_pct: number; sharpe_ratio: number;
  total_trades: number; closed_trades: number; win_rate_pct: number;
  avg_trade_profit: number; avg_holding_hours: number; profit_factor: number;
  timestamps: string[]; equity_curve: number[]; trades: TradeRecord[];
  strategy_version?: string;
  funding_fee_summary?: { total_paid: number; total_received: number; net_fee: number; settlement_count: number };
}

export interface TradeRecord {
  timestamp: string; action: string; price: number; amount: number;
  balance: number; position: number; equity: number;
  profit: number; profit_pct: number; reason: string;
  stop_loss: number; take_profit: number;
  indicators?: any;
}

export interface SignalDetail {
  backtest_id: string; total_trades: number;
  enriched_trades: any[]; indicator_stats: any; summary: any;
}

export const api = {
  listBacktests: () => request<{count: number; results: BacktestSummary[]}>('/backtest/list'),
  getBacktest: (id: string) => request<BacktestDetail>(`/backtest/${id}`),
  runBacktest: (params: any) => request<{task_id: string; status: string}>('/backtest/run', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(params)
  }),
  getTaskStatus: (taskId: string) => request<any>(`/backtest/task/${taskId}`),
  getParams: () => request<any>('/backtest/params'),
  getDaterange: () => request<any>('/backtest/data/daterange'),
  getSignalDetail: (id: string) => request<SignalDetail>(`/signal/detail/${id}`),
  getSignalAnalysis: (id: string) => request<any>(`/signal/analysis/${id}`),
};