# 4小时底分型预判策略修改计划

## 一、需求概述

修改 `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`，实现以下功能：

当4小时K线图表中出现可能形成底分型的结构时，在当前K线（第三根K线）完成之前，通过分析对应的15分钟K线数据，提前判断并入场做多。

## 二、核心逻辑架构

### 2.1 当前策略状态
- 已有4小时和30分钟K线数据处理
- 已有底分型检测（基于缠论ChanStrategy）
- 已有30分钟信号检测（背离、形态、趋势线、金叉）

### 2.2 新增功能模块

```
┌─────────────────────────────────────────────────────────┐
│                    4小时底分型预判策略                      │
├─────────────────────────────────────────────────────────┤
│  1. 底分型K1/K2结构检测                                    │
│     - K1: 下跌K线                                         │
│     - K2: 最低点低于K1，高点可高于或低于K1                    │
│     - 当前K线: K3候选                                      │
│  2. 时点判断                                             │
│     - 当前处于4小时K线后半段（第3-4小时）                      │
│     - K3正在形成中                                        │
│  3. 15分钟级别分析                                       │
│     - 15分钟一买检测（底背驰）                              │
│     - 15分钟二买检测（回调不破前低）                          │
│     - 15分钟趋势向上确认                                    │
│  4. 提前入场信号生成                                       │
└─────────────────────────────────────────────────────────┘
```

## 三、详细实现步骤

### 步骤1: 添加15分钟数据支持和初始化

**文件**: `mtf_fractal_strategy.py`

1.1 在 `__init__` 方法中添加:
```python
self.df_15m: pd.DataFrame = pd.DataFrame()
self._chan_first_buy_analyzer = ChanTheoryFirstBuyAnalyzer()  # 一买分析器
```

1.2 修改 `inject_data` 方法，支持15分钟数据注入:
```python
def inject_data(self, df_4h, df_30m, df_15m=None, df_daily=None):
    # 现有逻辑...
    if df_15m is not None:
        self.df_15m = df_15m.copy()
    # 添加15分钟指标计算
    if not self.df_15m.empty:
        self._calculate_indicators_15m()
```

### 步骤2: 实现4小时底分型K1/K2结构检测

新增方法 `_check_4h_bottom_fractal_k1k2`:

```python
def _check_4h_bottom_fractal_k1k2(self) -> Tuple[bool, int, int, int]:
    """
    检测4小时底分型K1/K2结构
    
    返回: (是否有K1/K2结构, K1索引, K2索引, K3候选索引)
    """
    # 1. K1: 下跌K线（收盘<开盘）
    # 2. K2: 最低点低于K1低点
    # 3. K3候选: 当前K线，低点高于K2低点
    
    # 返回值: (has_structure, k1_idx, k2_idx, k3_idx)
```

**判断条件**:
- K1: `close < open`（下跌K线）
- K2: `K2.low < K1.low`
- K3候选: `K3.low > K2.low` AND 当前K线运行中

### 步骤3: 实现时点判断逻辑

新增方法 `_is_in_candle_second_half`:

```python
def _is_in_candle_second_half(self) -> bool:
    """
    判断当前是否处于4小时K线的后半段（第3-4小时）
    
    逻辑: 
    - 获取当前4小时K线的开始时间
    - 计算当前时间距离K线开始已过去多少分钟
    - 如果 >= 120分钟（超过2小时），返回True
    """
```

### 步骤4: 实现15分钟一买（底背驰）检测

新增方法 `_check_15m_first_buy`:

```python
def _check_15m_first_buy(self) -> Tuple[bool, Dict[str, Any]]:
    """
    在15分钟K线中检测第一类买点（底背驰）
    
    参考: chan_first_buy_strategy.py 的 analyze() 方法
    
    返回: (是否检测到一买, 详细分析结果)
    """
    # 使用 ChanTheoryFirstBuyAnalyzer
    result = self._chan_first_buy_analyzer.analyze(
        self.df_15m[-100:],  # 15分钟数据
        self.df_30m[-200:]   # 辅助用30分钟数据
    )
    
    return result.divergence_confirmed, {
        'satisfied_count': result.satisfied_count,
        'suggested_entry': result.suggested_entry_price,
        'stop_loss': result.stop_loss_price,
        'targets': result.targets,
    }
```

### 步骤5: 实现15分钟二买（回调不破前低）检测

新增方法 `_check_15m_second_buy`:

```python
def _check_15m_second_buy(self, first_buy_info: Dict) -> Tuple[bool, Dict[str, Any]]:
    """
    在15分钟K线中检测第二类买点
    
    参考: chan_buy_sell_strategy.py 的二买分析逻辑
    
    条件:
    - 一买后价格反弹
    - 回调低点不破一买低点
    - 回调低点高于K2低点
    """
    # 分析逻辑...
```

### 步骤6: 实现15分钟趋势向上确认

新增方法 `_check_15m_uptrend`:

```python
def _check_15m_uptrend(self) -> Tuple[bool, str]:
    """
    确认15分钟趋势已转为向上
    
    检测方法:
    - MA5 > MA20（短期均线在长期均线上方）
    - 近期低点抬高（LL > HL）
    - 出现连续阳线
    """
```

### 步骤7: 修改信号生成逻辑

修改 `_generate_entry_signal` 方法，新增提前入场分支:

```python
def _generate_early_entry_signal(self) -> Optional[Dict[str, Any]]:
    """
    在K3形成过程中提前入场做多
    
    触发条件:
    1. 4小时底分型K1/K2结构已形成
    2. 当前处于K3后半段
    3. 15分钟级别满足以下任一条件:
       - 15分钟一买确认（底背驰）
       - 15分钟二买确认（回调不破前低）
    4. 15分钟趋势向上确认
    """
```

### 步骤8: 修改数据注入和回测支持

1. 修改 `inject_data` 方法签名:
```python
def inject_data(self, df_4h, df_30m, df_15m=None, df_daily=None):
```

2. 修改 `load_data_for_backtest` 方法:
```python
def load_data_for_backtest(self, df_4h, df_30m=None, df_15m=None, df_daily=None):
    self.inject_data(df_4h, df_30m, df_15m, df_daily)
```

3. 修改回测引擎调用处（`backtest_engine.py`）:
```python
# 如果需要15分钟数据
df_15m = load_15m_data(...)
strategy.inject_data(df_4h, df_30m, df_15m, df_daily)
```

## 四、关键数据结构定义

### 4.1 新增数据类

```python
@dataclass
class BottomFractalK12Structure:
    """4小时底分型K1/K2结构"""
    has_structure: bool = False
    k1_idx: int = -1
    k2_idx: int = -1
    k3_idx: int = -1
    k1_data: Dict = field(default_factory=dict)
    k2_data: Dict = field(default_factory=dict)
    is_k3_forming: bool = False
    k3_partial_data: Dict = field(default_factory=dict)


@dataclass
class EarlyEntrySignal:
    """提前入场信号"""
    action: str = 'HOLD'
    entry_price: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_ratio: float = 0.0
    confidence: float = 0.0  # 0.0-1.0 置信度
    signal_type: str = ''  # 'first_buy', 'second_buy', 'trend_up'
    reason: str = ''
    k1_idx: int = -1
    k2_idx: int = -1
```

## 五、参数配置

在 `__init__` 中新增以下可配置参数:

```python
def __init__(self, ..., 
             enable_early_entry: bool = True,  # 启用提前入场
             early_entry_min_confidence: float = 0.6,  # 最低置信度
             k3_second_half_threshold: float = 0.5,  # K3后半段阈值（默认50%）
             early_entry_ratio: float = 0.25):  # 提前入场仓位比例
```

## 六、代码修改清单

### 6.1 新增方法列表

| 方法名 | 功能 | 行数估计 |
|--------|------|----------|
| `_check_4h_bottom_fractal_k1k2` | 检测K1/K2结构 | ~80行 |
| `_is_in_candle_second_half` | 判断K线后半段 | ~30行 |
| `_calculate_indicators_15m` | 计算15分钟指标 | ~40行 |
| `_check_15m_first_buy` | 15分钟一买检测 | ~50行 |
| `_check_15m_second_buy` | 15分钟二买检测 | ~60行 |
| `_check_15m_uptrend` | 15分钟趋势确认 | ~40行 |
| `_generate_early_entry_signal` | 生成提前入场信号 | ~100行 |

### 6.2 修改方法列表

| 方法名 | 修改内容 |
|--------|----------|
| `__init__` | 添加15分钟数据存储和分析器初始化 |
| `inject_data` | 添加df_15m参数和数据注入 |
| `load_data_for_backtest` | 添加df_15m参数支持 |
| `generate_signal` | 集成提前入场逻辑 |
| `get_status` | 添加提前入场状态信息 |

### 6.3 新增数据成员

```python
self.df_15m: pd.DataFrame  # 15分钟K线数据
self._chan_first_buy_analyzer  # 一买分析器
self._early_entry_enabled  # 是否启用提前入场
self._bottom_fractal_k12: BottomFractalK12Structure  # K1/K2结构状态
```

## 七、测试计划

1. **单元测试**: 测试各新增方法的边界条件
2. **集成测试**: 测试完整的数据注入和信号生成流程
3. **回测测试**: 使用历史数据进行回测验证

## 八、注意事项

1. **数据依赖**: 确保15分钟数据能够正确获取和注入
2. **时点判断**: K线后半段判断需要准确的时间戳支持
3. **背驰检测**: 复用现有的ChanTheoryFirstBuyAnalyzer
4. **性能考虑**: 15分钟数据量较大，需要注意计算效率
5. **置信度设置**: 提前入场风险较高，需要合理设置置信度阈值

## 九、预期效果

修改后，策略将能够:

1. 在4小时K1/K2底分型结构形成后，提前识别K3的入场机会
2. 利用15分钟级别的精确分析，在K3完成前提前入场
3. 结合一买、二买和趋势确认，提高入场信号的可靠性
4. 通过置信度机制，控制提前入场的风险
