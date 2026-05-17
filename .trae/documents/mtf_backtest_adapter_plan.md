# MTF策略回测脚本适配计划

## 一、需求概述

按照修改后的 `mtf_fractal_strategy.py` 策略（新增底分型提前做多 + 顶分型提前做空），修改回测脚本以适配新功能，并运行回测提供优化建议。

## 二、当前状态分析

### 2.1 已修改的策略新增功能

| 功能 | 信号类型 | 方向 | 需要的数据 |
|------|---------|------|-----------|
| 底分型提前做多 | `EARLY_ENTRY` | long | 4h + 30m + **15m** |
| 顶分型提前做空 | `EARLY_SHORT_ENTRY` | short | 4h + 30m + **15m** |

### 2.2 当前回测脚本问题

**`run_backtest.py` (行267-272)**: MTF策略只加载了30m数据，未加载15m数据
**`run_backtest.py` (行313)**: `load_data_for_backtest` 调用未传递 `df_15m` 参数
**`backtest_engine.py` (行515)**: `_run_backtest_loop` 不更新 `df_15m`
**`backtest_engine.py` (行1177-1231)**: `_execute_trade` 不处理 `EARLY_ENTRY` / `EARLY_SHORT_ENTRY` 信号
**`run_ethusdc_mtf_backtest.py`**: 未传递提前入场相关参数

## 三、修改步骤

### 步骤1: 修改 `run_backtest.py` — 加载15分钟数据并传给策略

**文件**: `e:\Auto_test\huyhf\trading_system\backtest\run_backtest.py`

1.1 在 MTF 策略分支加载 15m 数据:

```python
# 行267-272 之后添加:
if strategy_version == "mtf":
    data_30m = engine.load_data(symbol, "30m", start_date=start_date, end_date=end_date)
    # ...existing 30m code...
    data_15m = engine.load_data(symbol, "15m", start_date=start_date, end_date=end_date)
    if data_15m and "15m" in data_15m:
        logger.info("15m data: %s rows", len(data_15m["15m"]))
    else:
        logger.warning("15m data missing, early entry features disabled")
        data_15m = {"15m": pd.DataFrame()}
```

1.2 修改 `load_data_for_backtest` 调用传递 df_15m:

```python
# 行313 - 改为:
strategy.load_data_for_backtest(df_4h=data[interval], df_30m=data_30m["30m"], 
                                df_15m=data_15m.get("15m"), df_daily=data["1d"])
```

1.3 添加 CLI 参数:

```python
parser.add_argument("--enable-early-entry", action="store_true", default=True,
    help="MTF策略: 启用底分型提前做多")
parser.add_argument("--enable-early-short-entry", action="store_true", default=True,
    help="MTF策略: 启用顶分型提前做空")
parser.add_argument("--early-entry-min-confidence", type=float, default=0.6,
    help="MTF策略: 提前入场最低置信度")
```

1.4 创建 MTF 策略时传递提前入场参数:

```python
strategy = MultiTFFractalStrategy(
    symbol=symbol,
    leverage=leverage,
    investment_ratio=investment_ratio,
    support_levels=support_levels or [],
    resistance_levels=resistance_levels or [],
    enable_early_entry=enable_early_entry,
    enable_early_short_entry=enable_early_short_entry,
    early_entry_min_confidence=early_entry_min_confidence,
    early_short_entry_min_confidence=early_short_entry_min_confidence,
)
```

### 步骤2: 修改 `backtest_engine.py` — 支持15m数据和提前入场信号

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\backtest_engine.py`

2.1 修改 `run_backtest` 方法，提取并传递 df_15m:

```python
# 在行479-482 30m数据加载之后添加:
df_15m = data.get("15m", pd.DataFrame())
if not df_15m.empty:
    df_15m = self._prepare_dataframe(df_15m)

# 修改行515 的 _run_backtest_loop 调用:
self._run_backtest_loop(df_interval, df_1d, daily_indices, strategy, df_30m, df_15m)
```

2.2 修改 `_run_backtest_loop` 方法签名和逻辑:

```python
def _run_backtest_loop(self, df_interval, df_1d, daily_indices, strategy, 
                       df_30m=None, df_15m=None):
    # ...
    # 在30m数据更新之后（行593-595）添加:
    if df_15m is not None and not df_15m.empty:
        current_time = df_interval.iloc[i]['open_time']
        strategy.df_15m = df_15m[df_15m['open_time'] <= current_time]
```

2.3 修改 `_execute_trade` 方法，处理新的提前入场信号:

```python
# 在 MTF 信号转换部分（行1177-1229）添加:
elif action == "EARLY_ENTRY":
    signal["action"] = "BUY"
    signal["position_size_ratio"] = signal.get("position_ratio", 0.25)
    signal["is_early_entry"] = True
    is_mtf_signal = True
elif action == "EARLY_SHORT_ENTRY":
    signal["action"] = "SELL"
    signal["position_size_ratio"] = signal.get("position_ratio", 0.25)
    signal["is_early_short_entry"] = True
    is_mtf_signal = True
```

### 步骤3: 修改 `run_ethusdc_mtf_backtest.py` — 更新显示信息和参数

**文件**: `e:\Auto_test\huyhf\run_ethusdc_mtf_backtest.py`

3.1 添加提前入场参数:

```python
ENABLE_EARLY_ENTRY = True
ENABLE_EARLY_SHORT_ENTRY = True
EARLY_ENTRY_MIN_CONFIDENCE = 0.6
```

3.2 添加到命令行:

```python
cmd = [
    # ...existing...
    "--strategy-version", "mtf",
    "--enable-early-entry",
    "--enable-early-short-entry",
    "--early-entry-min-confidence", str(EARLY_ENTRY_MIN_CONFIDENCE),
]
```

3.3 更新显示信息:

```python
print(f"  ✅ 15m 提前做多入场（底分型预判）")
print(f"  ✅ 15m 提前做空入场（顶分型预判）")
print(f"  ├─ 提前做多仓位: {EARLY_ENTRY_RATIO*100:.0f}%")
print(f"  └─ 提前做空仓位: {EARLY_SHORT_ENTRY_RATIO*100:.0f}%")
```

### 步骤4: 运行回测

运行修改后的回测脚本:

```bash
cd e:\Auto_test\huyhf
python run_ethusdc_mtf_backtest.py
```

### 步骤5: 分析结果并提供优化建议

根据回测结果分析：
- 提前入场信号的效果（胜率、盈亏比）
- 与试探性入场信号的对比
- 置信度阈值的合理性
- 仓位比例的建议

## 四、代码修改清单

| 文件 | 修改内容 | 行数估计 |
|------|---------|---------|
| `run_backtest.py` | 加载15m数据 + 传递参数 | ~30行 |
| `backtest_engine.py` | 15m数据更新 + 信号处理 | ~25行 |
| `run_ethusdc_mtf_backtest.py` | 参数传递 + 显示更新 | ~20行 |

## 五、预期效果

修改后，回测将能够:
1. 在每根4小时K线处理时，同步更新对应的15分钟K线数据
2. 正确执行 `EARLY_ENTRY`（底分型提前做多）和 `EARLY_SHORT_ENTRY`（顶分型提前做空）信号
3. 评估提前入场策略在历史数据上的表现