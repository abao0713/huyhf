# 提前入场优先级提升 Spec

## Why
当前 `_generate_signal_internal` 中标准入场信号（`PROBE_ENTRY`）优先于提前入场信号（`EARLY_ENTRY`），导致提前入场永远被标准信号"挡住"，无法触发。需要将提前入场提升为最高优先级，并调整仓位分配比例。

## What Changes
- **优先级反转**：`_generate_signal_internal` 中提前入场（EARLY_ENTRY/EARLY_SHORT_ENTRY）先于标准入场（PROBE_ENTRY）检测和执行
- **仓位调整**：`early_entry_ratio` 默认值从 0.25 改为 0.40，`early_short_entry_ratio` 同步修改
- **标准加仓调整**：当提前入场先触发后，K3确认加仓使用剩余 60%（`self.investment_ratio - early_entry_ratio`），而非 `confirm_ratio`
- 做多/做空双向保持镜像对称

## Impact
- Affected specs: `simplify_15m_entry_conditions`
- Affected code: `mtf_fractal_strategy.py`（`_generate_signal_internal` + ratio defaults），`run_ethusdc_mtf_backtest.py`（display update）

---

## MODIFIED Requirements

### Requirement: 提前入场优先级最高
系统 SHALL 在无持仓状态下**优先检测提前入场信号**，标准入场仅在提前入场未触发时才执行。

**变更前**（标准优先）:
```
无持仓 → 标准做多/做空 → 命中则return → 提前做多/做空
```

**变更后**（提前优先）:
```
无持仓 → 提前做多/做空 → 命中则return → 标准做多/做空
```

#### Scenario: 提前入场命中
- **WHEN** 无持仓，15分钟3条件满足 >=2（底背驰/二买/趋势向上）
- **THEN** 生成 `EARLY_ENTRY` 信号，`position_ratio=0.40`
- **AND** 跳过标准入场检测

#### Scenario: 提前入场未命中，标准入场命中
- **WHEN** 无持仓，提前入场未触发，但4h底分型+支撑区+30m信号满足
- **THEN** 生成标准 `PROBE_ENTRY` 信号

#### Scenario: 提前做空命中
- **WHEN** 无持仓，15分钟3条件满足 >=2（顶背驰/二卖/趋势向下）
- **THEN** 生成 `EARLY_SHORT_ENTRY` 信号，`position_ratio=0.40`
- **AND** 跳过标准做空检测

### Requirement: 提前入场仓位比例调整为40%
系统 SHALL 将 `early_entry_ratio` 和 `early_short_entry_ratio` 默认值从 `0.25` 改为 `0.40`。

#### Scenario: 默认仓位
- **WHEN** 未指定 `early_entry_ratio`
- **THEN** 默认值为 `0.40`（可执行资金的40%）

### Requirement: 提前入场后的标准加仓使用剩余仓位
当提前入场先触发后持仓，K3确认时系统 SHALL 使用 `self.investment_ratio - early_entry_ratio`（即 0.60）作为加仓比例，而非 `confirm_ratio`。

#### Scenario: 提前入场→K3确认加仓（做多）
- **WHEN** 已持有提前入场多仓（40%），K3收盘确认
- **THEN** 加仓比例 = `investment_ratio - early_entry_ratio` = 0.60
- **AND** 总计仓位 = 100% 可执行资金

#### Scenario: 无提前入场，仅标准入场
- **WHEN** 提前入场未触发，标准入场单独触发
- **THEN** 使用 `probe_ratio` 作为入场仓位
- **AND** 后续 K3 确认仍使用 `confirm_ratio` 加仓

---

## ADDED Requirements

### Requirement: 双向提前入场冲突处理
当提前做多和提前做空同时命中时，系统 SHALL 按 `satisfied_count` 比较，选择满足条件更多的方向。

#### Scenario: 做多3条件 vs 做空2条件
- **WHEN** 提前做多满足3条件，提前做空满足2条件
- **THEN** 选择提前做多（3 > 2）