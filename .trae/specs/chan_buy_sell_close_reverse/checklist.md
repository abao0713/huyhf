# Checklist

- [x] argparse `--strategy-version` 的 choices 列表包含 `"chan_buy_sell"`
- [x] `_check_state_transitions()` 中 `LONG_ENTRY` 状态下检测到一卖 → 状态重置为 IDLE
- [x] `_check_state_transitions()` 中 `WATCHING_SIMILAR_BUY` 状态下检测到一卖 → 状态重置为 IDLE
- [x] `_check_state_transitions()` 中 `SHORT_ENTRY` 状态下检测到一买 → 状态重置为 IDLE
- [x] `_check_state_transitions()` 中 `WATCHING_SIMILAR_SELL` 状态下检测到一买 → 状态重置为 IDLE
- [x] `generate_signal()` 中多仓 + 一卖 → 返回 `CLOSE_LONG` 信号
- [x] `generate_signal()` 中空仓 + 一买 → 返回 `CLOSE_SHORT` 信号
- [x] 反向平仓信号优先级高于加仓信号
- [x] `ChanBuySellStrategy` 可正常导入
- [x] 回测命令 `python run_chan_buy_sell_backtest.py --days 120` 可正常执行至完成
- [x] 回测输出包含完整绩效报告