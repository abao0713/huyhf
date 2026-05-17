# Checklist: MTF策略零信号修复验证

## 自动支撑/阻力位
- [x] `_calculate_auto_levels()` 使用近期价格区间（recent_range）而非全量历史price_range
- [x] 移除 `_auto_levels_calculated` 提前返回，允许回测循环中动态更新
- [x] 直接覆盖 `support_levels` / `resistance_levels`（而非仅为空时设置）
- [x] argparse 默认值改为 `default=None`，不再覆盖自动计算
- [x] 回测日志显示合理的支撑/阻力位（如 支撑=[2265.95, 2289.0, ...], 阻力=[2350.46, ...]）

## 30m确认信号
- [x] `min_signal_count` 参数可配置，默认1
- [x] `_check_30m_signals()` 和 `_check_30m_short_signals()` 使用 `self.min_signal_count`
- [x] 看跌/看涨吞没形态 `c1_body` 修复（使用c1而非c2的数据）

## 分型索引
- [x] `_check_4h_bottom_fractal()` 使用 `df_processed` 而非 `df_4h`
- [x] `_check_4h_top_fractal()` 使用 `df_processed` 而非 `df_4h`
- [x] `_generate_entry_signal` / `_generate_short_entry_signal` 修复
- [x] `_generate_confirm_signal` / `_generate_short_confirm_signal` 修复

## 回测引擎MTF Action支持
- [x] `_validate_signal()` 接受 PROBE_ENTRY/CONFIRM_ADD/PROBE_ENTRY_SHORT/CONFIRM_ADD_SHORT
- [x] `_execute_trade()` 中 MTF action → BUY/SELL 转换逻辑
- [x] MTF 加仓使用信号中的 `position_ratio`
- [x] 执行后调用 `strategy.update_position_from_signal()`
- [x] 止损时调用 `strategy.clear_position()`

## 30m数据完整性
- [x] `inject_data()` 保存完整30m数据为 `_df_30m_full`
- [x] `_process_data()` 始终从 `_df_30m_full` 过滤，不被截断

## 回测结果
- [x] 交易数 > 0（实际: 3笔交易）
- [x] 做多信号正常生成
- [x] 做空信号链路可达Layer3
- [x] 图表中分型标注正确