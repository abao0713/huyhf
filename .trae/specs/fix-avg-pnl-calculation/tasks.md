# Tasks

- [x] Task 1: 修复 `_build_closed_trades()` 的重复匹配缺陷
  - [x] 引入 `matched_entry_indices: set` 跟踪已被匹配的 entry trade 索引
  - [x] 引入 `entry_to_exits: dict` 将同一 entry 的多个 exit 聚合（key=entry在self.trades中的位置）
  - [x] 遍历：先收集同一 entry 的所有 exit，再一次性生成一个 ClosedTrade
  - [x] 聚合算法按 spec 实现：profit 求和，return_pct 基于 entry 总成本重新计算

- [x] Task 2: 语法检查
  - [x] `python -m py_compile trading_system/strategies/backtest_engine.py`

- [x] Task 3: 运行回测验证指标正确性
  - [x] `python run_ethusdc_mtf_backtest.py`
  - [x] 验证 "平均每笔盈亏" 与 "净利润/已平仓交易" 一致 → $312.43 = $5,936.08 / 19 ✓
  - [x] avg_profit 计算改为 `net_profit / len(closed_trades)` 以消除杠杆化 TradeRecord.profit 与实际余额变化之间的系统性差异

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2