# 修复顶分型做空镜像功能检查

## 问题描述

在 `mtf_fractal_strategy.py` 中，做多和做空功能应该互成镜像，但检查发现顶分型做空功能**没有完全实现**。

### 已完成的底分型做多功能（5个方法）

| 方法名 | 行号 | 功能 |
|--------|------|------|
| `_check_4h_bottom_fractal_k1k2()` | 333 | 检测4小时底分型K1/K2结构 |
| `_check_15m_first_buy()` | 467 | 检测15分钟一买（底背驰） |
| `_check_15m_second_buy()` | 508 | 检测15分钟二买（回调不破前低） |
| `_check_15m_uptrend()` | 578 | 确认15分钟趋势向上 |
| `_generate_early_entry_signal()` | 641 | 生成提前入场做多信号 |

### 未实现的顶分型做空镜像功能

| 方法名 | 功能 |
|--------|------|
| `_check_4h_top_fractal_k1k2()` | 检测4小时顶分型K1/K2结构 |
| `_check_15m_first_sell()` | 检测15分钟一卖（顶背驰） |
| `_check_15m_second_sell()` | 检测15分钟二卖（反弹不过前高） |
| `_check_15m_downtrend()` | 确认15分钟趋势向下 |
| `_generate_early_short_entry_signal()` | 生成提前入场做空信号 |
| `_open_early_short_entry()` | 执行提前做空订单（Executor） |

### 已添加但未使用的数据类

- `TopFractalK12Structure` (行66)
- `_top_fractal_k12` 数据成员 (行175)
- `_chan_first_sell_analyzer` 分析器 (行176)

### 已添加但未使用的参数

- `enable_early_short_entry` (行113)
- `early_short_entry_min_confidence` (行114)
- `early_short_entry_ratio` (行115)

### 已添加但未使用的数据成员

- `enable_early_short_entry` (行177)
- `early_short_entry_min_confidence` (行178)
- `early_short_entry_ratio` (行179)

## 镜像对称关系检查

| 功能 | 底分型做多 | 顶分型做空 | 状态 |
|------|-----------|-----------|------|
| K1条件 | close < open | close > open | 未实现 |
| K2条件 | low < K1.low | high > K1.high | 未实现 |
| K3条件 | low > K2.low | high < K2.high | 未实现 |
| 一买/一卖 | 底背驰 | 顶背驰 | 未实现 |
| 二买/二卖 | 回调不破 | 反弹不过 | 未实现 |
| 趋势 | 向上 | 向下 | 未实现 |
| 信号类型 | EARLY_ENTRY | EARLY_SHORT_ENTRY | 未实现 |
| 方向 | long | short | 未实现 |
| 止损方向 | 下方 | 上方 | 未实现 |
| 止盈方向 | 上方 | 下方 | 未实现 |

## 影响

- 顶分型做空功能不可用
- 无法在4小时K线顶分型形成时提前做空
- 只能依赖现有的基于阻力区域的做空信号

## 修复方案

实现以下5个方法和1个Executor方法，使做多和做空功能互成镜像：

1. `_check_4h_top_fractal_k1k2()` - 检测顶分型K1/K2结构
2. `_check_15m_first_sell()` - 检测15分钟一卖
3. `_check_15m_second_sell()` - 检测15分钟二卖
4. `_check_15m_downtrend()` - 确认15分钟趋势向下
5. `_generate_early_short_entry_signal()` - 生成提前做空信号
6. `_open_early_short_entry()` - Executor执行提前做空订单
7. 修改 `update_position_from_signal()` 支持 `early_short_entry`
8. 修改 `_execute_signal()` 支持 `EARLY_SHORT_ENTRY`
