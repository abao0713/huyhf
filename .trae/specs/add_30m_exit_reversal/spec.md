# 30分钟K线止盈 + 反手做空 Spec

## Why

当前策略的退出机制完全依赖回测引擎的ATR止损和追踪止损（4h级别），**完全没有使用30分钟K线信号来判断退出时机**。这导致两个致命问题：

1. 在2026-02-25T16:00权益达到$9,262峰值时，30m K线出现明显反转信号（如黄昏之星、MACD死叉等），但策略无视这些信号继续持仓，随后在下一根4h K线暴跌-22.2%后才被动止损。
2. 暴跌后30m K线出现做空信号（如看跌吞没、跌破上升趋势线、死叉），但策略无法反手做空，错过了趋势反转带来的利润。

核心结论：**策略只解决了"何时入场"，但完全没有解决"何时出场"和"何时反转"**。

## What Changes

- 策略层新增：持仓状态下检查30m反转信号，触发止盈退出（`CLOSE_LONG` / `CLOSE_SHORT`）
- 策略层新增：退出后立即检查反向入场条件，满足则触发反转（`REVERSE_TO_SHORT` / `REVERSE_TO_LONG`）
- **BREAKING**: 引擎层新增 `CLOSE_LONG` 和 `CLOSE_SHORT` 的MTF信号转换处理
- 引擎层复用已有的 `REVERSE_TO_SHORT` / `REVERSE_TO_LONG` 反转机制

## Impact

- Affected specs: `multi_tf_fractal_strategy`, `add_mtf_short_selling`, `fix_mtf_short_signal_backtest`
- Affected code:
  - `trading_system/strategies/mtf_fractal_strategy.py` — 新增退出信号检测 + `_generate_signal_internal()` 逻辑
  - `trading_system/strategies/backtest_engine.py` — `_execute_trade()` MTF信号转换 + `_validate_signal()`

## ADDED Requirements

### Requirement: 30分钟K线做多退出信号检测
策略在持有多单时，SHALL 使用30分钟K线数据检测三类反转信号：
- **看跌K线形态**（黄昏之星/看跌吞没/乌云盖顶/射击之星）：复用已有 `_check_30m_bearish_candlestick()`
- **跌破上升趋势线**：复用已有 `_check_30m_trendline_break_down()`
- **MACD/KDJ死叉**：复用已有 `_check_30m_death_cross()`

当检测到的信号数 ≥ `min_signal_count`（默认1）时，SHALL 生成 `CLOSE_LONG` 信号。

#### Scenario: 持有多单时30m出现黄昏之星+MACD死叉
- **GIVEN** 当前持有多单（direction="long"），confirm_added 可能为 True 或 False
- **WHEN** 30m K线检测到看跌形态=True 且 MACD死叉=True（≥2个信号）
- **THEN** 生成 `CLOSE_LONG` 信号，reason="30m反转信号: 看跌形态+MACD死叉"

#### Scenario: 持有多单时30m信号不足
- **GIVEN** 当前持有多单
- **WHEN** 30m K线检测到看跌形态=False, 趋势线跌破=False, 死叉=False（0个信号）
- **THEN** 不生成退出信号，继续持仓

### Requirement: 30分钟K线做空退出信号检测
策略在持有空单时，SHALL 使用30分钟K线数据检测三类反转信号：
- **看涨K线形态**（早晨之星/看涨吞没/锤子线）：复用已有 `_check_30m_bullish_candlestick()`
- **突破下降趋势线**：复用已有 `_check_30m_trendline_break()`
- **MACD/KDJ金叉**：复用已有 `_check_30m_golden_cross()`

当检测到的信号数 ≥ `min_signal_count`（默认1）时，SHALL 生成 `CLOSE_SHORT` 信号。

#### Scenario: 持有空单时30m出现看涨吞没+KDJ金叉
- **GIVEN** 当前持有空单（direction="short"）
- **WHEN** 30m K线检测到看涨形态=True 且 KDJ金叉=True（≥2个信号）
- **THEN** 生成 `CLOSE_SHORT` 信号，reason="30m反转信号: 看涨形态+KDJ金叉"

### Requirement: 退出后自动检查反转
策略在生成 `CLOSE_LONG` 信号后，SHALL 立即检查做空入场条件（阻力区域+4h顶分型+30m做空信号），若满足则改为生成 `REVERSE_TO_SHORT` 信号。

策略在生成 `CLOSE_SHORT` 信号后，SHALL 立即检查做多入场条件（支撑区域+4h底分型+30m做多信号），若满足则改为生成 `REVERSE_TO_LONG` 信号。

#### Scenario: 多单退出后做空条件满足 → 反转
- **GIVEN** 策略生成了 `CLOSE_LONG` 信号
- **WHEN** 做空入场条件满足（阻力区域+4h顶分型+30m做空信号≥min_signal_count）
- **THEN** 将信号改为 `REVERSE_TO_SHORT`，携带平仓原因+新开空信息

#### Scenario: 多单退出后做空条件不满足 → 仅平仓
- **GIVEN** 策略生成了 `CLOSE_LONG` 信号
- **WHEN** 做空入场条件不满足
- **THEN** 仅返回 `CLOSE_LONG` 信号，不反转

## MODIFIED Requirements

### Requirement: 引擎MTF信号转换
`_execute_trade()` 的MTF信号转换块 SHALL 新增对 `CLOSE_LONG` 和 `CLOSE_SHORT` 的处理：

- `CLOSE_LONG` → 直接调用 `_close_long()` 平掉全部多单，并清理策略持仓状态
- `CLOSE_SHORT` → 直接调用 `_close_short()` 平掉全部空单，并清理策略持仓状态

`_validate_signal()` SHALL 将 `CLOSE_LONG` 和 `CLOSE_SHORT` 加入允许的action列表。

#### Scenario: 引擎接收CLOSE_LONG信号
- **GIVEN** 引擎收到 action="CLOSE_LONG" 的信号
- **WHEN** 当前持有多单
- **THEN** 调用 `_close_long()` 平仓，清理策略持仓状态，信号处理结束

### Requirement: 信号生成主逻辑扩展
`_generate_signal_internal()` SHALL 在现有逻辑基础上新增两个分支：

1. 当 `position_state.direction == "long"` 时（无论confirm_added状态）：
   - 优先检查30m多单退出信号，若满足则生成 `CLOSE_LONG` 或 `REVERSE_TO_SHORT`
   - 若未触发退出，对于 confirm_added=False 的情况继续检查K3确认加仓

2. 当 `position_state.direction == "short"` 时（无论confirm_added状态）：
   - 优先检查30m空单退出信号，若满足则生成 `CLOSE_SHORT` 或 `REVERSE_TO_LONG`
   - 若未触发退出，对于 confirm_added=False 的情况继续检查K3确认加仓

#### Scenario: 持仓中优先检查30m退出，退出优先于加仓
- **GIVEN** 持有多单且未确认加仓
- **WHEN** 30m反转信号满足（≥min_signal_count）
- **THEN** 生成退出信号，不再检查K3确认加仓