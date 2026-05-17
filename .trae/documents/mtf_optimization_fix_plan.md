# MTF策略优化与日志编码修复计划

## 变更概述

修复3个问题 + 1个优化：

1. **修复 GBK 编码错误**：`backtest_engine.py` 中的 emoji 字符 (✅📈📉🛑📊⚠️) 在 Windows GBK 控制台无法输出
2. **放宽止损**：`atr_multiplier` 从 2.0→5.0（策略层）和 3.5→5.0（Executor层）
3. **增加4h趋势过滤**：仅当 SMA20_4h > SMA60_4h 时允许做多，SMA20_4h < SMA60_4h 时允许做空
4. **支撑区阈值**：`support_threshold` 从静态 10.0 改为 `ATR * 0.5`

## 修改步骤

### 步骤1：修复 `backtest_engine.py` 中的 Unicode emoji 编码错误（行754~1440）

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\backtest_engine.py`

11处 emoji 需要替换为纯文本：

| 行号 | 当前 | 替换为 |
|------|------|--------|
| 754 | `⚠️ 连续亏损` | `[WARN] 连续亏损` |
| 791 | `📊 凯利公式` | `[KELLY] 凯利公式` |
| 1002 | `✅止盈` / `🛑止损` | `[TP]止盈` / `[SL]止损` |
| 1053 | `✅止盈` / `🛑止损` | `[TP]止盈` / `[SL]止损` |
| 1183 | `✅ 限价单通过` | `[OK] 限价单通过` |
| 1277 | `📈 V2加仓多单` | `[LONG] V2加仓多单` |
| 1307 | `📈加仓` / `✅开多` | `[ADD]加仓` / `[LONG]开多` |
| 1338 | `📉 V2加仓空单` | `[SHORT] V2加仓空单` |
| 1368 | `📉加仓` / `✅开空` | `[ADD]加仓` / `[SHORT]开空` |
| 1413 | `✅ 已平掉全部多仓` | `[OK] 已平掉全部多仓` |
| 1440 | `✅ 已平掉全部空仓` | `[OK] 已平掉全部空仓` |

### 步骤2：放宽止损（ATR 倍数从 2.0/3.5 提升到 5.0）

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`

2.1 修改策略 `__init__` 默认值（行106）：
```python
# 从
atr_multiplier: float = 2.0,
# 改为
atr_multiplier: float = 5.0,
```

2.2 修改 Executor `__init__` 默认值（行2138）：
```python
# 从
atr_multiplier: float = 3.5,
# 改为
atr_multiplier: float = 5.0,
```

### 步骤3：增加4h趋势过滤

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`

3.1 在 `_calculate_indicators` 方法中添加 SMA 计算：
```python
self._sma_4h["SMA20"] = self.df_4h["close"].rolling(20).mean()
self._sma_4h["SMA60"] = self.df_4h["close"].rolling(60).mean()
```

3.2 新增方法 `_check_4h_trend(direction)`：
```python
def _check_4h_trend(self, direction: str = "long") -> str:
    """检查4h趋势：仅当SMA20>SMA60(做多)/SMA20<SMA60(做空)时才允许"""
    if len(self.df_4h) < 60:
        return "reduce"
    sma20 = float(self._sma_4h["SMA20"].iloc[-1])
    sma60 = float(self._sma_4h["SMA60"].iloc[-1])
    if direction == "long":
        if sma20 < sma60:
            return "block"
        return "ok"
    else:
        if sma20 > sma60:
            return "block"
        return "ok"
```

3.3 在 `_generate_entry_signal` 中（行1805附近）加入4h趋势检查：
```python
if self.enable_trend_filter:
    # 先检查4h趋势
    h4_trend = self._check_4h_trend("long")
    if h4_trend == "block":
        logger.info("[MTF] 4h SMA20<SMA60，空头趋势，禁止做多")
        return None
    # 再检查日线趋势
    trend = self._check_daily_trend("long")
    if trend == "block":
        return None
    if trend == "reduce":
        position_ratio = self.probe_ratio * 0.5
```

同样修改 `_generate_short_entry_signal`（做空信号）中的趋势检查：
```python
if self.enable_trend_filter:
    h4_trend = self._check_4h_trend("short")
    if h4_trend == "block":
        logger.info("[MTF] 4h SMA20>SMA60，多头趋势，禁止做空")
        return None
    trend = self._check_daily_trend("short")
    ...
```

### 步骤4：支撑区域阈值改为 ATR × 0.5

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`

**注意**：查看代码发现 `_check_support_zone()` (行299-311) 中的 `threshold` 已经是 `min(atr * 0.5, current_price * 0.01)`——它已经是动态的 ATR × 0.5！静态参数 `self.support_threshold = 10.0` 是未使用的死代码。无需修改逻辑。

但可以将 `__init__` 中的默认值（行90）改为 `ATR * 0.5` 的描述以便代码更清晰：
```python
# 从
support_threshold: float = 10.0,
# 改为
support_threshold: float = 0.0,  # 实际使用 ATR*0.5 动态计算，此参数保留兼容性
```

## 文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `backtest_engine.py` | 替换 11 处 emoji 为纯文本 |
| `mtf_fractal_strategy.py` | atr_multiplier 2.0→5.0；Exec atr_multiplier 3.5→5.0；新增 SMA 计算 + `_check_4h_trend()`；长做多/做空信号中加入 4h 趋势过滤 |