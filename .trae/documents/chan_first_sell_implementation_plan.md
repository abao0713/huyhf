# 缠论趋势顶背驰判断与做空交易逻辑 — 实现计划

## 一、任务概述

基于已实现的"一买"（底背驰做多）框架，新增"一卖"（顶背驰做空）分析逻辑。

- **复用现有架构**：`ChanTheoryFirstBuyAnalyzer`、数据结构、指标函数均可复用/镜像
- **策略**：尽可能共用代码，用 `direction` 参数区分做多/做空，避免大量重复代码

---

## 二、实现文件清单

| 序号 | 文件 | 操作 | 说明 |
| --- | --- | --- | --- |
| 1 | `trading_system/utils/indicators.py` | **追加** | 新增量价关系检测的上升趋势版函数 |
| 2 | `trading_system/strategies/chan_first_buy_strategy.py` | **修改** | 新增 `UpSegment`、`FirstSellAnalysisResult` 数据结构 + 5个做空分析方法 + 做空报告 |
| 3 | `run_first_buy_analysis.py` | **修改** | 新增 `--direction sell` 参数支持做空分析 |

---

## 三、详细实现步骤

### 步骤1：扩展 `indicators.py` — 新增上升趋势量价检测

在 `trading_system/utils/indicators.py` 末尾追加：

```python
def detect_volume_price_pattern_uptrend(df: pd.DataFrame, recent_bars: int = 40) -> dict:
    """检测上升趋势量价关系：上涨放量→回调无量 是否转变为 上涨缩量→回调放量"""
```

- 逻辑与 `detect_volume_price_pattern` 镜像对称
- 前半段：统计上涨K线和回调K线的平均成交量 → 正常模式"上涨放量、回调缩量"
- 后半段：统计上涨K线和回调K线的平均成交量 → 检测是否转变为"上涨缩量、回调放量"
- 返回 `pattern_shifted: bool` 及详细描述

---

### 步骤2：修改 `chan_first_buy_strategy.py` — 新增做空分析

#### 2.1 新增数据结构

```python
@dataclass
class UpSegment:
    """上涨段 — 用于顶背驰分析"""
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    slope: float
    kline_count: int
    pullback_strength_avg: float = 0.0  # 回调力度均值


@dataclass
class FirstSellAnalysisResult:
    """一卖完整分析结果"""
    has_uptrend: bool
    zhongshu_count: int
    in_final_breakout_segment: bool
    trend_details: str
    dimensions: List[DimensionResult] = field(default_factory=list)
    satisfied_count: int = 0
    divergence_confirmed: bool = False
    entry_conditions_met: bool = False
    suggested_entry_price: float = 0.0
    stop_loss_price: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_advice: Dict[str, float] = field(default_factory=dict)
    second_sell_zone: Optional[Tuple[float, float]] = None
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None
    zhongshu_list: List[ZhongShu] = field(default_factory=list)
    up_segments: List[UpSegment] = field(default_factory=list)
```

#### 2.2 分析器扩展：新增做空方法

在 `ChanTheoryFirstBuyAnalyzer` 类中新增以下方法：

##### 主入口方法
```python
def analyze_sell(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame) -> FirstSellAnalysisResult:
    """做空分析主入口，串联五步分析"""
```

##### 五步分析方法（与做多镜像对称）

1. **`_step1_check_uptrend_background(df) -> Tuple[bool, int, bool, str, List[ZhongShu], List[Pen]]`**
   - 确认上涨趋势存在（最后一下跌笔终点高于第一上升笔起点）
   - 识别上涨中枢数量（至少2个，direction='up'）
   - 判断当前是否处于最后一个上涨中枢之后的向上离开段
   - 复用 `_find_fractals`、`_build_pens`、`_identify_zhongshu(direction='up')`

2. **`_step2_sell_dimension1_price_structure(df, up_segments) -> DimensionResult`**
   - 子信号1：斜率衰减（b段斜率 < a段斜率）
   - 子信号2：结构复杂化（b段K线数更多/耗时更久）
   - 子信号3：波动收敛（上涨笔幅度减小、回调笔力度增强）

3. **`_step2_sell_dimension2_ma_system(df, high_points) -> DimensionResult`**
   - 子信号1：乖离缩小（最新乖离率/前次乖离率 < threshold）
   - 子信号2：均线走平（MA60斜率放缓或开始走平）

4. **`_step2_sell_dimension3_volume_verification(df, high_points) -> DimensionResult`**
   - 子信号1：价升量缩（最新高点量/前次高点量 < threshold）
   - 子信号2：量价结构破坏（调用 `detect_volume_price_pattern_uptrend`）

5. **`_step2_sell_dimension4_mtf_confirmation(df_4h, df_30m) -> DimensionResult`**
   - 30分钟出现上涨趋势背驰结构

6. **`_step3_sell_comprehensive_judgment(dimensions) -> Tuple[int, bool]`**
   - 与做多版逻辑相同（≥2个维度满足即成立）

7. **`_step4_sell_trading_decision(result, df) -> Dict`**
   - 进场：顶分型停顿信号确认
   - 止损：最高点上方1%-2%
   - 目标：最近中枢上沿→中枢下沿→趋势起点
   - 仓位：首仓20%-30%，加仓30%-40%

8. **`_step5_sell_followup_checkpoints(result) -> List[str]`**
   - 二卖确认、中枢演化、级别扩展

##### 辅助方法

9. **`_identify_up_segments(df) -> List[UpSegment]`**
   - 利用 `find_price_extremes` 找到局部高点，构建上涨段列表
   - 每段包含斜率、K线数、回调力度均值

10. **`_find_high_points(df) -> List[Dict]`**
    - 找到所有阶段性高点（价格+成交量+时间）

11. **`_check_top_fractal_confirm(df, lookback=8) -> bool`**
    - 确认顶分型停顿/验证信号

12. **`generate_sell_report(result) -> str`**
    - 生成做空分析可读文字报告

#### 2.3 策略类扩展

`ChanFirstBuyStrategy` 新增方法：

```python
def run_sell_analysis(self) -> FirstSellAnalysisResult:
    self.latest_sell_result = self.analyzer.analyze_sell(self.df_4h, self.df_30m)
    return self.latest_sell_result

def get_sell_signal(self) -> Optional[Dict[str, Any]]:
    # 返回做空交易信号
```

新增属性：
```python
self.latest_sell_result: Optional[FirstSellAnalysisResult] = None
```

#### 2.4 模块级便捷函数

```python
async def run_first_sell_analysis(symbol: str = 'ETHUSDC') -> FirstSellAnalysisResult:
    """做空分析便捷函数"""
```

---

### 步骤3：修改 `run_first_buy_analysis.py` — 支持做空方向

- 新增 `--direction` 参数：`long`（默认/做多）或 `sell`（做空）
- 根据方向选择调用 `run_analysis()` 或 `run_sell_analysis()`
- 输出对应的分析报告

```bash
# 做多分析（默认）
python run_first_buy_analysis.py --symbol ETHUSDC

# 做空分析
python run_first_buy_analysis.py --symbol ETHUSDC --direction sell
```

---

### 步骤4：更新 `__init__.py` 导出

在 `trading_system/strategies/__init__.py` 中新增导出：
- `FirstSellAnalysisResult`
- `UpSegment`
- `run_first_sell_analysis`

---

## 四、与做多逻辑的镜像对照表

| 做多（一买） | 做空（一卖） |
| --- | --- |
| `DownSegment` | `UpSegment` |
| `FirstBuyAnalysisResult` | `FirstSellAnalysisResult` |
| `analyze()` | `analyze_sell()` |
| `_step1_check_trend_background(direction='down')` | `_step1_check_uptrend_background(direction='up')` |
| `_identify_down_segments()` | `_identify_up_segments()` |
| `_find_low_points()` | `_find_high_points()` |
| `_step2_dimension1_price_structure` (下跌角度) | `_step2_sell_dimension1_price_structure` (上涨角度) |
| `_step2_dimension2_ma_system` (低点乖离) | `_step2_sell_dimension2_ma_system` (高点乖离) |
| `_step2_dimension3_volume_verification` (低点量缩) | `_step2_sell_dimension3_volume_verification` (高点量缩) |
| `detect_volume_price_pattern` (下跌量价) | `detect_volume_price_pattern_uptrend` (上涨量价) |
| `_check_bottom_fractal_confirm` | `_check_top_fractal_confirm` |
| `generate_report()` | `generate_sell_report()` |
| `get_signal()` | `get_sell_signal()` |
| 止损=最低点×0.98 | 止损=最高点×1.02 |

---

## 五、实现顺序

1. **步骤1**：`indicators.py` 追加 `detect_volume_price_pattern_uptrend`
2. **步骤2**：
   - 新增 `UpSegment` 和 `FirstSellAnalysisResult` 数据结构
   - 实现辅助方法：`_identify_up_segments`、`_find_high_points`、`_check_top_fractal_confirm`
   - 实现五步分析方法
   - 实现 `generate_sell_report`
   - 扩展 `ChanFirstBuyStrategy` 类
   - 新增 `run_first_sell_analysis` 便捷函数
3. **步骤3**：更新 `run_first_buy_analysis.py` 支持 `--direction sell`
4. **步骤4**：更新 `__init__.py` 导出
5. **步骤5**：验证测试（模拟数据 + 实际数据）

---

## 六、关键设计决策

1. **共用 Analyzer 类**：不做新类，在 `ChanTheoryFirstBuyAnalyzer` 中新增做空方法
2. **共用底层工具**：`_find_fractals`、`_build_pens`、`_identify_zhongshu` 完全复用
3. **镜像对称结构**：每个做多做空方法成对存在，命名规则 `_step2_dimension1_xxx` vs `_step2_sell_dimension1_xxx`
4. **独立结果类型**：`FirstBuyAnalysisResult` 和 `FirstSellAnalysisResult` 分开，各自可独立扩展
5. **策略类增强**：`ChanFirstBuyStrategy` 同时支持做多和做空，通过方法名区分