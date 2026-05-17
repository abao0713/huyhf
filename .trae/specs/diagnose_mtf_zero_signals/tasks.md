# Tasks: MTF策略零信号根因诊断与修复

- [x] Task 1: 实现支撑/阻力位动态计算
  - [x] SubTask 1.1: 在 `MultiTFFractalStrategy.__init__` 中添加 `auto_levels` 参数，默认 True
  - [x] SubTask 1.2: 实现 `_calculate_auto_levels()` 方法：基于近期60bar价格区间自动计算支撑/阻力位
    - 使用 `recent_range = recent_high - recent_low`（而非全量历史 `price_range`）
    - 支撑位: `recent_low + recent_range * [0, 0.15, 0.30, 0.45]`
    - 阻力位: `recent_low + recent_range * [0.55, 0.70, 0.85]` + `recent_high`
  - [x] SubTask 1.3: 在 `inject_data()` 中调用 `_calculate_auto_levels()`
  - [x] SubTask 1.4: 移除私自提前返回逻辑，允许回测循环中动态更新
  - [x] SubTask 1.5: 直接覆盖 `support_levels` / `resistance_levels`（而非仅为空时设置）

- [x] Task 2: 放宽30m确认信号门槛
  - [x] SubTask 2.1: 新增配置参数 `min_signal_count: int = 1`，允许用户调节
  - [x] SubTask 2.2: 将 `_check_30m_signals()` 和 `_check_30m_short_signals()` 使用 `self.min_signal_count`

- [x] Task 3: 修复分型索引与数据帧索引不匹配
  - [x] SubTask 3.1: 在 `_check_4h_bottom_fractal()` 中将 `df_4h.iloc[k2_idx]` 改为 `df_processed.iloc[k2_idx]`
  - [x] SubTask 3.2: 在 `_check_4h_top_fractal()` 中同样修复
  - [x] SubTask 3.3: 修复 `_generate_entry_signal` 和 `_generate_short_entry_signal` 中的索引使用
  - [x] SubTask 3.4: 修复 `_generate_confirm_signal` 和 `_generate_short_confirm_signal` 中的索引使用

- [x] Task 4: 修复回测引擎action不匹配（真正的根因）
  - [x] SubTask 4.1: argparse 默认值 `default="2050,2100,2150"` 覆盖自动计算 → 改为 `default=None`
  - [x] SubTask 4.2: `_validate_signal()` 只接受 BUY/SELL，不识别 MTF 的 PROBE_ENTRY 等 → 添加白名单
  - [x] SubTask 4.3: 在 `_execute_trade()` 中添加 MTF action 到 BUY/SELL 的转换逻辑
  - [x] SubTask 4.4: MTF 加仓使用信号中的 `position_ratio` 而非固定的 0.5
  - [x] SubTask 4.5: 执行后调用 `strategy.update_position_from_signal()` 同步策略状态
  - [x] SubTask 4.6: 止损时调用 `strategy.clear_position()` 重置仓位状态

- [x] Task 5: 修复 inject_data 截断30m数据（最关键Bug）
  - [x] SubTask 5.1: `inject_data()` 保存完整30m数据为 `_df_30m_full`
  - [x] SubTask 5.2: `_process_data()` 始终从 `_df_30m_full` 时间过滤，而非被截断的 `self.df_30m`

- [x] Task 6: 运行回测验证
  - [x] SubTask 6.1: 运行 `run_ethusdc_mtf_backtest.py`
  - [x] SubTask 6.2: 确认交易数 > 0 → **3笔交易，胜率100%，净利$85.72**

# 发现的根因总结

1. **auto_levels 全量price_range BUG**: `price_range = high.max() - low.min()` 使用全量2.5年数据（5343-1000=4343），导致 `recent_low + 4343*0.12 = 2726` 远超当前价格
2. **argparse 默认值覆盖**: `run_backtest.py` 中 `--resistance-levels` 默认 `"2050,2100,2150"` 覆盖了自动计算
3. **backtest_engine action不匹配**: MTF策略输出 PROBE_ENTRY/PROBE_ENTRY_SHORT/CONFIRM_ADD/CONFIRM_ADD_SHORT，回测引擎 `_validate_signal()` 只接受 BUY/SELL，所有信号被静默丢弃
4. **inject_data 截断30m数据**: `inject_data` 将过滤后的30m数据写回 `self.df_30m`，后续bar的 `_process_data` 从已截断数据中过滤，丢失新增的30m bar → 所有30m信号返回False
5. **看跌/看涨吞没形态Bug**: `c1_body` 错误使用了 `c2` 的数据计算（已修复）

# Task Dependencies
- Task 2 和 Task 3 互相独立，可并行执行
- Task 1 和 Task 2 可并行执行
- Task 6 依赖所有 Task 完成