# MTF策略优化修复计划 v2

## 背景
根据回测结果（0%胜率，-14.07%收益，34.25%最大回撤），需要实施三项优化 + 修复一个终端报错。

---

## 已完成的优化（无需重复操作）

### ✅ 步骤1: 修复 Terminal Unicode 报错（emoji → 文本标签）
- 文件: `trading_system/strategies/backtest_engine.py`
- 已将全部 11 处 emoji（⚠️📊✅🛑📈📉）替换为纯文本标签（`[WARN]`、`[KELLY]`、`[OK]`、`[SL]`、`[LONG]`、`[SHORT]` 等）
- 已通过 Grep 验证：backtest_engine.py 中无残留 emoji

### ✅ 步骤2: 放宽止损（atr_multiplier 3.5 → 5.0）
- `MultiTFFractalStrategy.__init__`: `atr_multiplier: float = 5.0` (line 106)
- `MultiTFFractalStrategyExecutor.__init__`: `atr_multiplier: float = 5.0` (line 2158)
- 所有 4 处止损计算（lines 724, 1085, 1799, 1963）均使用 `self.atr_multiplier`，无需额外修改

### ✅ 步骤2 前置：SMA 计算和 `_check_4h_trend()` 方法
- `self._sma_4h` 字典: line 153
- SMA 计算在 `_calculate_indicators()`: lines 234-235
- `_check_4h_trend()` 方法: lines 1899-1914
  - 做多检查：SMA20 < SMA60 → block
  - 做空检查：SMA20 > SMA60 → block

---

## 待实施任务

### 🔴 任务1: 将 `_check_4h_trend()` 集成到入场信号生成

**目标**: 在 `_generate_entry_signal()` 和 `_generate_short_entry_signal()` 中调用 4h 趋势过滤。

**修改文件**: `trading_system/strategies/mtf_fractal_strategy.py`

#### 1.1 修改 `_generate_entry_signal()`（做多信号，行1808附近）

**当前代码** (line 1808-1814):
```python
if self.enable_trend_filter:
    trend = self._check_daily_trend("long")
    if trend == "block":
        return None
    if trend == "reduce":
        position_ratio = self.probe_ratio * 0.5
        logger.info("[MTF] 逆势做多降仓50%")
```

**修改为**:
```python
if self.enable_trend_filter:
    h4_trend = self._check_4h_trend("long")
    if h4_trend == "block":
        return None
    trend = self._check_daily_trend("long")
    if trend == "block":
        return None
    if trend == "reduce":
        position_ratio = self.probe_ratio * 0.5
        logger.info("[MTF] 逆势做多降仓50%")
```

**逻辑**:
- 4h趋势过滤优先级最高，SMA20 < SMA60 直接禁止做多
- 日线趋势过滤在4h通过后才执行

#### 1.2 修改 `_generate_short_entry_signal()`（做空信号，行1972附近）

**当前代码** (line 1972-1977):
```python
if self.enable_trend_filter:
    trend_signal = self._check_daily_trend("short")
    if trend_signal == "block":
        return None
    if trend_signal == "reduce":
        position_ratio *= 0.5
```

**修改为**:
```python
if self.enable_trend_filter:
    h4_trend = self._check_4h_trend("short")
    if h4_trend == "block":
        return None
    trend_signal = self._check_daily_trend("short")
    if trend_signal == "block":
        return None
    if trend_signal == "reduce":
        position_ratio *= 0.5
```

---

### 🔴 任务2: 清理 `support_threshold` 死代码

**目标**: `support_threshold` 参数在 `__init__` 中存储为 `self.support_threshold`，但实际从未被使用。真正的阈值在 `_check_support_zone()` (line 309) 和 `_check_resistance_zone()` (line 1152) 中动态计算：`min(atr * 0.5, current_price * 0.01)`。

**修改文件**: `trading_system/strategies/mtf_fractal_strategy.py`

#### 2.1 `MultiTFFractalStrategy.__init__` (line 90)

**当前**:
```python
support_threshold: float = 10.0,
```

**修改为**:
```python
support_threshold: float = 0.0,  # 实际阈值在 _check_support_zone 中动态计算为 min(ATR*0.5, price*0.01)
```

#### 2.2 `MultiTFFractalStrategyExecutor.__init__` (line 2142)

**当前**:
```python
support_threshold: float = 10.0,
```

**修改为**:
```python
support_threshold: float = 0.0,  # 实际阈值在 _check_support_zone 中动态计算为 min(ATR*0.5, price*0.01)
```

**说明**: 不做大范围重构（如删除参数），仅修改默认值并加注释标记，避免影响回调脚本和其他调用方传参。

---

## 验证步骤

1. 运行 Python 语法检查：
   ```powershell
   python -c "import py_compile; py_compile.compile('e:\\Auto_test\\huyhf\\trading_system\\strategies\\mtf_fractal_strategy.py', doraise=True)"
   ```

2. （可选）运行回测验证 4h 趋势过滤效果：
   ```powershell
   python e:\Auto_test\huyhf\run_ethusdc_mtf_backtest.py
   ```

---

## 影响范围摘要

| 文件 | 修改量 | 类型 |
|------|--------|------|
| `mtf_fractal_strategy.py` | ~6行 | 新增4h趋势检查 + 清理死代码默认值 |
| `backtest_engine.py` | 0行 | 无需修改（emoji已修复） |

- **风险**: 低。`_check_4h_trend()` 方法已通过语法检查，仅需在调用链中插入。
- **兼容性**: 高。`support_threshold` 仅改默认值，不影响传入其他值的调用方。