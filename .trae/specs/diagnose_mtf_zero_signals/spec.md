# MTF策略零信号根因分析 Spec

## Why
MTF策略回测（4h+30m周期）期间产生0笔交易，而图表上应该存在大量可交易点位。需要系统分析信号生成链路中每一层过滤条件，定位真正的阻塞点。

## What Changes
- 深入分析做多和做空两条信号链路的每个过滤条件
- 定位导致0信号的"瓶颈层"
- 识别支撑/阻力位与当前价格区间的适配问题
- 识别30m确认信号在4h主周期下的触发率问题
- 识别可能的 Chan 分型索引与数据帧索引不匹配问题

## Impact
- Affected specs: `multi_tf_fractal_strategy`, `fix_mtf_short_signal_backtest`
- Affected code: `mtf_fractal_strategy.py`, `backtest_engine.py`, `run_ethusdc_mtf_backtest.py`

---

## 信号链路完整分析

### 做多链路（长仓试探入场）

```
_generate_entry_signal()
  ├── Layer 1: _check_support_zone()
  │    条件: min(close, low) <= support_level + support_threshold(10)
  │    当前支撑位: 1950, 1900, 1850
  │    当前价格区间: ~2200-2300
  │    ❌ 阻塞: 价格远高于所有支撑位，永远不满足
  │
  ├── Layer 2: _check_4h_bottom_fractal()
  │    条件: 最新Chan分型.type == "bottom" 且 K2收盘 > K2开盘*0.5
  │    (未到达，被Layer 1阻塞)
  │
  └── Layer 3: _check_30m_signals()
       条件: 4类信号中>=2个满足(底背离/看涨形态/趋势突破/金叉)
       (未到达)
```

**结论: 做多链路的阻塞点是 Layer 1 (`_check_support_zone`) — 支撑位（1950/1900/1850）与当前市场价（~2200-2300）完全不匹配。**

---

### 做空链路（短仓试探入场）

```
_generate_short_entry_signal()
  ├── Layer 1: _check_resistance_zone()
  │    条件: max(close, high) >= resistance_level - resistance_threshold(10)
  │    当前阻力位: 2050, 2100, 2150
  │    当前价格区间: ~2200-2300
  │    ✅ 通过: 价格高于所有阻力位（如 2317 >= 2150-10=2140）
  │
  ├── Layer 2: _check_4h_top_fractal()
  │    条件: 最新Chan分型.type == "top" 且 K2收盘 < K2开盘*1.5
  │    ✅ 通过: 日志显示 "4h顶分型(Chan): idx=328"
  │
  └── Layer 3: _check_30m_short_signals()
       条件: 4类信号中>=2个满足(顶背离/看跌形态/趋势跌破/死叉)
       ❌ 阻塞: 日志显示所有4类信号均为False (0/4)

各子信号分析:
  ├── _check_30m_top_divergence()
  │    条件: 30m上价格创新高但MACD柱不创新高
  │    依赖 _macd_30m 和 df_30m 的 idxmin/idxmax 计算
  │    ⚠️ 注意: 使用 iloc 整数索引, lookback=min(20, len//3)
  │
  ├── _check_30m_bearish_candlestick()
  │    条件: 黄昏之星/看跌吞没/乌云盖顶/射击之星
  │    仅检查最近3根30m K线
  │    触发概率: 中等偏高（常见形态）
  │
  ├── _check_30m_trendline_break_down()
  │    条件: 近20根30m K线低点拟合上升趋势线，当前收盘跌破趋势线
  │    需要 slope > 0（上升趋势），然后跌破
  │    触发概率: 较低（需要先有上升+然后跌破）
  │
  └── _check_30m_death_cross()
       条件: MACD死叉或KDJ高位死叉(K>80)
       依赖 _macd_30m 和 _kdj_30m
       触发概率: 中等
```

**结论: 做空链路的阻塞点是 Layer 3 (`_check_30m_short_signals`) — 虽然阻力和分型条件通过，但30m信号的4个子信号全部返回False，无法满足≥2条件。**

---

### 关键架构问题分析

#### 问题1: 支撑/阻力位硬编码，与新周期不匹配

`run_ethusdc_mtf_backtest.py` 中：
```python
SUPPORT_LEVELS = "1950,1900,1850"
RESISTANCE_LEVELS = "2050,2100,2150"
```

这些值是在30m/15m周期下设定的，且基于较早的ETH价格。当前ETH价格在2200-2300区间。迁移到4h周期后（数据区间约90天，覆盖2026年开始），支撑位远低于实际价格，导致做多链路在Layer 1就被阻塞。

**影响**: 做多链路完全无法触发。

#### 问题2: 支撑/阻力检查的方向性逻辑

`_check_support_zone()` 使用 `check_price <= level + threshold`，意味着价格必须"跌到支撑位附近"。在上升趋势中（ETH从~1800涨到~2300），价格无法回到低支撑位。

`_check_resistance_zone()` 使用 `check_price >= level - threshold`，意味着价格只要"高于阻力位"就算进入阻力区。这在上升行情中几乎每根K线都会触发（因为价格已突破所有阻力位）。

**影响**: 做多被永久阻塞，做空的Layer 1形同虚设（恒真）。

#### 问题3: 30m信号与4h主周期的错配

30m确认信号是在30m K线数据上计算的，但30m数据已被切片对齐到当前4h K线时间。由于4h K线的`open_time`是4小时的开始时间，切片后的30m数据只包含到该时间点的数据。这本身是正确的。

但30m信号的检测窗口较小：
- 顶/底背离: lookback = min(20, len//3)，4h下30m数据量有限
- 看涨/看跌形态: 仅检查最后3根30m K线
- 趋势线: 检查最后20根30m K线（约10小时）
- 金叉/死叉: 检查MACD最后2根

在4h主周期下，每个4h Bar之间理论上有8根30m K线。如果30m信号恰好没有形成≥2的条件，整个交易就无法触发。

#### 问题4: 分型索引与数据帧索引可能不匹配（潜在Bug）

`_check_4h_bottom_fractal()` / `_check_4h_top_fractal()` 使用 `last_fractal.idx` 作为 `self.df_4h` 的索引去取K线数据。但 `fractals` 是由 `ChanStrategy._process_data()` 在 `df_processed`（包含处理合并后的数据）上生成的，`last_fractal.idx` 对应的是 `df_processed` 的行号，而非 `df_4h` 的行号。

当Chan的包含合并(`_merge_inclusion`)减少了K线数量后，两者的索引会偏离。这可能导致：
- `self.df_4h.iloc[k2_idx]` 取到错误的K线
- 分型价格判断（K2收盘/K2开盘）基于错误数据
- 在极端情况下可能返回正确分型但仍用错误K线数据

---

## 针对性解决方案

### MODIFIED Requirement: 支撑/阻力位动态计算
系统 SHALL 支持根据历史价格数据自动计算支撑/阻力位，替代硬编码值。

#### Scenario: 自动计算支撑位
- **GIVEN** 已加载4h K线数据包含过去90天价格
- **WHEN** 策略初始化时计算支撑/阻力位
- **THEN** 支撑位基于近期价格区间的关键低点（如近期最低价、EMA低点区域）
- **AND** 阻力位基于近期价格区间的关键高点（如近期最高价、EMA高点区域）

### MODIFIED Requirement: 适当放宽30m确认信号阈值或调整检测逻辑
系统 SHALL 确保30m确认信号能在大多行情中产生≥2个触发。

#### Scenario: 信号检测需覆盖更多场景
- **GIVEN** 4h主周期确认了分型+支撑/阻力区
- **WHEN** 30m信号中有≥1个（或改为任意一个）触发
- **THEN** 触发试探性入场信号
- **OR** 调整各子信号的检测参数使其更易触发

### NEW Requirement: 修复分型索引与数据帧索引匹配
系统 SHALL 使用 `df_processed` 而非原始 `df_4h` 在分型检查中获取K线数据。

#### Scenario: 分型K线数据正确获取
- **GIVEN** Chan分型在 df_processed 上计算
- **WHEN** 获取分型K线的开高低收数据
- **THEN** 应使用 `self.df_processed.iloc[k2_idx]` 而非 `self.df_4h.iloc[k2_idx]`