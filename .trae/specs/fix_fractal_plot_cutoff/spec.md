# 回测图表分型显示不完整修复 Spec

## Why
MTF回测图表中，从K线索引700处开始就没有顶分型和底分型标识了。根因是：Chan策略默认开启 **包含合并**(`use_inclusion_merge=True`)，将1000根K线合并缩减为约700根。分型索引基于合并后的数据，但回测引擎检测到MTF策略没有 `df_processed` 属性，回退使用原始raw data（1000根）绘制K线，导致：
- K线x轴范围：0-999（原始1000根）
- 分型x轴范围：仅0-699（合并后~700根）

造成700之后的K线区域无分型标识的视觉断崖。

## What Changes
- **MODIFIED** `mtf_fractal_strategy.py`：在 `inject_data()` 中将 `_chan.df_processed` 传播到 `self.df_processed`，使回测引擎的 `hasattr(strategy, 'df_processed')` 检测生效，K线和分型使用同一份合并后数据
- **MODIFIED** `mtf_fractal_strategy.py`：在 `_process_data()` 中同样传播 `df_processed`

## Impact
- Affected specs: `optimize_mtf_backtest`, `fix_mtf_short_signal_backtest`
- Affected code: `mtf_fractal_strategy.py`

## MODIFIED Requirements

### Requirement: K线图表与分型数据索引一致
系统 SHALL 确保回测图表中K线数据与分型数据使用相同的数据集（合并后或原始），索引对齐。

#### Scenario: 图表分型覆盖完整
- **GIVEN** MTF策略运行90天回测
- **WHEN** 回测引擎生成图表
- **THEN** `strategy.df_processed` 与 `strategy.fractals` 使用相同索引的合并后数据
- **THEN** 分型标识从第一个到最后一个K线均匀分布，无视觉断崖

#### Scenario: 分型数量与K线数一致
- **GIVEN** 包含合并后 df_processed 有 N 根K线
- **WHEN** 分型检测完成
- **THEN** `fractal.idx` 最大值 ≤ N-1，图表上所有分型都在K线范围内