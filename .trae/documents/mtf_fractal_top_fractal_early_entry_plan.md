# 4小时顶分型预判策略修改计划

## 一、需求概述

修改 `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`，实现顶分型提前入场做空功能：

当4小时K线图表中出现可能形成顶分型的结构时，在当前K线（第三根K线）完成之前，通过分析对应的15分钟K线数据，提前判断并入场做空。

**注意**：当前策略已有底分型提前入场做多功能，本次添加的是对称的顶分型提前入场做空功能。

## 二、核心逻辑架构

### 2.1 当前策略状态
- 已有底分型提前入场做多功能（K1/K2结构 + 15分钟一买/二买）
- 已有30分钟顶背离和做空信号检测
- 已有15分钟K线数据支持
- 已有阻力区域检测

### 2.2 新增功能模块

```
┌─────────────────────────────────────────────────────────┐
│                    4小时顶分型预判策略                      │
├─────────────────────────────────────────────────────────┤
│  1. 顶分型K1/K2结构检测                                    │
│     - K1: 上涨K线                                         │
│     - K2: 最高点高于K1，低点可高于或低于K1                    │
│     - 当前K线: K3候选                                      │
│  2. 时点判断                                             │
│     - 当前处于4小时K线周期的后半段（第3-4小时）                      │
│     - K3正在形成中                                        │
│  3. 15分钟级别分析                                       │
│     - 15分钟一卖检测（顶背驰）                              │
│     - 15分钟二卖检测（反弹不过前高）                          │
│     - 15分钟趋势向下确认                                    │
│  4. 提前入场做空信号生成                                       │
└─────────────────────────────────────────────────────────┘
```

## 三、详细实现步骤

### 步骤1: 添加顶分型K1/K2结构数据类

**修改文件**: `mtf_fractal_strategy.py`

1.1 新增数据类 `TopFractalK12Structure`:
```python
@dataclass
class TopFractalK12Structure:
    has_structure: bool = False
    k1_idx: int = -1
    k2_idx: int = -1
    k3_idx: int = -1
    k1_high: float = 0.0
    k1_open: float = 0.0
    k1_close: float = 0.0
    k2_high: float = 0.0
    k2_low: float = 0.0
    k3_partial_low: float = 0.0
    k3_partial_high: float = 0.0
    k3_partial_close: float = 0.0
    is_k3_forming: bool = False
    is_in_second_half: bool = False
    confidence: float = 0.0
```

### 步骤2: 添加初始化参数和数据成员

2.1 在 `__init__` 方法中添加参数:
```python
enable_early_short_entry: bool = True
early_short_entry_min_confidence: float = 0.6
early_short_entry_ratio: float = 0.25
```

2.2 在 `__init__` 方法中添加数据成员:
```python
self._top_fractal_k12: TopFractalK12Structure = TopFractalK12Structure()
self._chan_first_sell_analyzer = ChanTheoryFirstBuyAnalyzer()
```

**注意**: 一卖分析器可以复用 `ChanTheoryFirstBuyAnalyzer`，因为它也实现了 `analyze_sell()` 方法来检测一卖。

### 步骤3: 实现4小时顶分型K1/K2结构检测方法

新增方法 `_check_4h_top_fractal_k1k2`:

```python
def _check_4h_top_fractal_k1k2(self) -> TopFractalK12Structure:
    """
    检测4小时顶分型K1/K2结构
    
    条件:
    - K1: 上涨K线（收盘>开盘）
    - K2: 最高点高于K1高点
    - K3候选: 当前K线，高点低于K2高点
    
    Returns:
        TopFractalK12Structure对象，包含检测结果
    """
    # 逻辑:
    # 1. 检查K1: close > open (上涨K线)
    # 2. 检查K2: high > K1.high
    # 3. 检查K3候选: high < K2.high
    # 4. 计算置信度
    # 5. 检查K3是否在后半段
```

### 步骤4: 实现15分钟一卖（顶背驰）检测

新增方法 `_check_15m_first_sell`:

```python
def _check_15m_first_sell(self) -> Tuple[bool, Dict[str, Any]]:
    """
    在15分钟K线中检测第一类卖点（顶背驰）
    
    参考: chan_first_buy_strategy.py 的 analyze_sell() 方法
    
    Returns:
        Tuple[bool, Dict]: (是否检测到一卖, 详细分析结果)
    """
    # 使用 ChanTheoryFirstBuyAnalyzer 的 analyze_sell 方法
    result = self._chan_first_sell_analyzer.analyze_sell(
        self.df_15m[-200:],
        self.df_30m[-400:] if not self.df_30m.empty else pd.DataFrame()
    )
    
    # 返回 divergence_confirmed 结果
```

### 步骤5: 实现15分钟二卖（反弹不过前高）检测

新增方法 `_check_15m_second_sell`:

```python
def _check_15m_second_sell(self, k1k2_info: TopFractalK12Structure) -> Tuple[bool, Dict[str, Any]]:
    """
    在15分钟K线中检测第二类卖点
    
    条件:
    - 一卖后价格下跌
    - 反弹高点不过一卖高点
    - 反弹高点低于K2高点
    
    Returns:
        Tuple[bool, Dict]: (是否检测到二卖, 详细分析结果)
    """
    # 逻辑:
    # 1. 找到近期高点
    # 2. 确认反弹高点低于一卖高点
    # 3. 确认反弹高点低于K2高点
    # 4. 计算置信度
```

### 步骤6: 实现15分钟趋势向下确认

新增方法 `_check_15m_downtrend`:

```python
def _check_15m_downtrend(self) -> Tuple[bool, str]:
    """
    确认15分钟趋势已转为向下
    
    检测方法:
    - MA5 < MA20 < MA60（短期均线在长期均线下方）
    - 近期高点降低（LH < HL）
    - 出现连续阴线
    
    Returns:
        Tuple[bool, str]: (是否确认趋势向下, 确认原因)
    """
```

### 步骤7: 实现提前入场做空信号生成方法

新增方法 `_generate_early_short_entry_signal`:

```python
def _generate_early_short_entry_signal(self) -> Optional[Dict[str, Any]]:
    """
    在K3形成过程中提前入场做空
    
    触发条件:
    1. 4小时顶分型K1/K2结构已形成
    2. 当前处于K3后半段
    3. 15分钟级别满足以下任一条件:
       - 15分钟一卖确认（顶背驰）
       - 15分钟二卖确认（反弹不过前高）
    4. 15分钟趋势向下确认
    
    Returns:
        Optional[Dict]: 做空入场信号字典
    """
    # 逻辑:
    # 1. 检查是否启用提前做空
    # 2. 检查15分钟数据
    # 3. 检测K1/K2结构
    # 4. 检测15分钟一卖、二卖
    # 5. 确认趋势向下
    # 6. 计算置信度
    # 7. 生成信号
```

### 步骤8: 集成提前做空逻辑到generate_signal

8.1 修改 `_generate_signal_internal` 方法:

```python
# 在 position_state.direction is None 分支中:
if short_signal:
    self._last_short_signal_time = current_time
    return short_signal

# 在长信号和短信号都没有时，添加:
early_short_entry_signal = self._generate_early_short_entry_signal()
if early_short_entry_signal:
    logger.info(f"[MTF] 提前做空信号优先级: {early_short_entry_signal.get('reason', '')}")
    return early_short_entry_signal
```

8.2 修改 `update_position_from_signal` 方法:

```python
elif sig_type == "early_short_entry":
    self.position_state.direction = "short"
    self.position_state.probe_entry_price = signal.get("entry_price", 0)
    self.position_state.k1_idx = signal.get("k1_idx", -1)
    self.position_state.k2_idx = signal.get("k2_idx", -1)
    self.position_state.k3_idx = signal.get("k3_idx", -1)
    self.position_state.stop_loss_price = signal.get("stop_loss", 0)
    self.position_state.confirm_added = False
    logger.info(f"[MTF] 更新持仓: 提前做空入场, 止损={signal.get('stop_loss', 0):.2f}, 置信度={signal.get('confidence', 0):.2f}")
```

### 步骤9: 修改Executor支持提前做空

9.1 在 `MultiTFFractalStrategyExecutor.__init__` 中添加参数:
```python
enable_early_short_entry: bool = True
early_short_entry_min_confidence: float = 0.6
early_short_entry_ratio: float = 0.25
```

9.2 在 `_run_once` 方法中，15分钟数据获取已存在，无需修改

9.3 在 `_execute_signal` 中添加EARLY_SHORT_ENTRY处理:
```python
elif action == "EARLY_SHORT_ENTRY":
    await self._open_early_short_entry(current_price, balance, signal)
```

9.4 新增方法 `_open_early_short_entry`:
```python
async def _open_early_short_entry(self, price: float, balance: float, signal: Dict[str, Any]):
    """执行提前做空入场订单"""
    # 逻辑类似于 _open_early_entry，但是做空方向
    # side="SELL", position_side="SHORT"
```

## 四、信号数据结构

```python
{
    "action": "EARLY_SHORT_ENTRY",
    "type": "early_short_entry",
    "entry_price": float,
    "stop_loss": float,
    "take_profit": float,
    "position": "short",
    "position_ratio": self.early_short_entry_ratio,
    "reason": "提前做空(first_sell/second_sell): 15分钟一卖, 15分钟趋势向下(...)",
    "k1_idx": int,
    "k2_idx": int,
    "k3_idx": int,
    "signal_type": "first_sell" or "second_sell",
    "confidence": float,
    "leverage": int,
    "first_sell_info": Dict,
    "second_sell_info": Dict,
}
```

## 五、代码修改清单

### 5.1 新增数据类

| 类名 | 功能 |
|------|------|
| `TopFractalK12Structure` | 4小时顶分型K1/K2结构跟踪 |

### 5.2 新增方法

| 方法名 | 功能 | 行数估计 |
|--------|------|----------|
| `_check_4h_top_fractal_k1k2` | 检测顶分型K1/K2结构 | ~80行 |
| `_check_15m_first_sell` | 15分钟一卖检测 | ~50行 |
| `_check_15m_second_sell` | 15分钟二卖检测 | ~60行 |
| `_check_15m_downtrend` | 15分钟趋势确认 | ~40行 |
| `_generate_early_short_entry_signal` | 生成提前做空信号 | ~100行 |
| `_open_early_short_entry` | 执行提前做空订单 | ~30行 |

### 5.3 修改方法

| 方法名 | 修改内容 |
|--------|----------|
| `__init__` | 添加做空参数和初始化 |
| `_generate_signal_internal` | 集成提前做空逻辑 |
| `update_position_from_signal` | 添加 early_short_entry 处理 |
| `MultiTFFractalStrategyExecutor.__init__` | 添加做空参数 |
| `_execute_signal` | 添加 EARLY_SHORT_ENTRY 处理 |

### 5.4 新增数据成员

```python
self._top_fractal_k12: TopFractalK12Structure
self._chan_first_sell_analyzer: ChanTheoryFirstBuyAnalyzer
self.enable_early_short_entry: bool
self.early_short_entry_min_confidence: float
self.early_short_entry_ratio: float
```

## 六、与底分型做多功能的对称关系

| 功能 | 底分型做多 | 顶分型做空 |
|------|-----------|-----------|
| K1条件 | close < open (下跌) | close > open (上涨) |
| K2条件 | low < K1.low | high > K1.high |
| K3条件 | low > K2.low | high < K2.high |
| 一买/一卖 | 15分钟一买(底背驰) | 15分钟一卖(顶背驰) |
| 二买/二卖 | 15分钟二买(回调不破) | 15分钟二卖(反弹不过) |
| 趋势 | 向上 | 向下 |
| 信号类型 | EARLY_ENTRY | EARLY_SHORT_ENTRY |
| 方向 | long | short |

## 七、测试要点

1. **K1/K2结构检测**: 测试各种K线组合
2. **时点判断**: 复用现有的 `_is_in_candle_second_half()` 方法
3. **15分钟信号检测**: 测试analyze_sell方法的正确性
4. **置信度计算**: 确保阈值合理
5. **信号生成**: 测试完整的信号生成流程
6. **订单执行**: 测试做空订单的正确性

## 八、预期效果

修改后，策略将能够:

1. 在4小时K1/K2顶分型结构形成后，提前识别K3的入场机会
2. 利用15分钟级别的精确分析，在K3完成前提前入场做空
3. 结合一卖、二卖和趋势确认，提高做空入场信号的可靠性
4. 通过置信度机制，控制提前做空的风险
5. 与底分型做多功能形成对称，完整支持双向提前入场
