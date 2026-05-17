# Tasks: 移除背离信号 + 动态支撑阻力阈值

- [x] Task 1: 从30m做多确认信号中移除底背离
  - [x] SubTask 1.1: 修改 `_check_30m_signals()`，将 `self._check_30m_divergence()` 替换为固定 `False`
  - [x] SubTask 1.2: 确认 `_check_30m_divergence()` 方法体保留不删除
  - [x] SubTask 1.3: 确认 `_generate_entry_signal()` 的 signal_details 中 divergence 固定为 False

- [x] Task 2: 从30m做空确认信号中移除顶背离
  - [x] SubTask 2.1: 修改 `_check_30m_short_signals()`，将 `self._check_30m_top_divergence()` 替换为固定 `False`
  - [x] SubTask 2.2: 确认 `_check_30m_top_divergence()` 方法体保留不删除
  - [x] SubTask 2.3: 确认 `_generate_short_entry_signal()` 的 signal_details 中 top_divergence 固定为 False

- [x] Task 3: 实现动态支撑/阻力阈值
  - [x] SubTask 3.1: 在 `_check_support_zone()` 中，将 `self.support_threshold` 替换为动态计算的阈值
  - [x] SubTask 3.2: 在 `_check_resistance_zone()` 中，将 `self.resistance_threshold` 替换为动态计算的阈值
  - [x] SubTask 3.3: 动态阈值公式: `min(current_atr * 0.5, current_price * 0.01)`，ATR为0时回退到 `current_price * 0.01`

- [x] Task 4: 提升投入金额占比至50%
  - [x] SubTask 4.1: 修改 `run_ethusdc_mtf_backtest.py` 中 `INVESTMENT_RATIO = 0.50`
  - [x] SubTask 4.2: 修改 `MultiTFFractalStrategy.__init__` 中 `investment_ratio` 默认值为 `0.50`

- [x] Task 5: 运行回测验证
  - [x] SubTask 5.1: 运行 `run_ethusdc_mtf_backtest.py`
  - [x] SubTask 5.2: 确认交易数 > 0，日志中30m信号为3种（不再出现divergence/top_divergence）
  - [x] SubTask 5.3: 确认动态阈值数值合理（在1%价格范围内）
  - [x] SubTask 5.4: 确认交易仓位使用了50%投入比例（净利润从$85→$1,106，约5倍提升）

# Task Dependencies
- Task 1 和 Task 2 互相独立，可并行执行
- Task 3 独立于 Task 1、2
- Task 4 独立于所有 Task
- Task 5 依赖所有 Task 完成