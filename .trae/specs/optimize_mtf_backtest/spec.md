# MTF策略优化&回测接入 Spec

## Why
当前 `MultiTFFractalStrategy` 存在多个关键缺陷：①固定5美元止损无法自适应市场波动率（ETH价格1800 vs 3500时风险差异巨大）；②分型检测过于简陋（仅看最近3根K线），远不如 ChanStrategyV2 的 hg1=8 严格窗口；③无法接入现有回测引擎（缺少 `load_data_for_backtest`、`generate_signal(bar_idx)` 接口）；④缺少平仓方法无法处理止损执行。需要从 ChanStrategyV2 中提取可复用的能力，优化 MTF 策略并使其能共享回测基础设施。

## What Changes
- **MODIFIED** `MultiTFFractalStrategy` 全面优化：
  - PositionState 从 dict 升级为 dataclass（新增 `avg_entry_price`、`entry_count`）
  - **复用 ChanStrategy 分型引擎**：嵌入 `ChanStrategy` 实例获取 hg1=8 严格分型/笔/线段
  - **ATR 动态止损**：从固定 `stop_offset=5.0` 改为 `entry_price ± current_atr * atr_multiplier`
  - 做多信号增加止盈价和风险回报比检查
  - 做多方向趋势过滤（日线 EMA20 < EMA60 降仓）
  - 做多方向成交量萎缩过滤
  - 添加 `load_data_for_backtest(df_30m, df_15m, df_daily)` 回测入口
  - 添加 `generate_signal(bar_idx)` bar_idx 参数支持
  - 添加 `generate_all_pending_signals(bar_idx)` 批量信号
  - 添加 `extend_cooldown_after_loss()` 回测引擎回调接口
  - 止损爆仓价安全检查
  - 数据处理完成后的摘要日志

- **MODIFIED** `MultiTFFractalStrategyExecutor` 添加平仓方法：
  - 新增 `_close_all_long()`、`_close_all_short()`、`_get_position_quantity()`
  - 新增 `CLOSE_LONG` / `CLOSE_SHORT` 信号类型支持

- **MODIFIED** `run_backtest.py` 新增 MTF 策略回测分支：
  - 检测 `hasattr(strategy, 'load_data_for_backtest')` 自动适配
  - 支持 `--strategy-version mtf` 参数
  - 双周期数据加载（30m + 15m）

- **NEW** `run_ethusdc_mtf_backtest.py` MTF 独立回测脚本：
  - 参考 `run_ethusdc_v2_backtest.py` 结构
  - 共享同一套回测引擎和数据源

## Impact
- Affected specs: `multi_tf_fractal_strategy`、`add_mtf_short_selling`
- Affected code:
  - `trading_system/strategies/mtf_fractal_strategy.py` (重大修改)
  - `run_backtest.py` (新增 MTF 分支)
  - `run_ethusdc_mtf_backtest.py` (新增)

## MODIFIED Requirements

### Requirement: ATR 动态止损替代固定偏移
系统 SHALL 使用 ATR(14) 计算动态止损，替代固定 `stop_offset=5.0`。

#### Scenario: 高波动市场自适应止损
- **GIVEN** ETH 当前价格 = 3500, ATR(14) = 80
- **WHEN** 生成做多信号
- **THEN** 止损 = 入场价 - ATR × atr_multiplier(默认3.5) = 入场价 - 280，而非固定的 -5

#### Scenario: 低波动市场收紧止损
- **GIVEN** ETH 当前价格 = 1800, ATR(14) = 15
- **WHEN** 生成做多信号
- **THEN** 止损 = 入场价 - 52.5，适当收紧止损保护利润

### Requirement: 复用 Chan 分型引擎
系统 SHALL 内部嵌入 `ChanStrategy` 实例，使用 hg1=8 严格窗口识别分型，替代当前仅看3根K线的简易检测。

#### Scenario: 严格分型过滤假信号
- **GIVEN** 30分钟K线出现短暂低点但未满足 hg1=8 确认
- **WHEN** `_chan._find_fractals()` 未识别到分型
- **THEN** MTF 不触发入场，过滤掉假信号

### Requirement: 回测引擎接入
系统 SHALL 实现 `load_data_for_backtest(df_30m, df_15m, df_daily)` 方法，使 `generate_signal()` 接受 `bar_idx` 参数，支持逐K线回测循环。

#### Scenario: 回测模式逐K线调用
- **GIVEN** 已调用 `load_data_for_backtest()` 注入800根30m + 1600根15m K线
- **WHEN** 回测引擎在第400根K线调用 `generate_signal(bar_idx=400)`
- **THEN** 系统只基于第400根K线之前的数据生成信号

### Requirement: 平仓执行方法
系统 SHALL 提供 `_close_all_long()`、`_close_all_short()`、`_get_position_quantity()` 方法，支持止损/反转执行。

#### Scenario: 做空止损平仓
- **GIVEN** 持有 short 仓位，当前价格触发止损
- **WHEN** 系统检测到止损条件
- **THEN** 调用 `_close_all_short()` 平掉所有空单

### Requirement: 双向对称完善
做多方向 SHALL 享有与做空方向对等的止盈计算、趋势过滤、成交量过滤。

#### Scenario: 做多方向的趋势过滤
- **GIVEN** 日线 EMA20 < EMA60（空头趋势）
- **WHEN** 做多信号生成
- **THEN** 仓位降低至原仓位50%，日志记录"逆势做多降仓"

## ADDED Requirements

### Requirement: MTF 独立回测脚本
系统 SHALL 提供 `run_ethusdc_mtf_backtest.py`，支持命令行指定参数日期范围，输出完整的回测报告（收益率、胜率、最大回撤、夏普比率）。

### Requirement: 止损爆仓安全检查
做多止损 SHALL NOT 低于爆仓价 `entry_price * (1 - 1/leverage)`。做空止损 SHALL NOT 高于爆仓价 `entry_price * (1 + 1/leverage)`。