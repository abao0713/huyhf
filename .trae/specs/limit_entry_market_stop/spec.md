# 入场/加仓走限价单、止损走市价单 Spec

## Why
当前 `mtf_fractal_strategy.py` 中所有 8 处 `place_order` 调用均使用 `MARKET`（市价单）。用户要求：**入场开仓和加仓使用 LIMIT（限价单）避免滑点，止损平仓使用 MARKET（市价单）确保立即成交**。

## 现状分析

| 序号 | 函数 | 场景 | 当前类型 | 要求 |
|------|------|------|----------|------|
| 1 | `_open_long_probe` | 试探开多 | MARKET | LIMIT |
| 2 | `_add_long_confirm` | 确认加仓(多) | MARKET | LIMIT |
| 3 | `_open_early_entry` | 提前入场做多 | MARKET | LIMIT |
| 4 | `_open_early_short_entry` | 提前入场做空 | MARKET | LIMIT |
| 5 | `_open_short_probe` | 试探开空 | MARKET | LIMIT |
| 6 | `_add_short_confirm` | 确认加仓(空) | MARKET | LIMIT |
| 7 | `_close_all_long` | 平多单(止损) | MARKET | MARKET ✅ |
| 8 | `_close_all_short` | 平空单(止损) | MARKET | MARKET ✅ |

## What Changes
- 6 处入场/加仓 `place_order` 调用的 `order_type` 从 `"MARKET"` 改为 `"LIMIT"`，并传入 `price` 参数
- 2 处止损平仓调用保持不变（已为 MARKET）

## Impact
- Affected specs: none
- Affected code: `trading_system/strategies/mtf_fractal_strategy.py`

## MODIFIED Requirements
### Requirement: 入场和加仓使用限价单
入场开仓（试探开多/空、提前入场做多/空）和加仓（确认加仓做多/空）SHALL 使用 LIMIT 限价单下单，价格使用信号中传入的 entry price，避免滑点。

#### Scenario: 试探入场使用限价单
- **WHEN** 策略触发试探入场信号（PROBE_ENTRY / PROBE_ENTRY_SHORT）
- **THEN** `place_order` 调用传入 `order_type="LIMIT"` 和 `price=<entry_price>`
- **AND** 止损平仓调用仍使用 `order_type="MARKET"`

#### Scenario: 确认加仓使用限价单
- **WHEN** 策略触发确认加仓信号（CONFIRM_ADD / CONFIRM_ADD_SHORT）
- **THEN** `place_order` 调用传入 `order_type="LIMIT"` 和 `price=<entry_price>`

#### Scenario: 提前入场使用限价单
- **WHEN** 策略触发提前入场信号（EARLY_ENTRY / EARLY_SHORT_ENTRY）
- **THEN** `place_order` 调用传入 `order_type="LIMIT"` 和 `price=<entry_price>`

### Requirement: 止损平仓保持市价单
止损平仓（CLOSE_LONG / CLOSE_SHORT）SHALL 继续使用 MARKET 市价单，确保立即成交。

#### Scenario: 止损平多单使用市价单
- **WHEN** 策略触发止损平多单信号
- **THEN** `place_order` 调用传入 `order_type="MARKET"`（不变）

#### Scenario: 止损平空单使用市价单
- **WHEN** 策略触发止损平空单信号
- **THEN** `place_order` 调用传入 `order_type="MARKET"`（不变）