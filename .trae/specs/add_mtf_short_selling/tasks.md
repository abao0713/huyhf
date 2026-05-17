# Tasks

- [x] Task 1: 扩展 `MultiTFFractalStrategy` 构造函数和参数
  - [x] 新增 `resistance_levels`、`resistance_threshold`、`profit_loss_ratio`、`enable_trend_filter`、`enable_volume_filter` 参数
  - [x] 新增 `_last_short_signal_time` 追踪做空信号时间
  - [x] 修改 `initialize()` 日志输出包含阻力位信息

- [x] Task 2: 实现30分钟级别做空预判
  - [x] 新增 `_check_resistance_zone()` 阻力区域检测（价格 >= 阻力位 - 阈值）
  - [x] 新增 `_check_30m_top_fractal()` 顶分型预判（K2.high > K1.high AND K2.close < K2.open * 1.5）

- [x] Task 3: 实现15分钟级别空头多信号检测
  - [x] 新增 `_check_15m_top_divergence()` 顶背离检测（新高 + MACD未新高）
  - [x] 新增 `_check_15m_bearish_candlestick()` 看跌K线形态（黄昏之星/看跌吞没/射击之星/乌云盖顶）
  - [x] 新增 `_check_15m_trendline_break_down()` 跌破上升趋势线检测
  - [x] 新增 `_check_15m_death_cross()` 死叉检测（MACD死叉 / KDJ高位死叉K>80）
  - [x] 新增 `_check_15m_short_signals()` 空头信号汇总方法

- [x] Task 4: 实现做空信号生成和双向仓位管理
  - [x] 新增 `_generate_short_entry_signal()` 做空试探入场信号（40%仓位+止盈）
  - [x] 新增 `_generate_short_confirm_signal()` 做空确认加仓信号（60%仓位）
  - [x] 修改 `generate_signal()` 支持双向检测和信号优先级
  - [x] 修改 `update_position_from_signal()` 支持 short 方向
  - [x] 修改 `clear_position()` 支持双向清仓

- [x] Task 5: 实现做空可选过滤条件
  - [x] 实现大周期趋势过滤 `_check_daily_trend_for_short()` (日线EMA20>EMA60降仓50%)
  - [x] 实现强势上涨回避 `_check_strong_rally_avoid()` (连续3阳线涨0.5%拒绝)
  - [x] 实现成交量萎缩谨慎 `_check_volume_shrinkage()` (量<20周期60%降仓50%)

- [x] Task 6: 扩展 `MultiTFFractalStrategyExecutor` 做空交易执行
  - [x] 新增 `_open_short_probe()` 做空试探开仓
  - [x] 新增 `_add_short_confirm()` 做空确认加仓
  - [x] 修改 `_execute_signal()` 支持 `PROBE_ENTRY_SHORT` / `CONFIRM_ADD_SHORT`

- [x] Task 7: 扩展运行脚本 `run_ethusdc_mtf_live.py`
  - [x] 新增 `--resistance-levels` CLI 参数
  - [x] 修改 DryRunExecutor 支持做空信号日志
  - [x] 启动信息显示阻力位和止盈比

- [x] Task 8: 运行 dry-run 验证
  - [x] 验证做空阻力位预判逻辑
  - [x] 验证15分钟空头多信号检测输出
  - [x] 验证做空两阶段仓位管理
  - [x] 验证过滤条件触发
  - [x] 验证多空双向不冲突

# Task Dependencies
- Task 2 依赖 Task 1 ✓
- Task 3 依赖 Task 1 ✓
- Task 4 依赖 Task 2, 3 ✓
- Task 5 依赖 Task 1 ✓
- Task 6 依赖 Task 4 ✓
- Task 7 依赖 Task 6 ✓
- Task 8 依赖 Task 7 ✓