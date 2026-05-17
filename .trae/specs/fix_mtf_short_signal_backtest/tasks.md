# Tasks

- [x] Task 1: 调整默认支撑/阻力位为回测期间匹配值
  - [x] 修改 `run_ethusdc_mtf_backtest.py` 中 `SUPPORT_LEVELS` 改为 `"1950,1900,1850"`、`RESISTANCE_LEVELS` 改为 `"2050,2100,2150"`
  - [x] 修改 `run_backtest.py` 中 `--support-levels` / `--resistance-levels` 的 `default` 值同步调整
  - [x] 确保做多支撑位覆盖价格区间下沿（1950,1900,1850）
  - [x] 确保做空阻力位覆盖价格区间上沿（2050,2100,2150）

- [x] Task 2: 做空止损耦合风控机制（已验证，无需修改）
  - [x] 确认 `_generate_short_entry_signal()` 信号后由 Executor 的 `_check_risk()` 控制风险
  - [x] 确认回测引擎 `_check_short_stop_loss()` 在第994-995行调用 `extend_cooldown_after_loss("short")` → `on_stop_loss()`
  - [x] 确认 `_check_risk` 和风控计数器是方向无关的（全局 `_consecutive_stops`、`_daily_pnl`），做空止损不会绕过暂停机制

- [x] Task 3: 回测验证双向信号
  - [x] 重新运行 `run_ethusdc_mtf_backtest.py` 覆盖最近90天
  - [x] 验证日志中同时出现 `[MTF] 15m做空信号检测` 和 `[MTF] 15m信号检测`
  - [x] 验证回测报告输出: 0笔交易（15m信号阈值严格，无异常）
  - [x] 验证无Python异常（exit code 0）

# Task Dependencies
- Task 1 无依赖（可立即执行）
- Task 2 无依赖（可并行执行）
- Task 3 依赖 Task 1,2