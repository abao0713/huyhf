# 多周期共振顶分型预判做空策略 Spec

## Why
当前 `MultiTFFractalStrategy` 仅支持做多方向（底分型+支撑位共振），缺乏对称的做空能力。需要在现有策略框架上扩展顶分型预判做空逻辑，利用阻力位+双周期共振+多信号确认机制，实现完整的双向交易能力。

## What Changes
- **MODIFIED** `MultiTFFractalStrategy` 类新增做空参数和检测方法
  - 新增 `resistance_levels` (关键阻力位列表) 和 `resistance_threshold` 参数
  - 新增 `_check_resistance_zone()` 阻力区域检测
  - 新增 `_check_30m_top_fractal()` 30分钟顶分型预判
  - 新增15分钟空头信号检测：`_check_15m_top_divergence()` / `_check_15m_bearish_candlestick()` / `_check_15m_trendline_break_down()` / `_check_15m_death_cross()`
  - 新增 `_check_15m_short_signals()` 空头多信号确认
  - 新增 `_generate_short_entry_signal()` / `_generate_short_confirm_signal()` 做空信号生成
  - 修改 `generate_signal()` 同时检测做多和做空信号
  - 修改 `update_position_from_signal()` 支持多空双向持仓状态
  - 新增可选过滤条件：大周期趋势(MATrend)、市场环境(强势上涨回避)、成交量萎缩谨慎
- **MODIFIED** `MultiTFFractalStrategyExecutor` 新增做空交易执行
  - 新增 `_open_short_probe()` / `_add_short_confirm()` 空头交易方法
  - 修改 `_execute_signal()` 支持 `PROBE_ENTRY_SHORT` / `CONFIRM_ADD_SHORT` 信号
- **MODIFIED** `run_ethusdc_mtf_live.py` 新增阻力位参数
  - 新增 `--resistance-levels` CLI 参数
  - 显示阻力位配置信息和止盈比

## Impact
- Affected specs: `multi_tf_fractal_strategy` (扩展)
- Affected code:
  - `trading_system/strategies/mtf_fractal_strategy.py` (修改)
  - `run_ethusdc_mtf_live.py` (修改)

## MODIFIED Requirements

### Requirement: 30分钟级别阻力位预判
系统 SHALL 在30分钟K线图上检测价格是否进入关键阻力区域（当前价格 >= 阻力位 - 阈值），并识别潜在顶分型结构（K1、K2两根K线满足K2.high > K1.high且K2.close < K2.open * 1.5）。

#### Scenario: 价格进入阻力区域且出现顶分型雏形
- **GIVEN** 用户配置了关键阻力位列表 [2400, 2450, 2500]
- **WHEN** 30分钟当前价格 >= 2400 - 阈值(如10点) 且 存在K1,K2满足顶分型条件
- **THEN** 系统切换到15分钟图表进一步确认做空信号

#### Scenario: 价格远离阻力区域
- **GIVEN** 30分钟当前价格 = 2250，最近阻力位 = 2400
- **WHEN** 价格远低于阻力位
- **THEN** 系统不触发后续15分钟做空确认流程

### Requirement: 15分钟级别空头多信号确认
系统 SHALL 在15分钟图表上检测以下4类空头信号，至少满足2个才触发做空试探性入场：
1. **顶背离**: 15分钟价格创新高但MACD未创新高
2. **看跌K线形态**: 出现黄昏之星、看跌吞没、射击之星或乌云盖顶
3. **跌破上升趋势线**: 收盘价低于最近N根K线的上升趋势线
4. **指标死叉**: MACD死叉或KDJ高位死叉(K>80)

#### Scenario: 满足2个信号触发做空试探入场
- **GIVEN** 15分钟图表检测到顶背离 + MACD死叉
- **WHEN** 满足信号数 >= 2
- **THEN** 系统生成做空试探入场信号，仓位=总仓位40%，止损=max(15分钟信号K线最高点, K2最高点)+偏移，止盈=入场-(止损-入场)*盈亏比

#### Scenario: 满足1个信号不触发
- **GIVEN** 15分钟图表仅检测到顶背离
- **WHEN** 满足信号数 < 2
- **THEN** 系统不生成做空信号，等待更多确认

### Requirement: 做空两阶段仓位管理
系统 SHALL 支持做空试探性入场（40%仓位）和确认加仓（60%仓位）两阶段操作。

#### Scenario: 做空试探入场后K3确认
- **GIVEN** 已执行做空试探入场（40%仓位）
- **WHEN** 30分钟K3收盘价 < K2最低价
- **THEN** 系统生成做空加仓信号，加仓仓位=总仓位60%，止损更新为顶分型最高点+偏移

#### Scenario: 做空试探入场后K3未确认
- **GIVEN** 已执行做空试探入场
- **WHEN** 30分钟K3收盘价 >= K2最低价
- **THEN** 系统保持现有做空仓位，不执行加仓，继续监控

### Requirement: 做空可选过滤条件
系统 SHALL 支持以下可选过滤来避免不利的做空条件：
1. **大周期趋势过滤**: 当日线或2小时均线EMA20>EMA60(多头趋势)时降仓或拒绝做空
2. **强势上涨回避**: 30分钟连续3根以上阳线(每根涨幅>0.5%)时暂不做空
3. **成交量萎缩谨慎**: 15分钟成交量低于20周期均量60%时降低做空仓位至原仓位50%

#### Scenario: 日线多头趋势中做空降仓
- **GIVEN** 日线EMA20 > EMA60（多头趋势）
- **WHEN** 做空信号生成
- **THEN** 系统将仓位降低至原仓位50%，日志记录"逆势做空降仓"

#### Scenario: 强势上涨中拒绝做空
- **GIVEN** 30分钟最近3根K线均为阳线且涨幅>0.5%
- **WHEN** 做空信号生成
- **THEN** 系统丢弃做空信号，记录"强势上涨回避做空"

### Requirement: 统一风控（多空共用）
现有风控规则（单笔2%、连续3次止损、日亏损5%）SHALL 同时适用于多空两个方向，止损计数器多空不区分。

## ADDED Requirements

### Requirement: 做空资金管理
做空交易 SHALL 使用与做多相同的INVESTMENT_RATIO和LEVERAGE计算仓位，direction参数设置为"short"。做空信号包含止盈价：止盈价 = 入场价 - (止损价 - 入场价) * 盈亏比(default=1.5)。

### Requirement: 双向信号优先级
当同一周期同时出现做多和做空信号时，系统 SHALL 优先考虑与当前持仓方向一致的信号。空仓状态下，优先选择信号满足数更多的方向；满足数相同时，优先选择做多信号。