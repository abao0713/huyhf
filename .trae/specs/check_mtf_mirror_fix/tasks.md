# Tasks

## 修复顶分型做空镜像功能

- [x] Task 1: 实现4小时顶分型K1/K2结构检测方法 `_check_4h_top_fractal_k1k2`
  - [x] 检查K1: close > open (上涨K线)
  - [x] 检查K2: high > K1.high
  - [x] 检查K3候选: high < K2.high
  - [x] 计算置信度
  - [x] 检查K3是否在后半段

- [x] Task 2: 实现15分钟一卖检测方法 `_check_15m_first_sell`
  - [x] 调用 _chan_first_sell_analyzer.analyze_sell()
  - [x] 返回 divergence_confirmed 结果
  - [x] 返回详细分析信息

- [x] Task 3: 实现15分钟二卖检测方法 `_check_15m_second_sell`
  - [x] 找到近期高点
  - [x] 确认反弹高点低于一卖高点
  - [x] 确认反弹高点低于K2高点
  - [x] 计算置信度

- [x] Task 4: 实现15分钟趋势向下确认方法 `_check_15m_downtrend`
  - [x] MA5 < MA20 < MA60
  - [x] 近期高点降低（LH < HL）
  - [x] 出现连续阴线

- [x] Task 5: 实现提前入场做空信号生成方法 `_generate_early_short_entry_signal`
  - [x] 检查 enable_early_short_entry 参数
  - [x] 检查15分钟数据
  - [x] 检测K1/K2结构
  - [x] 检测15分钟一卖、二卖
  - [x] 确认趋势向下
  - [x] 计算置信度
  - [x] 生成 EARLY_SHORT_ENTRY 信号

- [x] Task 6: 实现提前做空订单执行方法 `_open_early_short_entry`（Executor）
  - [x] 计算仓位数量
  - [x] 执行做空市价单
  - [x] 更新持仓状态

- [x] Task 7: 修改 `update_position_from_signal()` 支持 early_short_entry
  - [x] 添加 elif sig_type == "early_short_entry" 分支
  - [x] 设置 direction = "short"
  - [x] 设置相关索引和止损

- [x] Task 8: 修改 `_execute_signal()` 支持 EARLY_SHORT_ENTRY
  - [x] 添加 elif action == "EARLY_SHORT_ENTRY" 分支
  - [x] 调用 _open_early_short_entry

- [x] Task 9: 语法检查和验证
  - [x] 运行 python -m py_compile 检查语法
  - [x] 确认所有方法正确实现

# Task Dependencies
- Task 6, 7, 8 依赖 Task 1, 2, 3, 4, 5 - ✅ 已完成
- Task 9 依赖 Task 1-8 - ✅ 已完成
