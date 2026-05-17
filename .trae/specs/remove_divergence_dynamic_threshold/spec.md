# 移除背离信号 + 动态支撑阻力阈值 Spec

## Why
当前MTF策略中30m背离信号（底背离/顶背离）实际触发率极低，且背离检测需要MACD柱与价格做对比，计算复杂但信号质量不高。支撑/阻力区域的固定阈值10不适用于不同价格区间的波动环境，需改为动态计算。投入金额占比需从10%提升至50%以提高资金利用率。

## What Changes
- 从30m做多确认信号中移除 `divergence`（底背离）
- 从30m做空确认信号中移除 `top_divergence`（顶背离）
- `_check_30m_divergence()` 和 `_check_30m_top_divergence()` 方法保留但不参与信号计数
- 支撑/阻力区域阈值从固定 `10.0` 改为基于当前价格波动率动态计算，上限不超过当前价格的1%
- 投入金额占总金额比例从 `0.10` 提升至 `0.50`（50%）

## Impact
- Affected specs: diagnose_mtf_zero_signals
- Affected code: `trading_system/strategies/mtf_fractal_strategy.py`

## MODIFIED Requirements

### Requirement: 30m做多确认信号
30m做多确认信号列表 SHALL 从4种缩减为3种：
- ~~divergence（底背离）~~ → 移除
- bullish_candlestick（看涨K线形态）
- trendline_break（突破下降趋势线）
- golden_cross（金叉：MACD金叉 或 KDJ低位金叉）

#### Scenario: 做多信号检测不包含背离
- **WHEN** `_check_30m_signals()` 被调用
- **THEN** 返回的信号字典中 `divergence` 键固定为 `False`
- **AND** 信号计数不再将背离纳入统计

### Requirement: 30m做空确认信号
30m做空确认信号列表 SHALL 从4种缩减为3种：
- ~~top_divergence（顶背离）~~ → 移除
- bearish_candlestick（看跌K线形态）
- trendline_break_down（跌破上升趋势线）
- death_cross（死叉：MACD死叉 或 KDJ高位死叉）

#### Scenario: 做空信号检测不包含顶背离
- **WHEN** `_check_30m_short_signals()` 被调用
- **THEN** 返回的信号字典中 `top_divergence` 键固定为 `False`
- **AND** 信号计数不再将顶背离纳入统计

### Requirement: 动态支撑/阻力阈值
支撑区域检查 `_check_support_zone()` 和阻力区域检查 `_check_resistance_zone()` SHALL 使用动态阈值替代固定值10.0。

阈值计算规则：
```
dynamic_threshold = min(ATR * 0.5, current_price * 0.01)
```
即：取 ATR的一半 和 当前价格1% 中的较小值。

#### Scenario: 波动率低时阈值由ATR决定
- **WHEN** 当前ATR=30，价格=2300
- **THEN** 阈值 = min(30*0.5, 2300*0.01) = min(15, 23) = 15

#### Scenario: 波动率高时阈值受1%上限限制
- **WHEN** 当前ATR=120，价格=2200
- **THEN** 阈值 = min(120*0.5, 2200*0.01) = min(60, 22) = 22

#### Scenario: ATR不可用时回退
- **WHEN** `current_atr` 为 0 或 None
- **THEN** 阈值 = `current_price * 0.01`（回退为1%价格）

### Requirement: 阈值参数保留
`support_threshold` 和 `resistance_threshold` 参数在 `__init__` 中保留，但默认值不再使用。当 `current_atr` 不可用且无法计算时，回退到原固定阈值。

## REMOVED Requirements

### Requirement: 30m背离信号参与入场确认
**Reason**: 背离信号在实际回测中触发率极低，增加复杂度但贡献不大的信号
**Migration**: `_check_30m_divergence()` 和 `_check_30m_top_divergence()` 方法代码保留在文件中（防止其他模块引用），但不再被 `_check_30m_signals()` 和 `_check_30m_short_signals()` 调用

### Requirement: 策略投入金额占比
策略的 `investment_ratio` 默认值 SHALL 从 `0.10` 改为 `0.50`，即每次开仓时投入金额占总金额的50%。回测运行脚本 `run_ethusdc_mtf_backtest.py` 中的 `INVESTMENT_RATIO` 常量 SHALL 同步改为 `0.50`。

#### Scenario: 开仓时使用50%资金
- **WHEN** 策略生成 PROBE_ENTRY 信号
- **THEN** 回测引擎计算仓位时使用 `balance * 0.50 * probe_ratio(0.4)` = `balance * 0.20`（20%总资金作为试探仓）