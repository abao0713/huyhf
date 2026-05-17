# 修复缠论V2实时交易信号检测问题

## 问题诊断

### 根因分析

脚本运行一晚上"入场次数=0"的根因在 `ChanStrategyV2.generate_signal()` 方法的 `_current_fractal_idx` 管理逻辑有bug。

**具体机制：**

1. `_run_once()` 每60秒执行一次，每次都重新获取800根30m K线，重新 `_process_data()` 重新计算全部61个分型
2. 然后调用 `generate_signal(bar_idx=len(df_processed)-1)`，传入**最后一根K线的索引**(如799)
3. `generate_signal()` 从 `_current_fractal_idx` 开始遍历所有分型，但分型永远不可能出现在最后 hg1=8 根K线的位置（分型需要左右各8根确认），所以 `fractal.idx` 永远 < `bar_idx`(799)，所有分型都被 `skip` 跳过
4. **第一次循环**就把 `_current_fractal_idx` 推到61（分型总数），此后所有循环都立即返回HOLD

```
循环1: _current_fractal_idx 0→61, 所有分型被跳过, 返回HOLD
循环2: _current_fractal_idx=61, len(fractals)=61, 直接返回HOLD
循环N: ...永远HOLD
```

### 次要问题

| 问题 | 描述 |
|------|------|
| 无数据时间戳 | 日志不显示K线数据的最新时间，无法验证数据实时性 |
| 无分型详情 | 只显示"分型=61"，不显示最新分型的类型(顶/底)、位置、价格 |
| 无补救机制 | 重新处理时不会检测之前错过的分型信号 |

---

## 修改计划

### 步骤1：修复 `generate_signal()` — 分型索引管理

**文件:** `trading_system/strategies/chan_strategy_v2.py`

**改动A:** 在 `ChanStrategyV2` 类中添加 `_last_processed_timestamp` 属性，用于跟踪已处理分型：

```python
# 在 __init__ 中添加 (约第148行后)
self._current_fractal_idx = 0
self._last_processed_fractal_ts: Optional[pd.Timestamp] = None  # 新增
```

**改动B:** 修改 `generate_signal()` 方法（约540-611行）：

核心逻辑改为：
1. 每次被调用时，先检查 `_current_fractal_idx` 是否需要重置（如果 `_internal_strategy` 的数据被更新了）
2. 将 bar_idx 参数的含义从"只检查这一根K线"改为"检查所有 <= bar_idx 的新分型"
3. 使用 `_last_processed_fractal_ts` 跳过已经处理过的分型
4. 处理完一个分型后更新 `_last_processed_fractal_ts`

```python
def generate_signal(self, bar_idx: int = None) -> Optional[Dict[str, Any]]:
    if not self.fractals or len(self.fractals) == 0:
        return {"action": "HOLD"}
    
    # 查找 bar_idx 范围内所有未处理的新分型
    # 只处理 fractal.idx <= bar_idx 且 timestamp > _last_processed_fractal_ts 的分型
    
    for i in range(len(self.fractals)):
        fractal = self.fractals[i]
        if fractal.idx > bar_idx:
            break
        
        # 跳过已处理的分型
        if (self._last_processed_fractal_ts is not None and 
            fractal.timestamp <= self._last_processed_fractal_ts):
            continue
        
        # 生成信号...
        signal = self._build_signal_for_fractal(fractal)
        self._last_processed_fractal_ts = fractal.timestamp
        return signal
    
    return {"action": "HOLD"}
```

**改动C:** 在 `_run_once()` 中，数据重新处理后重置 `_current_fractal_idx`：

在 `_sync_internal_data()` 调用后添加：
```python
self.strategy._current_fractal_idx = 0
```

---

### 步骤2：添加数据时间戳日志

**文件:** `trading_system/strategies/chan_strategy_v2.py`

在 `_run_once()` 方法中，获取K线数据后添加最新K线时间日志（约746行后）：

```python
logger.info(f"[ChanStrategyV2Executor] 获取到 {len(continuous_klines)} 条{self.time_frame}K线")

# 新增：打印数据时间范围
if isinstance(continuous_klines, list) and len(continuous_klines) > 0:
    first_time = pd.to_datetime(continuous_klines[0][0], unit='ms')
    last_time = pd.to_datetime(continuous_klines[-1][0], unit='ms')
    logger.info(f"[ChanStrategyV2Executor] K线数据时间范围: {first_time} ~ {last_time}")
    logger.info(f"[ChanStrategyV2Executor] 最新K线时间: {last_time} (距今{(pd.Timestamp.now() - last_time).total_seconds()/60:.1f}分钟前)")
```

日线同理（约765行后）：
```python
logger.info(f"[ChanStrategyV2Executor] 获取到 {len(daily_klines)} 条日线K线")
# 新增日线时间范围日志
```

---

### 步骤3：添加分型详情日志

**文件:** `trading_system/strategies/chan_strategy_v2.py`

在 `_run_once()` 的状态日志（约788行后）中增强，显示最新几个分型的详情：

```python
status = self.strategy.get_status()
logger.info(f"[ChanStrategyV2Executor] V2策略状态: "
           f"分型={status['fractals_count']} | "
           f"持仓={status['position_direction'] or '空仓'} | "
           f"入场次数={status['entry_count']}")

# 新增：显示最新分型详情
if self.strategy.fractals:
    recent = self.strategy.fractals[-5:]  # 最新5个
    f_info = []
    for f in recent:
        f_type = "顶" if f.type == "top" else "底"
        f_price = f.high if f.type == "top" else f.low
        f_info.append(f"{f_type}@{f.idx}({f_price:.2f})")
    logger.info(f"[ChanStrategyV2Executor] 最新分型: {' → '.join(f_info)}")
```

---

### 步骤4：添加错过信号补救机制

**文件:** `trading_system/strategies/chan_strategy_v2.py`

在 `_run_once()` 中，首次运行或数据刷新后，扫描所有未处理的分型并执行信号：

修改 `_run_once()` 的信号处理段（约794行后）：

```python
# 原逻辑：只检查最后一根K线
# bar_idx = len(self.strategy._internal_strategy.df_processed) - 1
# signal = self.strategy.generate_signal(bar_idx=bar_idx)

# 新逻辑：检查所有未处理分型（补救错过信号）
bar_idx = len(self.strategy._internal_strategy.df_processed) - 1
signals = self.strategy.generate_all_pending_signals(bar_idx=bar_idx)

for signal in signals:
    logger.info(f"[ChanStrategyV2Executor] >>> 补救/新V2信号: action={signal['action']}, "
               f"add={signal.get('is_add_position', False)}")
    await self._execute_v2_signal(signal)

if not signals:
    logger.debug(f"[ChanStrategyV2Executor] 无交易信号 (HOLD)")
```

同时在 `ChanStrategyV2` 类中添加 `generate_all_pending_signals()` 方法。

---

### 预期效果

修复后的日志输出示例：
```
[ChanStrategyV2Executor] 获取到 800 条30mK线
[ChanStrategyV2Executor] K线数据时间范围: 2026-05-14 00:00:00 ~ 2026-05-15 07:00:00
[ChanStrategyV2Executor] 最新K线时间: 2026-05-15 07:00:00 (距今0.5分钟前)
[ChanStrategyV2Executor] V2策略状态: 分型=61 | 持仓=空仓 | 入场次数=0
[ChanStrategyV2Executor] 最新分型: 顶@755(2310.50) → 底@768(2285.30) → 顶@780(2302.10) → 底@792(2278.40) → 底@798(2275.20)
[ChanStrategyV2Executor] >>> V2信号: action=BUY, add=False
```

---

## 涉及文件

| 文件 | 改动内容 |
|------|----------|
| `trading_system/strategies/chan_strategy_v2.py` | 核心修复：`generate_signal()`、新增 `generate_all_pending_signals()`、日志增强、分型追踪 |