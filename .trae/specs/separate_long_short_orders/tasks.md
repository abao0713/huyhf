# Tasks

- [ ] Task 1: 拆分仓位状态为独立的多空仓位
  - [ ] SubTask 1.1: 在 BacktestEngine 中将 `self.position` 拆分为 `self.long_position` 和 `self.short_position`
  - [ ] SubTask 1.2: 添加 `self.long_avg_price` 和 `self.short_avg_price` 分别记录做多做空开仓均价
  - [ ] SubTask 1.3: 修改 `_reset_state()` 重置双仓位状态
  - [ ] SubTask 1.4: 修改 `_update_equity()` 权益计算支持双仓位浮动盈亏
  - [ ] SubTask 1.5: 修改 TradeRecord 的 `position` 字段，支持同时记录多空仓位

- [ ] Task 2: 为做多和做空分别创建独立的止盈止损参数和追踪
  - [ ] SubTask 2.1: 在 BacktestConfig 中添加独立的做多止盈止损参数
  - [ ] SubTask 2.2: 在 BacktestConfig 中添加独立的做空止盈止损参数
  - [ ] SubTask 2.3: 拆分 `_initialize_stop_loss()` 为 `_init_long_stop_loss()` 和 `_init_short_stop_loss()`
  - [ ] SubTask 2.4: 拆分 `_update_trailing_stop()` 为 `_update_long_trailing_stop()` 和 `_update_short_trailing_stop()`
  - [ ] SubTask 2.5: 拆分 `_check_advanced_stop_loss()` 为 `_check_long_stop_loss()` 和 `_check_short_stop_loss()`

- [ ] Task 3: 移除"自动反向开仓"逻辑，改为独立信号决策
  - [ ] SubTask 3.1: 从 `_check_advanced_stop_loss` 中移除平多自动开空、平空自动开多的代码
  - [ ] SubTask 3.2: 从 `_execute_trade` 的 BUY 信号中移除先平空再开多的耦合逻辑
  - [ ] SubTask 3.3: 从 `_execute_trade` 的 SELL 信号中移除先平多再开空的耦合逻辑
  - [ ] SubTask 3.4: 移除 `_open_long_position()` 和 `_open_short_position()` 辅助方法

- [ ] Task 4: 实现独立的做多仓位管理（开仓、加仓、平仓）
  - [ ] SubTask 4.1: 创建 `_open_long()` 方法独立开多单
  - [ ] SubTask 4.2: 创建 `_close_long()` 方法独平多单（含盈亏计算）
  - [ ] SubTask 4.3: 添加做多独立冷却期计数器 `self.long_last_signal_info`
  - [ ] SubTask 4.4: 修改 `_buy_with_reason()` 适配独立的做多仓位状态

- [ ] Task 5: 实现独立的做空仓位管理（开仓、加仓、平仓）
  - [ ] SubTask 5.1: 创建 `_open_short()` 方法独立开空单
  - [ ] SubTask 5.2: 修改 `_close_short_position()` 适配独立的做空仓位状态
  - [ ] SubTask 5.3: 添加做空独立冷却期计数器 `self.short_last_signal_info`
  - [ ] SubTask 5.4: 确认 `_sell_with_reason()` 开空逻辑正确

- [ ] Task 6: 修改 chan_strategy.py 信号生成支持独立多空信号
  - [ ] SubTask 6.1: 拆分 `self.signal_cooldown_bars` 为 `long_signal_cooldown_bars` 和 `short_signal_cooldown_bars`
  - [ ] SubTask 6.2: 拆分 `self.last_signal_info` 为 `self.long_last_signal_info` 和 `self.short_last_signal_info`
  - [ ] SubTask 6.3: 修改 `generate_signal()` 中 BUY 信号只操作做多系统，SELL 信号只操作做空系统
  - [ ] SubTask 6.4: 移除 `generate_signal()` 中"平仓+反向开仓"的耦合代码

- [ ] Task 7: 适配资金费用计算到双仓位模式
  - [ ] SubTask 7.1: 修改 `FundingFeeCalculator.check_settlement()` 支持传入 long_position 和 short_position
  - [ ] SubTask 7.2: 修改 `_settle_funding_fee()` 分别计算多空资金费用
  - [ ] SubTask 7.3: 汇总多空资金费用后统一调整余额

- [ ] Task 8: 更新回测结果和图表展示
  - [ ] SubTask 8.1: 修改 `_calculate_performance()` 输出独立的做多做空统计
  - [ ] SubTask 8.2: 修改 `print_summary()` 分开展示做多做空交易明细
  - [ ] SubTask 8.3: 修改 `chan_plotter.py` 使用不同颜色标记做多做空信号（如红色多单信号/绿色空单信号）
  - [ ] SubTask 8.4: 跟踪录支持标记每条交易属于做多还是做空

- [ ] Task 9: 整合测试与验证
  - [ ] SubTask 9.1: 使用60天ETHUSDT 30分钟数据进行完整回测
  - [ ] SubTask 9.2: 验证做多做空信号是否独立生成且互不影响
  - [ ] SubTask 9.3: 验证独立止盈止损是否正确触发
  - [ ] SubTask 9.4: 对比分离前后的交易次数和收益率变化
  - [ ] SubTask 9.5: 验证同时持有做多做空仓位时的权益计算正确性

# Task Dependencies
- [Task 1] 是所有后续任务的基础，必须最先完成
- [Task 2] 和 [Task 3] 依赖 [Task 1]，可并行开发
- [Task 4] 和 [Task 5] 依赖 [Task 1] + [Task 2] + [Task 3]，可并行开发
- [Task 6] 依赖 [Task 4] + [Task 5]
- [Task 7] 依赖 [Task 1]，可较早开始
- [Task 8] 依赖 [Task 1]~[Task 6]
- [Task 9] 必须等待所有任务完成后执行
