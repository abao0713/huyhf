# Checklist

- [x] 双仓位状态正确拆分
  - [x] `self.long_position` 和 `self.short_position` 独立维护
  - [x] `self.long_avg_price` 和 `self.short_avg_price` 分别计算
  - [x] `_reset_state()` 正确重置双仓位
  - [x] 权益计算包含多空双方向的浮动盈亏 (long_pnl + short_pnl)
  - [x] TradeRecord 能区分做多做空交易 (包含 long_position/short_position 字段)

- [x] 独立止盈止损参数已配置
  - [x] BacktestConfig 包含 `long_take_profit_ratio`, `long_stop_loss_ratio` 等做多参数
  - [x] BacktestConfig 包含 `short_take_profit_ratio`, `short_stop_loss_ratio` 等做空参数
  - [x] 做多追踪止损独立上移，不影响做空
  - [x] 做空追踪止损独立下移，不影响做多
  - [x] 做多止盈止损只平多单，不做空 ✅ 日志显示 [LONG] 止盈/止损
  - [x] 做空止盈止损只平空单，不做多 ✅ 日志显示 [SHORT] 止盈/止损

- [x] 自动反向开仓已移除
  - [x] `_check_advanced_stop_loss` 不再自动反向开仓（方法已删除）
  - [x] `_execute_trade` BUY/SELL 信号不再耦合对向平仓
  - [x] `_open_long_position()` 和 `_open_short_position()` 方法已移除

- [x] 独立做多仓位管理完整
  - [x] `_open_long()` 正确开多单
  - [x] `_close_long()` 正确平多单并计算盈亏
  - [x] 做多冷却期独立生效
  - [x] `_buy_with_reason()` 适配新仓位状态

- [x] 独立做空仓位管理完整
  - [x] `_open_short()` 正确开空单
  - [x] `_close_short_position()` 正确平空单并计算盈亏
  - [x] 做空冷却期独立生效

- [x] 策略信号分成正确的独立多空
  - [x] `long_signal_cooldown_bars` 和 `short_signal_cooldown_bars` 独立配置
  - [x] `long_signal_info` 和 `short_signal_info` 独立跟踪
  - [x] BUY 信号只影响做多系统
  - [x] SELL 信号只影响做空系统

- [x] 资金费用正确适配双仓位
  - [x] 多空资金费用分别计算 ✅ 日志: "多头:0.0000/$0.00, 空头:0.1627/$354.10"
  - [x] 总资金费用正确汇总
  - [x] 余额调整正确

- [x] 回测结果和图表更新
  - [x] 回测报告分开展示做多做空统计 [LONG]/[SHORT] 前缀
  - [x] 图表中做多做空信号使用不同颜色/标记
  - [x] 交易记录包含方向标识

- [x] 整合测试通过
  - [x] 60天数据回测成功 (1000根K线, 5分29秒)
  - [x] 做多做空信号互不影响 (独立冷却期生效)
  - [x] 独立止盈止损正确触发 ([LONG]止盈, [SHORT]止损 等)
  - [x] 同时持有多空仓位时权益计算正确
  - [x] 图表清晰展示多空独立信号 (19个信号)
