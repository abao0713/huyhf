# 多空订单分离 Spec

## Why
当前策略采用连续循环交易模式（做多→平仓→做空→平仓→做多...），多空共用一个持仓状态（position）。这导致：
1. 无法同时持有做多和做空仓位进行对冲
2. 做多和做空共用同一套止盈止损逻辑，无法差异化配置
3. 平仓一个方向后强制开反向仓，缺乏灵活性

需要将多空双向订单完全分离为独立的交易系统，各自管理仓位、止盈和止损。

## What Changes
- **修改**：将单一 `self.position` 拆分为 `self.long_position`（多单仓位）和 `self.short_position`（空单仓位）
- **新增**：独立的做多止盈止损参数（`long_stop_loss`, `long_take_profit`, `long_trailing_stop`）
- **新增**：独立的做空止盈止损参数（`short_stop_loss`, `short_take_profit`, `short_trailing_stop`）
- **新增**：支持同时持有多空仓位（对冲模式）
- **修改**：BUY信号只影响做多系统，SELL信号只影响做空系统，不再互相联动
- **修改**：移除"平仓后自动反向开仓"的强耦合逻辑，改为各自独立决策

## Impact
- Affected specs: `limit_order_funding_fee_optimization`
- Affected code:
  - `trading_system/strategies/chan_strategy.py` - 信号生成逻辑改为独立多空信号
  - `trading_system/strategies/backtest_engine.py` - 回测引擎支持双仓位管理
  - `trading_system/utils/chan_plotter.py` - 图表支持独立多空标记

## ADDED Requirements

### Requirement: 多空仓位分离
系统 SHALL 将做多和做空作为两个独立的交易子系统，各自维护独立的仓位状态。

#### Scenario: 底背驰触发做多
- **WHEN** 策略检测到底背驰信号
- **THEN** 生成做多信号，只影响 `long_position` 和做多相关参数
- **AND** 不影响做空仓位（`short_position` 保持不变）

#### Scenario: 顶背驰触发做空
- **WHEN** 策略检测到顶背驰信号
- **THEN** 生成做空信号，只影响 `short_position` 和做空相关参数
- **AND** 不影响做多仓位（`long_position` 保持不变）

#### Scenario: 同时持有多空仓位
- **WHEN** 多单和空单同时持有
- **THEN** 系统 SHALL 正确计算两个方向的浮动盈亏
- **AND** 权益 = 余额 + 多单浮动盈亏 + 空单浮动盈亏

### Requirement: 独立的止盈止损配置
系统 SHALL 为做多和做空分别提供独立的止盈止损参数配置。

#### Scenario: 做多止盈
- **WHEN** 多单持仓且价格上涨达到 `long_take_profit_ratio`（如 +5%）
- **THEN** 触发做多止盈，平多单
- **AND** 不影响做空仓位

#### Scenario: 做多止损
- **WHEN** 多单持仓且价格下跌达到 `long_stop_loss_ratio`（如 -3%）
- **THEN** 触发做多止损，平多单
- **AND** 不影响做空仓位

#### Scenario: 做空止盈
- **WHEN** 空单持仓且价格下跌达到 `short_take_profit_ratio`（如 +5%）
- **THEN** 触发做空止盈，平空单
- **AND** 不影响做多仓位

#### Scenario: 做空止损
- **WHEN** 空单持仓且价格上涨达到 `short_stop_loss_ratio`（如 -3%）
- **THEN** 触发做空止损，平空单
- **AND** 不影响做多仓位

### Requirement: 独立追踪止损
系统 SHALL 为做多和做空分别维护独立的追踪止损线。

#### Scenario: 做多追踪止损上移
- **WHEN** 多单持仓期间价格创新高
- **THEN** 做多追踪止损位向上移动（锁利）
- **AND** 不影响做空追踪止损位

#### Scenario: 做空追踪止损下移
- **WHEN** 空单持仓期间价格创新低
- **THEN** 做空追踪止损位向下移动（锁利）
- **AND** 不影响做多追踪止损位

### Requirement: 做多仓位管理
系统 SHALL 为做多交易提供独立的开仓、加仓和平仓管理。

#### Scenario: 开做多仓位
- **WHEN** 底背驰信号 + 做多冷却期通过 + 波动率正常 + 做多盈亏比达标
- **THEN** 按做多专属配置开多单
- **AND** 使用 `long_position_size_ratio` 计算仓位规模

#### Scenario: 做多信号冷却期
- **WHEN** 上次做多信号在 `long_signal_cooldown_bars` 根K线内
- **THEN** 跳过本次做多信号
- **AND** 不影响做空信号冷却期

### Requirement: 做空仓位管理
系统 SHALL 为做空交易提供独立的开仓、加仓和平仓管理。

#### Scenario: 开做空仓位
- **WHEN** 顶背驰信号 + 做空冷却期通过 + 波动率正常 + 做空盈亏比达标
- **THEN** 按做空专属配置开空单
- **AND** 使用 `short_position_size_ratio` 计算仓位规模

#### Scenario: 做空信号冷却期
- **WHEN** 上次做空信号在 `short_signal_cooldown_bars` 根K线内
- **THEN** 跳过本次做空信号
- **AND** 不影响做多信号冷却期

## MODIFIED Requirements

### Requirement: 资金费用计算（适配双仓位）
原资金费用计算需适配双仓位模式：
- **原逻辑**：根据单一 `position` 计算资金费用
- **新逻辑**：分别对 `long_position` 和 `short_position` 计算资金费用并汇总

### Requirement: 信号生成（不再强耦合）
- **原逻辑**：平仓+反向开仓绑定在同一信号处理流程中
- **新逻辑**：BUY信号只关做多，SELL信号只关做空，各自独立调用

## REMOVED Requirements

### Requirement: 自动反向开仓
**Reason**：多空分离后，不再需要"平多自动开空/平空自动开多"的强耦合逻辑
**Migration**：移除 `_open_short_position()` 和 `_open_long_position()` 的自动调用，改为各自独立的信号决策
