# 缠论买卖点串联策略 + 反向平仓 Spec

## Why
- 五大买卖点（一买/二买/类二买/一卖/二卖/类二卖）的状态机已实现，但存在 `run_backtest.py` 中 argparse `choices` 缺失导致回测被阻塞的 bug
- 用户新增需求：持仓期间检测到反向买卖点需立即平仓止损，避免持有逆势仓位（做多遇到一卖 → 平多；做空遇到一买 → 平空）

## What Changes
- **修复** `run_backtest.py` argparse choices，加入 `"chan_buy_sell"`
- **新增** `generate_signal()` 中的反向平仓逻辑：`LONG_ENTRY / WATCHING_SIMILAR_BUY` 状态下识别到一卖 → 返回 `CLOSE_LONG` 信号；`SHORT_ENTRY / WATCHING_SIMILAR_SELL` 状态下识别到一买 → 返回 `CLOSE_SHORT` 信号
- **新增** `_check_state_transitions()` 中的反向平仓状态回退：一卖触发平多 → 回到 IDLE；一买触发平空 → 回到 IDLE

## Impact
- Affected specs: 无（新建）
- Affected code:
  - `trading_system/backtest/run_backtest.py` (1行修改)
  - `trading_system/strategies/chan_buy_sell_strategy.py` (~30行新增)

## ADDED Requirements

### Requirement: 反向一卖平多仓
When the strategy is holding a LONG position (state = LONG_ENTRY or WATCHING_SIMILAR_BUY) and a 一卖 (First Sell) is confirmed, the system SHALL immediately close all long positions and return to IDLE state.

#### Scenario: 做多持仓中检测到一卖，立即平多
- **GIVEN** 当前状态为 `LONG_ENTRY` 或 `WATCHING_SIMILAR_BUY`（持有多仓）
- **AND** 一卖分析结果中 `fs.divergence_confirmed == True`
- **WHEN** `generate_signal()` 被调用
- **THEN** 返回 `{'action': 'CLOSE_LONG', 'reason': '一卖信号→平多', ...}`
- **AND** `_check_state_transitions()` 中将状态重置为 `IDLE`

### Requirement: 反向一买平空仓
When the strategy is holding a SHORT position (state = SHORT_ENTRY or WATCHING_SIMILAR_SELL) and a 一买 (First Buy) is confirmed, the system SHALL immediately close all short positions and return to IDLE state.

#### Scenario: 做空持仓中检测到一买，立即平空
- **GIVEN** 当前状态为 `SHORT_ENTRY` 或 `WATCHING_SIMILAR_SELL`（持有空仓）
- **AND** 一买分析结果中 `fb.divergence_confirmed == True`
- **WHEN** `generate_signal()` 被调用
- **THEN** 返回 `{'action': 'CLOSE_SHORT', 'reason': '一买信号→平空', ...}`
- **AND** `_check_state_transitions()` 中将状态重置为 `IDLE`

### Requirement: chan_buy_sell 入选 choices 列表
The argparse `--strategy-version` parameter SHALL accept `"chan_buy_sell"` as a valid choice.

#### Scenario: 用户通过 CLI 指定 chan_buy_sell 策略
- **WHEN** 用户执行 `python run_backtest.py --strategy-version chan_buy_sell`
- **THEN** argparse 不会报错，正常解析参数