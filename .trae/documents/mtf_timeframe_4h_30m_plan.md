# MTF策略时间周期迁移计划：30m+15m → 4h+30m

## 目标
将MTF多周期共振分型策略的主周期从**30分钟K线**替换为**4小时K线**，辅助周期从**15分钟K线**替换为**30分钟K线**。
4小时K线的时间范围内理论上会出现8根30分钟K线。

---

## 影响范围分析

| 文件 | 变更量 | 关键变更 |
|------|--------|----------|
| `trading_system/strategies/mtf_fractal_strategy.py` | **~100+ 行** | 变量/方法/日志全部重命名，executor K线间隔 |
| `trading_system/strategies/backtest_engine.py` | **4 处** | `strategy.df_30m` → `strategy.df_4h` |
| `trading_system/backtest/run_backtest.py` | **~6 行** | `15m` → `30m` 数据加载 |
| `run_ethusdc_mtf_backtest.py` | **~5 行** | INTERVAL, 显示文本 |
| `run_ethusdc_mtf_live.py` | **~2 行** | 显示文本 |

---

## Step 1: 下载4小时历史数据

下载 `ETHUSDC_4h.csv` 到 `trading_system/data/binance_history/` 目录。

**执行方式**: 运行 BacktestDataManager 下载脚本：
```python
from trading_system.data.backtest_data_manager import BacktestDataManager
manager = BacktestDataManager()
manager.download_and_save_data("ETHUSDC", ["4h"], start_date="2024-01-01")
```

**验证**: 确认文件 `trading_system/data/binance_history/ETHUSDC_4h.csv` 存在且记录数 > 0。

---

## Step 2: 重命名 `mtf_fractal_strategy.py` 中所有变量/方法/日志 (~100+ 行)

### 2.1 类属性声明 (L89-94)
| 旧名 | 新名 |
|------|------|
| `self.df_30m: pd.DataFrame = pd.DataFrame()` | `self.df_4h: pd.DataFrame = pd.DataFrame()` |
| `self.df_15m: pd.DataFrame = pd.DataFrame()` | `self.df_30m: pd.DataFrame = pd.DataFrame()` |
| `self._macd_30m: Dict[str, pd.Series] = {}` | `self._macd_4h: Dict[str, pd.Series] = {}` |
| `self._macd_15m: Dict[str, pd.Series] = {}` | `self._macd_30m: Dict[str, pd.Series] = {}` |

### 2.2 ChanStrategy 初始化 (L102)
```python
# 旧: self._chan = ChanStrategy(symbol=symbol, time_frame="30m", hg1=8, use_binance_client=False)
# 新: self._chan = ChanStrategy(symbol=symbol, time_frame="4h", hg1=8, use_binance_client=False)
```

### 2.3 `inject_data` 方法 (L134-140) + `_calculate_indicators` (L149-162)
- 参数 `df_30m` → `df_4h`, `df_15m` → `df_30m`
- 方法体内所有 `self.df_30m` → `self.df_4h`, `self.df_15m` → `self.df_30m`
- `_macd_30m` → `_macd_4h`, `_macd_15m` → `_macd_30m`
- `_calc_kdj_30m()` → `_calc_kdj_4h()`, `_calc_kdj_15m()` → `_calc_kdj_30m()`

### 2.4 `_calc_kdj_30m` → `_calc_kdj_4h` (L164-171)
- 方法名 + 内部 `self._kdj_30m` → `self._kdj_4h`
- 内部 `self.df_30m` → `self.df_4h`

### 2.5 `_calc_kdj_15m` → `_calc_kdj_30m` (L173-180)
- 方法名 + 内部 `self._kdj_15m` → `self._kdj_30m`
- 内部 `self.df_15m` → `self.df_30m`

### 2.6 `_check_support_zone` (L192-202)
- `self.df_30m` → `self.df_4h` (3处)

### 2.7 `_calculate_atr` (L204-222)
- `self.df_30m` → `self.df_4h` (2处)

### 2.8 `_check_30m_bottom_fractal` → `_check_4h_bottom_fractal` (L224-239)
- 方法名重命名
- `self.df_30m` → `self.df_4h` (2处)
- **日志消息**: `"30m底分型"` → `"4h底分型"`

### 2.9 `_check_resistance_zone` (L241-251)
- `self.df_30m` → `self.df_4h` (3处)

### 2.10 `_check_30m_top_fractal` → `_check_4h_top_fractal` (L253-268)
- 方法名重命名
- `self.df_30m` → `self.df_4h` (2处)
- **日志消息**: `"30m顶分型"` → `"4h顶分型"`

### 2.11 `_check_15m_divergence` → `_check_30m_divergence` (L270-290)
- 方法名重命名
- `self.df_15m` → `self.df_30m` (2处)
- `_macd_15m` → `_macd_30m` (1处)
- **日志消息**: `"15m底背离"` → `"30m底背离"`

### 2.12 `_check_15m_bullish_candlestick` → `_check_30m_bullish_candlestick` (L292-328)
- 方法名重命名
- `self.df_15m` → `self.df_30m` (3处)
- **日志消息**: `"15m看涨吞没/锤子线"` → `"30m看涨吞没/锤子线"`

### 2.13 `_check_15m_trendline_break` → `_check_30m_trendline_break` (L330-343)
- 方法名重命名
- `self.df_15m` → `self.df_30m` (3处)
- **日志消息**: `"15m下降趋势线突破"` → `"30m下降趋势线突破"`

### 2.14 `_check_15m_golden_cross` → `_check_30m_golden_cross` (L345-365)
- 方法名重命名
- `_macd_15m` → `_macd_30m` (2处)
- `_kdj_15m` → `_kdj_30m` (2处)
- **日志消息**: `"15m金叉"` → `"30m金叉"`

### 2.15 `_check_15m_top_divergence` → `_check_30m_top_divergence` (L367-387)
- 方法名重命名
- `self.df_15m` → `self.df_30m` (2处)
- `_macd_15m` → `_macd_30m` (1处)
- **日志消息**: `"15m顶背离"` → `"30m顶背离"`

### 2.16 `_check_15m_bearish_candlestick` → `_check_30m_bearish_candlestick` (L389-436)
- 方法名重命名
- `self.df_15m` → `self.df_30m` (3处)
- **日志消息**: `"15m看跌吞没/上吊线"` → `"30m看跌吞没/上吊线"`

### 2.17 `_check_15m_trendline_break_down` → `_check_30m_trendline_break_down` (L438-451)
- 方法名重命名
- `self.df_15m` → `self.df_30m` (3处)
- **日志消息**: `"15m上升趋势线跌破"` → `"30m上升趋势线跌破"`

### 2.18 `_check_15m_death_cross` → `_check_30m_death_cross` (L453-473)
- 方法名重命名
- `_macd_15m` → `_macd_30m` (2处)
- `_kdj_15m` → `_kdj_30m` (2处)
- **日志消息**: `"15m死叉"` → `"30m死叉"`

### 2.19 `_check_15m_short_signals` → `_check_30m_short_signals` (L475-483)
- 方法名重命名
- 内部调用全部改为 `_check_30m_*` 方法

### 2.20 `_check_15m_signals` → `_check_30m_signals` (L485-493)
- 方法名重命名
- 内部调用全部改为 `_check_30m_*` 方法

### 2.21 Helper方法 (L495-503)
- `_get_15m_signal_low` → `_get_30m_signal_low`, `self.df_15m` → `self.df_30m`
- `_get_15m_signal_high` → `_get_30m_signal_high`, `self.df_15m` → `self.df_30m`

### 2.22 `generate_signal` (L534-536)
- `self.df_30m` → `self.df_4h`
- `self.df_15m` → `self.df_30m`

### 2.23 `_generate_signal_internal` (L548)
- `self.df_30m` → `self.df_4h`

### 2.24 `load_data_for_backtest` (L582-586)
- 参数 `df_30m` → `df_4h`, `df_15m` → `df_30m`
- 方法体内对应更新
- **日志消息**: `"30m="` → `"4h="`, `"15m="` → `"30m="`

### 2.25 `_process_data` (L588-595) - **逻辑变更**
```python
# 旧: 将15m数据按30m时间对齐后注入
# 新: 将30m数据按4h时间对齐后注入
```
- `df_15m_sliced` → `df_30m_sliced`
- 时间对齐逻辑从 `self.df_15m <= last_30m_time` 改为 `self.df_30m <= last_4h_time`
- `self.inject_data(self.df_30m, df_15m_sliced, self.df_daily)` → `self.inject_data(self.df_4h, df_30m_sliced, self.df_daily)`

### 2.26 `_generate_entry_signal` (L612-665)
- `_check_30m_bottom_fractal()` → `_check_4h_bottom_fractal()`
- `_check_15m_signals()` → `_check_30m_signals()`
- `self.df_30m` → `self.df_4h` (3处)
- `signal_15m_low` → `signal_30m_low`
- `_get_15m_signal_low()` → `_get_30m_signal_low()`
- **日志消息** 中 `"30m"` → `"4h"`, `"15m"` → `"30m"`

### 2.27 `_generate_confirm_signal` (L669-679)
- `self.df_30m` → `self.df_4h` (5处)

### 2.28 `_check_strong_rally_avoid` (L715-728)
- `self.df_30m` → `self.df_4h` (2处)

### 2.29 `_check_volume_shrinkage` (L730-738)
- `self.df_15m` → `self.df_30m` (2处)

### 2.30 `_generate_short_entry_signal` (L741-799)
- `_check_30m_top_fractal()` → `_check_4h_top_fractal()`
- `_check_15m_short_signals()` → `_check_30m_short_signals()`
- `self.df_30m` → `self.df_4h` (3处)
- `signal_15m_high` → `signal_30m_high`
- `_get_15m_signal_high()` → `_get_30m_signal_high()`
- **日志消息** 中 `"30m"` → `"4h"`, `"15m"` → `"30m"`

### 2.31 `_generate_short_confirm_signal` (L801-811)
- `self.df_30m` → `self.df_4h` (5处)

### 2.32 Executor `_run_once` (L988-1030) - **关键API变更**
- `klines_30m` → `klines_4h`, `interval="30m"` → `interval="4h"`
- `klines_15m` → `klines_30m`, `interval="15m"` → `interval="30m"`
- `df_30m = binance_klines_to_dataframe(klines_30m)` → `df_4h = binance_klines_to_dataframe(klines_4h)`
- `df_15m = binance_klines_to_dataframe(klines_15m)` → `df_30m = binance_klines_to_dataframe(klines_30m)`
- `self.strategy.inject_data(df_30m, df_15m)` → `self.strategy.inject_data(df_4h, df_30m)`
- **所有日志消息** 中 `"30m"` → `"4h"`, `"15m"` → `"30m"`

### 2.33 Executor `_execute_signal` (L1053)
- `self.strategy.df_30m` → `self.strategy.df_4h`

---

## Step 3: 修改 `backtest_engine.py` (4处)

### 3.1 L581 - 主回测循环数据注入
```python
# 旧: strategy.df_30m = df_interval.iloc[:i + 1]
# 新: strategy.df_4h = df_interval.iloc[:i + 1]
```

### 3.2 L671-674 - ATR计算检查
```python
# 旧: if not hasattr(strategy, 'df_30m') or strategy.df_30m.empty:
# 新: if not hasattr(strategy, 'df_4h') or strategy.df_4h.empty:
# 旧: df = strategy.df_30m
# 新: df = strategy.df_4h
```

### 3.3 L517 - 绘图用的kline_data_for_plot（无变更，已使用 `hasattr` 通用检查）
不需要修改，因为 `df_processed` 属性不依赖周期命名。

---

## Step 4: 修改 `run_backtest.py` (~6行)

### 4.1 L268-272 - 辅助周期数据加载
```python
# 旧: data_15m = engine.load_data(symbol, "15m", ...)
# 旧: if not data_15m or "15m" not in data_15m:
# 旧: logger.error("15m data missing for MTF strategy")
# 旧: logger.info("15m data: %s rows", len(data_15m["15m"]))
# 新: data_30m = engine.load_data(symbol, "30m", ...)
# 新: if not data_30m or "30m" not in data_30m:
# 新: logger.error("30m data missing for MTF strategy")
# 新: logger.info("30m data: %s rows", len(data_30m["30m"]))
```

### 4.2 L303 - `load_data_for_backtest` 参数
```python
# 旧: strategy.load_data_for_backtest(df_30m=data[interval], df_15m=data_15m["15m"], df_daily=data["1d"])
# 新: strategy.load_data_for_backtest(df_4h=data[interval], df_30m=data_30m["30m"], df_daily=data["1d"])
```

---

## Step 5: 修改 `run_ethusdc_mtf_backtest.py` (~5行)

### 5.1 INTERVAL 常量
```python
# 旧: INTERVAL = "30m"
# 新: INTERVAL = "4h"
```

### 5.2 文档字符串 + print 显示文本
- 文件头docstring: `"30分钟"` → `"4小时"`
- `main()` 函数print标题: `"ETHUSDC 30m+15m 回测"` → `"ETHUSDC 4h+30m 回测"`
- print配置信息: `"K线周期: {INTERVAL} + 15m (多周期)"` → `"K线周期: {INTERVAL} + 30m (多周期)"`
- print策略特性: `"Chan分型引擎 (30m)"` → `"Chan分型引擎 (4h)"`
- print策略特性: `"15m 4信号确认"` → `"30m 4信号确认"`

---

## Step 6: 修改 `run_ethusdc_mtf_live.py` (~2行)

### 6.1 显示文本
- print 标题: `"30m + 15m 双周期"` → `"4h + 30m 双周期"`

---

## Step 7: 验证

### 7.1 导入测试
```bash
cd e:\Auto_test\huyhf
python -c "from trading_system.strategies.mtf_fractal_strategy import MultiTFFractalStrategy, MultiTFFractalStrategyExecutor; print('Import OK')"
```

### 7.2 干运行测试
```bash
python -c "
from trading_system.strategies.mtf_fractal_strategy import MultiTFFractalStrategy
s = MultiTFFractalStrategy(symbol='ETHUSDC', support_levels=[1900,1850], resistance_levels=[2100,2150])
print(f'Attr check: df_4h={hasattr(s, \"df_4h\")}, df_30m={hasattr(s, \"df_30m\")}')
print('Strategy init OK')
"
```

### 7.3 回测运行
```bash
python run_ethusdc_mtf_backtest.py
```
**检查点**:
- 回测无报错完成
- 有交易产生（交易数 > 0）
- 图表正常生成（分型标注无截断）
- 日志中显示 `"4h"` 和 `"30m"` 而非旧周期名

### 7.4 日志检查
确认日志中不再出现 `"30m底分型"`, `"15m背离"` 等旧周期名称，全部替换为 `"4h底分型"`, `"30m背离"` 等。

---

## 风险点与注意事项

1. **`backtest_engine.py` 中 `strategy.df_30m` → `strategy.df_4h`**：引擎在逐K回测时逐条注入4h数据（L581），ATR计算也在引擎侧从 `strategy.df_4h` 读取。确保两处同步修改。

2. **`_process_data()` 时间对齐逻辑**：原逻辑将15m数据按30m主周期时间对齐后注入。改为4h主周期后，30m数据也需按4h时间对齐。时间对齐使用 `open_time` 字段比较。

3. **ChanStrategy `time_frame` 参数**：从 `"30m"` 改为 `"4h"` 后，分型识别的K线窗口 `hg1=8` 保持不变。4h K线的分型将基于8根4h K线（约32小时范围），比之前30m×8=4小时范围大得多，分型级别更高。

4. **实时执行器K线limit**：`_run_once()` 中 `limit=800` 对4h来说将获取约133天数据，足以用于回测。

---

## 执行顺序
1. Step 1：下载数据（先决条件）
2. Step 2：修改核心策略文件（最复杂的部分）
3. Step 3-6：修改支持文件（可并行）
4. Step 7：验证所有修改