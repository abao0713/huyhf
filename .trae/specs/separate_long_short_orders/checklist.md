# Checklist

- [ ] 双仓位状态正确拆分
  - [ ] `self.long_position` 和 `self.short_position` 独立维护
  - [ ] `self.long_avg_price` 和 `self.short_avg_price` 分别计算
  - [ ] `_reset_state()` 正确重置双仓位
  - [ ] 权益计算包含多空双方向的浮动盈亏
  - [ ] TradeRecord 能区分做多做空交易

- [ ] 独立止盈止损参数已配置
  - [ ] BacktestConfig 包含 `long_take_profit_ratio`, `long_stop_loss_ratio` 等做多参数
  - [ ] BacktestConfig 包含 `short_take_profit_ratio`, `short_stop_loss_ratio` 等做空参数
  - [ ] 做多追踪止损独立上移，不影响做空
  - [ ] 做空追踪止损独立下移，不影响做多
  - [ ] 做多止盈止损只平多单，不做空
  - [ ] 做空止盈止损只平空单，不做多

- [ ] 自动反向开仓已移除
  - [ ] `_check_advanced_stop_loss` 不再自动反向开仓
  - [ ] `_execute_trade` BUY/SELL 信号不再耦合对向平仓
  - [ ] `_open_long_position()` 和 `_open_short_position()` 方法已移除

- [ ] 独立做多仓位管理完整
  - [ ] `_open_long()` 正确开多单
  - [ ] `_close_long()` 正确平多单并计算盈亏
  - [ ] 做多冷却期独立生效
  - [ ] `_buy_with_reason()` 适配新仓位状态

- [ ] 独立做空仓位管理完整
  - [ ] `_open_short()` 正确开空单
  - [ ] `_close_short_position()` 正确平空单并计算盈亏
  - [ ] 做空冷却期独立生效

- [ ] 策略信号分成正确的独立多空
  - [ ] `long_signal_cooldown_bars` 和 `short_signal_cooldown_bars` 独立配置
  - [ ] `long_last_signal_info` 和 `short_last_signal_info` 独立跟踪
  - [ ] BUY 信号只影响做多系统
  - [ ] SELL 信号只影响做空系统

- [ ] 资金费用正确适配双仓位
  - [ ] 多空资金费用分别计算
  - [ ] 总资金费用正确汇总
  - [ ] 余额调整正确

- [ ] 回测结果和图表更新
  - [ ] 回测报告分开展示做多做空统计
  - [ ] 图表中做多做空信号使用不同颜色/标记
  - [ ] 交易记录包含方向标识

- [ ] 整合测试通过
  - [ ] 60天数据回测成功
  - [ ] 做多做空信号互不影响
  - [ ] 独立止盈止损正确触发
  - [ ] 同时持有多空仓位时权益计算正确
  - [ ] 图表清晰展示多空独立信号
