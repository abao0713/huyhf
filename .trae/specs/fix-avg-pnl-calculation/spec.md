# 修复平均每笔盈亏计算 Spec

## Why
`_build_closed_trades()` 的 BUY→SELL 配对逻辑存在缺陷：同一笔入场（BUY）可能被多个出场（SELL）重复匹配（如PARTIAL_CLOSE→平60% + 后续止损→平40%），导致已平仓交易数量虚增，`avg_profit`、`profit_factor`、`win_rate` 等指标全部失真。

## What Changes
- 修复 `_build_closed_trades()` 的配对逻辑：已匹配过的 entry trade 不应再被后续 exit trade 匹配
- PARTIAL_CLOSE 类型的部分平仓不应独立生成 ClosedTrade，等最终全平时聚合为一个完整的 round-trip
- `avg_profit`（平均每笔盈亏）、`profit_factor`（盈利因子）、`win_rate`（胜率）随之自动修正

## Impact
- Affected specs: 无
- Affected code: [backtest_engine.py](file:///e:/Auto_test/huyhf/trading_system/strategies/backtest_engine.py) - `_build_closed_trades()` (L2202-2268), `_calculate_performance()` 不变

## MODIFIED Requirements

### Requirement: `_build_closed_trades` 不应让同一 entry 被多次匹配
`_build_closed_trades()` 在遍历 `self.trades` 寻找 entry_trade 时，SHALL 将已匹配过的 entry trade 排除，确保每个 entry 最多对应一个 ClosedTrade。

#### Scenario: PARTIAL_CLOSE 后接全平
- **GIVEN** 一笔 BUY 入场（amount=10, profit=0）
- **AND** 一笔 PARTIAL_CLOSE_LONG 出场平60%（amount=6, profit=+30）
- **AND** 一笔止损出场平剩余40%（amount=4, profit=-50）
- **WHEN** `_build_closed_trades()` 被调用
- **THEN** 只生成**1个** ClosedTrade（而非2个）
- **AND** ClosedTrade.profit = (+30) + (-50) = -20（两段盈亏之和）
- **AND** ClosedTrade.return_pct = -20 / (10 * entry_price) * 100

#### Scenario: 标准一次全平（无PARTIAL_CLOSE）
- **GIVEN** 一笔 BUY 入场（profit=0）
- **AND** 一笔 SELL 出场（profit=+100）
- **WHEN** `_build_closed_trades()` 被调用
- **THEN** 生成**1个** ClosedTrade
- **AND** 行为与修复前一致

#### Scenario: 连续多笔交易互不干扰
- **GIVEN** BUY1 → SELL1（全平）, BUY2 → PARTIAL_CLOSE → SELL2（全平）
- **WHEN** `_build_closed_trades()` 被调用
- **THEN** 生成**2个** ClosedTrade（对应两笔独立入场）
- **AND** BUY2 的两段出场聚合为一个 ClosedTrade

### Requirement: 聚合算法
对于被同一 entry 匹配的多个 exit：
- **profit** = 所有 exit 的 `trade.profit` 之和
- **return_pct** = sum(profit) / (entry.amount * entry.price) * 100
- **exit_time** = 最后一个 exit 的 timestamp
- **exit_price** = 最后一个 exit 的 price
- **amount** = entry.amount（整笔入场的数量）
- **holding_hours** = 最后一个 exit 的 timestamp - entry.timestamp
- **stop_loss_hit** / **take_profit_hit** = 任一 exit 满足即 True