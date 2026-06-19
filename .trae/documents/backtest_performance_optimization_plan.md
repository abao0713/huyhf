# Crypto_Chan_4H 回测性能优化方案

## 一、瓶颈分析

通过代码审查发现以下**热点路径**——回测主循环中每根 4H K 线都会触发的操作：

### 1.1 主热点：ChanStrategy._process_data() 冗余计算

| 模块 | 问题 | 每帧耗时估算 |
|------|------|------------|
| `_calculate_macd()` | **重复计算**：引擎已在 `_precompute_all_indicators()` 中预计算了 MACD，但 ChanStrategy 内部 `_process_data()` 仍独立计算一次（含 EMA12/26/9 三次 ewm） | ~15-20ms |
| `_calculate_mavgs()` | 每帧计算 SMA20/60/120 **和** EMA20/60（共 5 条均线），其中 SMA 用 `rolling().mean()` 、EMA 用 `ewm().mean()` | ~20-30ms |
| `_calculate_mavgs()` 内的 `logger.info()` | 即使日志级别设为 WARNING，字符串格式化仍然执行 | ~5ms |
| `_build_pens()` | 每帧全量重建笔（从分型列表 `O(n)` 遍历） | ~2-5ms |
| **合计** | **4H 每帧 total** | **~50-60ms** |

> 按 90 天 ≈ 540 根 4H K 线计算：540 × 60ms ≈ **32 秒纯 overhead**

### 1.2 次要热点

| 模块 | 问题 |
|------|------|
| `_calculate_macd` 内嵌在 `_calculate_macd_all` | 即使预计算逻辑已存在，fallback 路径在每帧仍遍历 3 个周期 |
| `generate_signal` → `evaluate_directives` | 每帧创建多个临时对象（信号的 dict 拷贝） |

## 二、优化方案

### 优化 1：跳过 ChanStrategy 中冗余的 MACD 计算（关键优化）

**文件**: `trading_system/strategies/chan_strategy.py`  
**措施**: 在 ChanStrategy 中添加 `_skip_macd_calc` 标志，当由回测引擎提供预计算结果时，跳过内部 `_calculate_macd()` 调用。

**修改点**:
- `ChanStrategy.__init__` 中添加 `self._external_macd = None` 属性
- `ChanStrategy._process_data` 中检查 `_external_macd`，若已设置则跳过 `_calculate_macd()`
- `CryptoChan4HBacktestEngine._precompute_all_indicators` 中注入预计算的 MACD 到 ChanStrategy 实例

**预期提速**: 每帧节省 ~15-20ms

### 优化 2：回测模式下跳过均线计算（关键优化）

**文件**: `trading_system/strategies/chan_strategy.py`  
**措施**: 在 ChanStrategy 中添加 `_backtest_mode` 标志，当启用时跳过 `_calculate_mavgs()` 和 `_calculate_ema_trend_indicators()`调用。

**修改点**:
- `ChanStrategy.__init__` 中添加 `self._backtest_fast = False`
- `ChanStrategy._process_data` 中检查 `_backtest_fast`，若为 True 则跳过均线计算
- `CryptoChan4HBacktestEngine.__init__` 或 `_precompute_all_indicators` 中设置引擎实例的标志

**预期提速**: 每帧节省 ~20-30ms

### 优化 3：条件日志保护

**文件**: `trading_system/strategies/chan_strategy.py`  
**措施**: 在 `_calculate_mavgs()` 和 `_calculate_ema_trend_indicators()` 中对所有 `logger.info()` 和 `logger.debug()` 调用添加 `if logger.isEnabledFor()` 守卫。

**修改点**:
```python
if logger.isEnabledFor(logging.INFO):
    logger.info(...)
```

**预期提速**: 每帧节省 ~5ms（防止无意义的字符串格式化）

### 优化 4：回测主循环微观优化

**文件**: `trading_system/strategies/mtf_fractal_strategy.py`  
**措施**:
- 将 `generate_signal` 中的 `evaluate_directives()` 结果缓存 (directives 只依赖静态规则)
- 回测引擎 `run()` 方法中避免重复的 `len()` 调用

### 优化 5：添加 `--fast` 命令行参数

**文件**: `run_crypto_chan_backtest.py`  
**措施**: 添加 `--fast` 参数，启用快速回测模式（跳过均线/EMA 计算、禁用详细日志）

## 三、实施步骤

1. 修改 `ChanStrategy.__init__` 添加 `_backtest_fast` 和 `_external_macd` 属性
2. 修改 `ChanStrategy._process_data` 添加条件跳过逻辑
3. 修改 `CryptoChan4HBacktestEngine` 注入预计算的 MACD 并设置快速标志
4. 修改 `run_crypto_chan_backtest.py` 添加 `--fast` 参数
5. 运行回测验证优化效果并修复运行时问题

## 四、预期效果

- 原耗时: 每帧 ~60ms → 优化后: 每帧 ~10-15ms
- 90 天回测: ~32s → ~5-8s
- 加速比: **4-6x**

## 五、验证方法

```bash
python run_crypto_chan_backtest.py --symbol ETH/USDC --days 90 --fast
```

对比优化前后的总耗时和最终报告指标一致性。