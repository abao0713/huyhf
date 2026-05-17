# MTF策略6项优化实施计划

## 背景
经过前3步优化（步骤1-3已完成），策略参数已调整。现在需要完成剩余的步骤4-6，然后进行语法检查和回测验证。

## 已完成（回顾）
| 步骤 | 内容 | 状态 |
|------|------|------|
| 步骤1 | 止损改为K2低点/高点参考（做多取min(K2止损, ATR止损)，做空取max） | ✅ 完成 |
| 步骤2 | k3_second_half_threshold 0.5 → 0.4 | ✅ 完成 |
| 步骤3 | profit_loss_ratio 1.5 → 2.5 | ✅ 完成 |

---

## 步骤4: 平仓逻辑重构 — 提前反向分型平60%，标准分型平40%

### 现状
- `_generate_long_exit_signal()` (L1523-1557)：检查30m反转信号和阻力区+顶分型来判断反手做空
- `_generate_short_exit_signal()` (L1559-1599)：镜像逻辑
- `_execute_trade()` 已处理 CLOSE_LONG/CLOSE_SHORT，但无部分平仓能力
- `_close_long()` (L1559-1629) 和 `_close_short()` (L1694-1764) 都是全平

### 实施方案

#### 4a. 在 `backtest_engine.py` `_execute_trade()` 中新增 PARTIAL_CLOSE 处理
**位置**: L1250 之后（EARLY_SHORT_ENTRY 处理之后，`action = signal.get("action")` 之前）

新增：
```python
elif action == "PARTIAL_CLOSE_LONG":
    close_ratio = signal.get("close_ratio", 0.60)
    self._close_long_partial(close_price, close_time, signal.get("reason", "[LONG] 提前顶分型→平60%"), close_ratio)
    signal["action"] = "SELL"
    signal["is_mtf_close_partial"] = True
    is_mtf_signal = True
elif action == "PARTIAL_CLOSE_SHORT":
    close_ratio = signal.get("close_ratio", 0.60)
    self._close_short_partial(close_price, close_time, signal.get("reason", "[SHORT] 提前底分型→平60%"), close_ratio)
    signal["action"] = "BUY"
    signal["is_mtf_close_partial"] = True
    is_mtf_signal = True
```

注意：CLOSE_LONG 的 close_price/close_time 获取逻辑需要提取到 PARTIAL_CLOSE 之前共用。需要重构 L1191-1222 的价格/时间获取代码。

#### 4b. 新增 `_close_long_partial()` 和 `_close_short_partial()` 方法
**文件**: `e:\Auto_test\huyhf\trading_system\strategies\backtest_engine.py`
**位置**: 在 `_close_long()` 方法后面（L1629 后）

```python
def _close_long_partial(self, timestamp, price, reason, close_ratio=0.60):
    """平部分多单"""
    if self.long_position <= 0 or price <= 0:
        return None
    qty = self.long_position * close_ratio
    proceeds = qty * price * (1 - self.config.commission)
    cost = qty * self.long_avg_price
    profit = proceeds - cost
    profit_pct = (profit / cost * 100) if cost > 0 else 0.0
    
    if profit < 0:
        self.consecutive_losses += 1
    else:
        self.consecutive_losses = 0
    
    self.balance += proceeds
    self.long_position -= qty
    # avg_price保持不变（剩余仓位的成本基础不变）
    
    trade = TradeRecord(...)
    self.trades.append(trade)
    return trade
```

做空镜像：
```python
def _close_short_partial(self, timestamp, price, reason, close_ratio=0.60):
    """平部分空单"""
    if self.short_position <= 0 or price <= 0:
        return None
    qty = self.short_position * close_ratio
    proceeds = qty * price * (1 - self.config.commission)
    cost = qty * self.short_avg_price
    profit = cost - proceeds  # 空单盈亏
    profit_pct = ((self.short_avg_price - price) / self.short_avg_price * 100) if self.short_avg_price > 0 else 0.0
    
    if profit < 0:
        self.consecutive_losses += 1
    else:
        self.consecutive_losses = 0
    
    self.balance += proceeds
    self.short_position -= qty
    
    trade = TradeRecord(...)
    self.trades.append(trade)
    return trade
```

#### 4c. 重写 `_generate_long_exit_signal()`
**文件**: `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`
**位置**: 替换 L1523-1557

新逻辑：
```python
def _generate_long_exit_signal(self) -> Optional[Dict]:
    """
    多单退出信号生成（新逻辑）：
    1. 检测提前顶分型K1/K2 + K3形成中 → PARTIAL_CLOSE_LONG (平60%)
    2. 检测标准顶分型确认 → CLOSE_LONG (平剩余40%)
    3. 回退：30m反转信号 + 阻力区检测
    """
    price = float(self.df_4h.iloc[-1]["close"])
    
    # Step 1: 检测提前顶分型K1/K2
    top_k1k2 = self._check_4h_top_fractal_k1k2()
    if top_k1k2.has_structure and top_k1k2.is_k3_forming:
        # 检测到可能形成顶分型 → 平60%
        logger.info(f"[LONG退出] 检测到提前顶分型K1/K2结构 → PARTIAL_CLOSE 60%")
        return {
            "action": "PARTIAL_CLOSE_LONG",
            "strategy": self.name,
            "reason": f"提前顶分型→平60%",
            "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
            "price": price,
            "close_ratio": 0.60,
        }
    
    # Step 2: 检测标准顶分型确认
    has_top_fractal, _, _ = self._check_4h_top_fractal()
    if has_top_fractal:
        logger.info(f"[LONG退出] 检测到标准顶分型确认 → CLOSE_LONG")
        signal = {
            "action": "CLOSE_LONG",
            "strategy": self.name,
            "reason": "顶分型确认→平剩余",
            "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
            "price": price,
        }
        
        # 检查是否同时满足做空条件（反手）
        in_resistance, _ = self._check_resistance_zone()
        if in_resistance:
            short_count, short_signals = self._check_30m_short_signals()
            if short_count >= self.min_signal_count:
                short_active = [name for name, active in short_signals.items() if active]
                signal["action"] = "REVERSE_TO_SHORT"
                signal["reason"] = f"顶分型确认+阻力区→反手做空({', '.join(short_active)})"
                signal["short_signals"] = short_active
                signal["short_position_info"] = {
                    "entry_price": price,
                    "probe_ratio": self.probe_ratio,
                    "confirm_ratio": self.confirm_ratio,
                }
                logger.info("[REVERSE_TO_SHORT] 多单退出反手做空")
        return signal
    
    # Step 3: 回退到30m反转信号检测
    exit_signals = self._check_long_exit_signals()
    signal_count = sum(1 for v in exit_signals.values() if v)
    if signal_count < self.min_signal_count:
        return None
    
    active_signals = [name for name, active in exit_signals.items() if active]
    logger.info(f"[LONG退出] 30m做多退出信号: {', '.join(active_signals)} ({signal_count}/{self.min_signal_count})")
    
    signal = {
        "action": "CLOSE_LONG",
        "strategy": self.name,
        "reason": f"30m反转信号: {', '.join(active_signals)}",
        "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
        "price": price,
    }
    return signal
```

#### 4d. 重写 `_generate_short_exit_signal()`（镜像）
**位置**: 替换 L1559-1599

```python
def _generate_short_exit_signal(self) -> Optional[Dict]:
    """
    空单退出信号生成（新逻辑）：
    1. 检测提前底分型K1/K2 + K3形成中 → PARTIAL_CLOSE_SHORT (平60%)
    2. 检测标准底分型确认 → CLOSE_SHORT (平剩余40%)
    3. 回退：30m反转信号 + 支撑区检测
    """
    price = float(self.df_4h.iloc[-1]["close"])
    
    # Step 1: 检测提前底分型K1/K2
    bottom_k1k2 = self._check_4h_bottom_fractal_k1k2()
    if bottom_k1k2.has_structure and bottom_k1k2.is_k3_forming:
        logger.info(f"[SHORT退出] 检测到提前底分型K1/K2结构 → PARTIAL_CLOSE 60%")
        return {
            "action": "PARTIAL_CLOSE_SHORT",
            "strategy": self.name,
            "reason": f"提前底分型→平60%",
            "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
            "price": price,
            "close_ratio": 0.60,
        }
    
    # Step 2: 检测标准底分型确认
    has_bottom_fractal, _, _ = self._check_4h_bottom_fractal()
    if has_bottom_fractal:
        logger.info(f"[SHORT退出] 检测到标准底分型确认 → CLOSE_SHORT")
        signal = {
            "action": "CLOSE_SHORT",
            "strategy": self.name,
            "reason": "底分型确认→平剩余",
            "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
            "price": price,
        }
        
        # 检查是否同时满足做多条件（反手）
        in_support, _ = self._check_support_zone()
        if in_support:
            long_count, long_signals = self._check_30m_signals()
            if long_count >= self.min_signal_count:
                long_active = [name for name, active in long_signals.items() if active]
                signal["action"] = "REVERSE_TO_LONG"
                signal["reason"] = f"底分型确认+支撑区→反手做多({', '.join(long_active)})"
                signal["long_signals"] = long_active
                signal["long_position_info"] = {
                    "entry_price": price,
                    "probe_ratio": self.probe_ratio,
                    "confirm_ratio": self.confirm_ratio,
                }
                logger.info("[REVERSE_TO_LONG] 空单退出反手做多")
        return signal
    
    # Step 3: 回退到30m反转信号检测
    exit_signals = self._check_short_exit_signals()
    signal_count = sum(1 for v in exit_signals.values() if v)
    if signal_count < self.min_signal_count:
        return None
    
    active_signals = [name for name, active in exit_signals.items() if active]
    logger.info(f"[SHORT退出] 30m做空退出信号: {', '.join(active_signals)} ({signal_count}/{self.min_signal_count})")
    
    signal = {
        "action": "CLOSE_SHORT",
        "strategy": self.name,
        "reason": f"30m反转信号: {', '.join(active_signals)}",
        "timestamp": self.df_4h.iloc[-1].get("open_time", pd.Timestamp.now()),
        "price": price,
    }
    return signal
```

### 关键注意事项
1. **部分平仓后的仓位追踪**：`_close_long_partial` 平掉60%后，剩余40%仓位仍在。后续的 `_check_long_stop_loss` 和标准退出仍然有效。
2. **避免重复部分平仓**：需要在策略中添加状态标记 `_long_partial_closed` / `_short_partial_closed`，防止同一笔交易多次触发 PARTIAL_CLOSE。
3. **信号顺序**：PARTIAL_CLOSE_LONG 返回后，`_execute_trade` 将其转换为 SELL 记录到 trades。策略通过 `clear_position` 后 `position_state.direction` 仍为 "long"（因为只平了60%），下一根K线检测时如果标准顶分型确认，再发 CLOSE_LONG 平剩余。

---

## 步骤5: 15分钟K线数据日期扩展30天

### 现状
- `run_backtest.py` L314: 15m数据加载使用与主周期相同的 start_date
- `backtest_engine.py` L604-606: 已将完整15m上下文传递给策略（无需修改）

### 实施方案

#### 5a. 修改 `run_backtest.py` 的15m数据加载
**文件**: `e:\Auto_test\huyhf\trading_system\backtest\run_backtest.py`
**位置**: L314

```python
# 修改前:
data_15m = engine.load_data(symbol, "15m", start_date=start_date, end_date=end_date)

# 修改后:
from datetime import timedelta
extended_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")
data_15m = engine.load_data(symbol, "15m", start_date=extended_start, end_date=end_date)
logger.info(f"15m数据扩展30天上下文: {extended_start} ~ {end_date}")
```

需要确保顶部已有 `from datetime import datetime, timedelta` 导入。

#### 5b. Binance API 1000根限制说明
- CSV回测不受限制（CSV文件包含完整数据）
- 实时拉取模式：30天 × 24h × 4根/h = 2880根15m K线，需分3次API请求
- 此改动**仅**影响 `trading_system/data/binance_data_manager.py` 中的 `load_data` 方法，且仅在使用API实时拉取时需要处理。当前 `load_data` 使用CSV优先策略，暂不需修改。

---

## 步骤6: 图表标签和K线索引显示修复

### 问题分析

**问题6a: K线索引250后才显示交易**
- 90天 × 6根/天 = 约540根4h K线。前250根（约42天）无信号是正常的——缠论分型检测需要足够的K线历史积累。
- `_is_in_candle_second_half()` 使用 `pd.Timestamp.now()` 在回测中始终返回 True（历史K线经过的时间远超阈值），所以不是它导致延迟。实际上这个"bug"让所有回测K线都能通过后半段检测，反而是放宽了条件。
- 信号时间戳通过 `chan_plotter.py` 的 timestamp→K线索引映射定位。如果信号时间戳在K线open_time之前，会被映射到后续K线。这是可能的问题点，但不是根本原因。
- **结论**：前250根无交易属于正常现象，但可通过以下方式改善：确保信号 timestamp 使用的是 K线 open_time 而非其他时间戳。

**问题6b: 卖出标记全部显示"止损"**
- 回测循环先检查止损止盈（L619-623），再调用 `strategy.generate_signal()`（L626）
- 如果K2止损（步骤1更宽的止损）先触发，`_check_long_stop_loss` 中的 `stop_reason = "止损"` 被写入 TradeRecord
- 图表上显示的标签来自 `signal.get('reason')` 或 TradeRecord 的 reason 字段
- 理想情况：如果策略检测到反向分型并发出了 REVERSE_TO_SHORT，应显示"反手做空"

### 实施方案

#### 6a. 优化止损reason文本
**文件**: `e:\Auto_test\huyhf\trading_system\strategies\backtest_engine.py`
**位置**: `_check_long_stop_loss()` L993-1005 和 `_check_short_stop_loss()` L1043-1053

多单止损reason优化：
```python
# 修改前:
stop_reason = "止损"
# 修改后:
stop_reason = f"止损@{effective_stop_loss:.2f}"

# _close_long调用:
self._close_long(open_time, exit_price, f"[LONG] {stop_reason}")
```

同时保留利润/亏损判断：如果 profit_pct > 0 显示"止盈"，否则显示"止损@价格"。

#### 6b. 确保策略退出信号reason清晰
在步骤4c和4d中已包含清晰的reason文本：
- `"提前顶分型→平60%"` — 用于 PARTIAL_CLOSE_LONG
- `"顶分型确认→平剩余"` — 用于 CLOSE_LONG
- `"顶分型确认+阻力区→反手做空(...)"` — 用于 REVERSE_TO_SHORT

图表只显示 `reason[:10]` 字符（参见 chan_plotter.py L487 和 L558），所以需要确保关键信息在前10个字符内。

#### 6c. 验证K线时间对齐
- 确认策略信号中的 `timestamp` 使用 `self.df_4h.iloc[-1].get("open_time")`（当前代码已正确使用）
- `chan_plotter.py` 的 timestamp 映射逻辑（L393-418）使用 `>= signal_time` 查找，合理

---

## 步骤7: 语法检查与回测验证

### 7a. 语法/Lint检查
```bash
cd e:\Auto_test\huyhf
python -m py_compile trading_system/strategies/mtf_fractal_strategy.py
python -m py_compile trading_system/strategies/backtest_engine.py
python -m py_compile trading_system/backtest/run_backtest.py
```

### 7b. 运行回测
```bash
python run_ethusdc_mtf_backtest.py
```

### 7c. 验证要点
1. PARTIAL_CLOSE_LONG/SHORT 正确触发（日志中应有 "检测到提前顶分型K1/K2结构 → PARTIAL_CLOSE 60%"）
2. 部分平仓后剩余仓位被标准分型或止损正确清理
3. 图表标签区分 "提前顶分型"、"反手做空"、"止损" 等不同原因
4. 盈亏比 2.5 对应的止盈距离合理

---

## 实施顺序

1. **步骤5a** — 15m数据扩展（独立，最简单）
2. **步骤4b** — 新增 `_close_long_partial` / `_close_short_partial`（依赖最少）
3. **步骤4a** — `_execute_trade()` 新增 PARTIAL_CLOSE 处理
4. **步骤4c/4d** — 重写退出信号方法（依赖4a和4b）
5. **步骤6a** — 止损reason文本优化
6. **步骤6c** — K线时间对齐验证（如有需要）
7. **步骤7a** — 语法检查
8. **步骤7b** — 运行回测

---

## 文件修改汇总

| 文件 | 修改内容 |
|------|---------|
| `mtf_fractal_strategy.py` | 重写 `_generate_long_exit_signal()` 和 `_generate_short_exit_signal()` |
| `backtest_engine.py` | 新增 `_close_long_partial()` 和 `_close_short_partial()`；`_execute_trade()` 添加 PARTIAL_CLOSE 处理；优化 `_check_long_stop_loss`/`_check_short_stop_loss` reason文本 |
| `run_backtest.py` | 15m数据 start_date 扩展30天 |
| `run_ethusdc_mtf_backtest.py` | 参数显示更新（盈亏比、K3阈值等） |

---

## 风险评估

1. **部分平仓状态追踪**：如果 PARTIAL_CLOSE 触发后立即又触发（同一根K线），需要去重。建议添加 `_long_partial_closed_at_bar` 状态标记。
2. **止损与策略退出的竞争**：止损在 `_check_long_stop_loss` 中先于 `generate_signal` 执行。如果K2止损太紧，可能在策略检测到反向分型前就止损出局。这是合理的——K2被突破说明形态已失效。
3. **15m数据扩展**：如果CSV文件中没有扩展日期范围内的数据，`load_data` 会返回空或部分数据。需确认数据文件覆盖了扩展后的日期范围。