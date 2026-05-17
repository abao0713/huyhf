# 简化15分钟入场条件 Spec

## Why
当前策略的15分钟提前入场分析依赖 `ChanTheoryFirstBuyAnalyzer` 进行一买/一卖检测（需要完整的分型→笔→线段→中枢结构分析），条件过于严格导致回测中提前入场信号基本不触发（satisfied_count=0）。需要将一买/一卖检测简化为直接的15分钟K线分析，同时将入场逻辑从"置信度加权"改为"3条件满足2个"的更灵活模型。

## What Changes
- **移除** `_check_15m_first_buy()` 对 `ChanTheoryFirstBuyAnalyzer.analyze()` 的依赖，改为直接15分钟K线底背驰检测
- **移除** `_check_15m_first_sell()` 对 `ChanTheoryFirstBuyAnalyzer.analyze_sell()` 的依赖，改为直接15分钟K线顶背驰检测
- **重构** `_generate_early_entry_signal()` 入场逻辑：3条件（一买/二买/趋势向上）满足 ≥2 即触发
- **重构** `_generate_early_short_entry_signal()` 入场逻辑：3条件（一卖/二卖/趋势向下）满足 ≥2 即触发
- **新增** `min_early_entry_conditions` 可配置参数（默认 2）
- 移除 `early_entry_min_confidence` / `early_short_entry_min_confidence` 置信度阈值（由条件计数替代）
- 做多和做空保持镜像对称

## Impact
- Affected specs: multi_tf_fractal_strategy, check_mtf_mirror_fix
- Affected code: `mtf_fractal_strategy.py`（核心修改），`run_ethusdc_mtf_backtest.py`（参数同步）

---

## ADDED Requirements

### Requirement: 15分钟底背驰直接检测（做多）
系统 SHALL 在15分钟K线上直接检测底背驰，无需依赖 `ChanTheoryFirstBuyAnalyzer`。

#### Scenario: MACD底背驰检测
- **WHEN** 15分钟数据 >= 50 根K线
- **THEN** 计算 MACD(12,26,9)，检测最近两个低点之间：
  - 价格低点降低（新低 < 前低）
  - MACD DIF 低点抬高（新低 DIF > 前低 DIF）
  - 两个条件同时满足 → 底背驰成立
- **AND** 返回 `(True, details_dict)`

#### Scenario: 数据不足
- **WHEN** 15分钟数据 < 50 根K线
- **THEN** 返回 `(False, {})`

### Requirement: 15分钟顶背驰直接检测（做空）
系统 SHALL 在15分钟K线上直接检测顶背驰，无需依赖 `ChanTheoryFirstBuyAnalyzer`。

#### Scenario: MACD顶背驰检测
- **WHEN** 15分钟数据 >= 50 根K线
- **THEN** 计算 MACD(12,26,9)，检测最近两个高点之间：
  - 价格高点抬高（新高 > 前高）
  - MACD DIF 高点降低（新高 DIF < 前高 DIF）
  - 两个条件同时满足 → 顶背驰成立
- **AND** 返回 `(True, details_dict)`

#### Scenario: 数据不足
- **WHEN** 15分钟数据 < 50 根K线
- **THEN** 返回 `(False, {})`

### Requirement: 3取2入场模型（做多）
系统 SHALL 在提前入场做多时使用3取2条件模型。

#### Scenario: 3个条件均满足
- **WHEN** 一买（底背驰）=True, 二买（回调不破前低）=True, 趋势向上=True
- **THEN** 满足数=3 >= min_early_entry_conditions(2)，生成 `EARLY_ENTRY` 信号

#### Scenario: 2个条件满足
- **WHEN** 一买=True, 二买=False, 趋势向上=True
- **THEN** 满足数=2 >= 2，生成 `EARLY_ENTRY` 信号

#### Scenario: 仅1个条件满足
- **WHEN** 一买=False, 二买=False, 趋势向上=True
- **THEN** 满足数=1 < 2，不生成信号

### Requirement: 3取2入场模型（做空）
系统 SHALL 在提前入场做空时使用3取2条件模型。

#### Scenario: 2个条件满足
- **WHEN** 一卖=True, 二卖=False, 趋势向下=True
- **THEN** 满足数=2 >= 2，生成 `EARLY_SHORT_ENTRY` 信号

#### Scenario: 仅1个条件满足
- **WHEN** 一卖=False, 二卖=True, 趋势向下=False
- **THEN** 满足数=1 < 2，不生成信号

### Requirement: min_early_entry_conditions 可配置
系统 SHALL 支持通过 `min_early_entry_conditions` 参数配置入场所需的最少条件数。

#### Scenario: 默认值
- **WHEN** 未指定 `min_early_entry_conditions`
- **THEN** 默认值为 2

#### Scenario: 自定义为3
- **WHEN** `min_early_entry_conditions=3`
- **THEN** 需要一买+二买+趋势全部满足才入场

---

## REMOVED Requirements

### Requirement: ChanTheoryFirstBuyAnalyzer 用于15分钟一买/一卖检测
**Reason**: 条件过于严格，需要完整缠论结构（分型→笔→线段→中枢），在15分钟级别难以满足，导致提前入场信号基本不触发。
**Migration**: `_check_15m_first_buy()` 和 `_check_15m_first_sell()` 改为直接MACD背驰检测。`ChanTheoryFirstBuyAnalyzer` 的 import 和实例化代码保留但不再用于15分钟提前入场分析（其他标准入场逻辑不受影响）。

### Requirement: early_entry_min_confidence / early_short_entry_min_confidence 置信度阈值
**Reason**: 由3取2条件计数模型替代，不再需要置信度加权计算。
**Migration**: 参数定义保留但标记为废弃，默认值不影响新逻辑。

---

## MODIFIED Requirements

### Requirement: _generate_early_entry_signal 入场逻辑
系统 SHALL 使用3取2条件模型替代置信度加权模型。

**变更前**: 一买+0.4, 二买+0.4, 趋势+0.3, 合计 >= min_confidence 且 (一买或二买) 必须为True
**变更后**: 一买/二买/趋势向上 三个条件独立判断，满足数 >= min_early_entry_conditions(默认2)

### Requirement: _generate_early_short_entry_signal 入场逻辑
系统 SHALL 使用3取2条件模型替代置信度加权模型。

**变更前**: 一卖+0.4, 二卖+0.4, 趋势+0.3, 合计 >= min_confidence 且 (一卖或二卖) 必须为True
**变更后**: 一卖/二卖/趋势向下 三个条件独立判断，满足数 >= min_early_entry_conditions(默认2)