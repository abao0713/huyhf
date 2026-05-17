# MTF做空信号回测修复 Spec

## Why
MTF回测（2026-02-14 ~ 2026-05-15）期间仅检测了做多信号，做空信号完全未被评估。原因：默认阻力位 `[2100,2150,2200,2250,2300]` 远高于回测期间实际价格区间（~1900-2100），`_check_resistance_zone()` 从未返回True，导致 `_generate_short_entry_signal()` 在第一行就返回None。此外，长仓风控（连续止损暂停/日亏损停止）也未对做空方向生效。

## What Changes
- **MODIFIED** `run_ethusdc_mtf_backtest.py`：调整默认支撑/阻力位，使其与回测期间实际价格区间匹配
- **MODIFIED** `run_backtest.py`：调整默认支撑/阻力位参数默认值
- **MODIFIED** `mtf_fractal_strategy.py`：确保长仓风控（连续止损暂停）对做空方向同样生效（当前 `on_stop_loss()` 中断所有交易但只在长仓路径调用）

## Impact
- Affected specs: `optimize_mtf_backtest`
- Affected code:
  - `run_ethusdc_mtf_backtest.py` (默认参数调整)
  - `run_backtest.py` (默认参数调整)
  - `mtf_fractal_strategy.py` (做空止损风控对称)

## MODIFIED Requirements

### Requirement: 支撑/阻力位匹配回测期间价格区间
系统 SHALL 提供与回测期间实际价格范围匹配的默认支撑/阻力位，使多空两个方向均有可触发条件。

#### Scenario: 回测期间做空信号可见
- **GIVEN** 回测期间（2026-02-14 ~ 2026-05-15）ETH价格区间 ~1900-2100
- **WHEN** 使用默认参数运行 `run_ethusdc_mtf_backtest.py`
- **THEN** 阻力位应在价格可达范围内（如2050-2150），做空信号能够被检测到

#### Scenario: 回测期间做多信号可见
- **GIVEN** 同上价格区间
- **WHEN** 使用默认参数运行回测
- **THEN** 支撑位应在价格可达范围内（如1900-2000），做多信号能够被检测到

### Requirement: 做空止损风控触发
做空方向的止损 SHALL 触发 `on_stop_loss()` 风控机制（连续止损计数、交易暂停）。

#### Scenario: 做空止损后风控生效
- **GIVEN** 持有short仓位，触发止损
- **WHEN** 做空止损执行
- **THEN** `on_stop_loss()` 被调用，连续止损计数+1，达到阈值后暂停所有交易