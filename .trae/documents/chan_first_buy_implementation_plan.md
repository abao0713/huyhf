# 缠论4小时K线第一类买点（一买）背驰判断与做多分析框架 — 实现计划

## 一、任务概述

基于用户提供的缠论一买分析框架，在现有量化交易系统中实现一个**不依赖MACD的四维度背驰判断模块**。

-   **核心差异**：现有 `chan_strategy.py` 的背驰判断基于MACD面积对比，新策略使用四大维度替代MACD。
-   **目标**：新建独立的策略模块，输出完整的五步分析报告和交易决策建议。

---

## 二、实现文件清单

| 序号 | 文件 | 操作 | 说明 |
| --- | --- | --- | --- |
| 1 | `trading_system/utils/indicators.py` | **追加** | 新增非MACD维度的指标计算函数 |
| 2 | `trading_system/strategies/chan_first_buy_strategy.py` | **新建** | 一买分析核心模块（含五步分析+策略） |
| 3 | `trading_system/strategies/__init__.py` | 检查 | 确保模块可导入 |
| 4 | `run_first_buy_analysis.py` | **新建** | 分析运行脚本入口 |

---

## 三、详细实现步骤

### 步骤1：扩展 `indicators.py` — 新增无MACD维度的指标函数

在 `trading_system/utils/indicators.py` 末尾追加以下函数：

#### 1.1 斜率计算增强
```python
def calculate_price_slope(prices: pd.Series) -> float:
    """对整段序列做线性回归，返回斜率（用于下跌角度对比）"""
```
-   输入：一段价格序列
-   输出：线性回归斜率值

#### 1.2 乖离率计算
```python
def calculate_deviation_rate(close: pd.Series, ma_period: int) -> pd.Series:
    """计算价格与MA的乖离率：(close - MA) / MA * 100%"""
```

#### 1.3 均线斜率判断
```python
def calculate_ma_slope(close: pd.Series, period: int, lookback: int = 10) -> float:
    """计算MA在最近lookback根K线的斜率，判断均线走平/放缓"""
```

#### 1.4 成交量对比
```python
def calculate_volume_ratio(current_vol: float, previous_vol: float) -> float:
    """计算成交量比例：当前量/前次量"""
```

#### 1.5 量价关系检测
```python
def detect_volume_price_pattern(df: pd.DataFrame, recent_bars: int = 20) -> Dict[str, bool]:
    """检测下跌放量→反弹无量 是否转换为 下跌缩量→反弹温和放量"""
```

#### 1.6 K线复杂度/数量统计
```python
def count_klines_between_lows(df: pd.DataFrame, start_idx: int, end_idx: int) -> int:
    """统计两低点之间的K线数量"""
```

#### 1.7 反弹力度评估
```python
def calculate_bounce_strength(df: pd.DataFrame, segment_start: int, segment_end: int) -> Dict[str, float]:
    """计算一段时间内每次反弹的幅度和力度"""
```

---

### 步骤2：新建 `chan_first_buy_strategy.py` — 核心分析模块

文件路径：`trading_system/strategies/chan_first_buy_strategy.py`

#### 2.1 数据结构定义

```python
@dataclass
class ZhongShu:
    """中枢（震荡区间）"""
    start_idx: int
    end_idx: int
    upper: float    # 中枢上沿
    lower: float    # 中枢下沿
    direction: str  # "down" / "up"

@dataclass
class DownSegment:
    """下跌段"""
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    slope: float
    kline_count: int
    bounce_strengths: List[float]

@dataclass
class DimensionResult:
    """单个维度判断结果"""
    name: str
    satisfied: bool
    details: List[str]  # 各子信号的详细说明

@dataclass
class FirstBuyAnalysisResult:
    """一买完整分析结果"""
    # 第一步：趋势背景
    has_downtrend: bool
    zhongshu_count: int
    in_final_exit_segment: bool
    trend_details: str

    # 第二步：四大维度
    dimensions: List[DimensionResult]

    # 第三步：综合判定
    satisfied_count: int
    divergence_confirmed: bool

    # 第四步：做多决策
    entry_conditions_met: bool
    suggested_entry_price: float
    stop_loss_price: float
    targets: List[float]
    position_advice: Dict[str, float]

    # 第五步：跟踪要点
    second_buy_zone: Optional[Tuple[float, float]]

    # 原始数据
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None
```

#### 2.2 分析器类 `ChanTheoryFirstBuyAnalyzer`

```python
class ChanTheoryFirstBuyAnalyzer:
    """缠论4H第一类买点分析器"""

    def __init__(
        self,
        # 可配置参数
        deviation_ratio_threshold: float = 0.8,      # 乖离率显著缩小阈值
        volume_shrink_threshold: float = 0.7,          # 量缩显著阈值
        slope_flatten_threshold: float = 0.3,          # 斜率放缓阈值
        min_zhongshu_for_buy: int = 2,                 # 最低中枢数
        min_dimensions_for_divergence: int = 2,        # 最低满足维度数
    ):
        ...
```

##### 核心方法：

1.  **`analyze(df_4h: pd.DataFrame, df_30m: pd.DataFrame) -> FirstBuyAnalysisResult`**
    -   主入口方法，依次调用五步分析

2.  **`_step1_check_trend_background(df) -> Tuple[bool, int, bool, str]`**
    -   确认下跌趋势存在
    -   识别下跌中枢数量（至少2个）
    -   判断当前是否处于最后一个下跌中枢之后的向下离开段
    -   复用现有的分型/笔/中枢识别逻辑

3.  **`_step2_dimension1_price_structure(df, down_segments) -> DimensionResult`**
    -   子信号1：斜率对比（最后一段斜率 < 前一段斜率）
    -   子信号2：持续时间与复杂度（K线数量更多、结构更复杂）
    -   子信号3：波动幅度收敛（反弹增强、下跌笔幅度减小）
    -   满足任意1个子信号则本维度成立

4.  **`_step2_dimension2_ma_system(df, low_points) -> DimensionResult`**
    -   子信号1：乖离率变化（最新乖离率/前次乖离率 < 0.8）
    -   子信号2：长期均线形态（60/120周期均线斜率走平）
    -   满足任意1个子信号则本维度成立

5.  **`_step2_dimension3_volume_verification(df, low_points) -> DimensionResult`**
    -   子信号1：价跌量缩（最新低点量/前次低点量 < 0.7）
    -   子信号2：量价关系转变（下跌缩量+反弹温和放量）
    -   满足任意1个子信号则本维度成立

6.  **`_step2_dimension4_mtf_confirmation(df_4h, df_30m) -> DimensionResult`**
    -   子信号：30分钟图上也出现清晰趋势背驰结构
    -   调用本分析器对30分钟数据进行递归检查
    -   满足则本维度成立

7.  **`_step3_comprehensive_judgment(dimensions) -> Tuple[int, bool]`**
    -   统计满足维度数
    -   至少2个 → 背驰成立

8.  **`_step4_trading_decision(result, df) -> Dict`**
    -   进场条件：底分型停顿验证、价格不创新低
    -   仓位管理：首仓20%-30%、加仓30%-40%
    -   止损：最低点下方1%-2%
    -   目标：中枢下沿→中枢上沿→趋势起点

9.  **`_step5_followup_checkpoints(result) -> List[str]`**
    -   生成后续跟踪要点清单

##### 辅助方法：

10. **`_identify_zhongshu(pens, direction='down') -> List[ZhongShu]`**
    -   通过三笔重叠（连续三笔有价格重叠区间）识别中枢

11. **`_identify_down_segments(df) -> List[DownSegment]`**
    -   识别所有下跌段及其属性

12. **`_find_low_points(df) -> List[Dict]`**
    -   找到所有阶段性低点（价格+成交量+时间）

13. **`_check_bottom_fractal_confirm(df, lookback=5) -> bool`**
    -   确认底分型停顿/验证信号

14. **`_generate_report(result) -> str`**
    -   生成可读的文字分析报告

#### 2.3 策略类 `ChanFirstBuyStrategy`

```python
class ChanFirstBuyStrategy(BaseStrategy):
    """继承BaseStrategy，对接回测/实盘引擎"""

    def __init__(self, symbol, time_frame='4h', ...):
        super().__init__("ChanFirstBuyStrategy")
        self.analyzer = ChanTheoryFirstBuyAnalyzer(...)
        ...

    async def initialize(self, symbol: str) -> bool:
        # 获取4H和30M数据
        ...

    async def on_bar(self, bar_data) -> Optional[Dict]:
        # 运行analyzer.analyze()
        # 返回交易信号
        ...
```

---

### 步骤3：确保 `__init__.py` 导出正常

检查 `trading_system/strategies/__init__.py`，确认可以正常导入新模块。

---

### 步骤4：创建运行脚本 `run_first_buy_analysis.py`

```python
"""
缠论4H第一类买点分析 — 独立运行脚本
支持：实时分析 | 历史回测 | 可视化报告
"""
```
-   获取ETHUSDC或指定品种的4H + 30M K线数据
-   调用 `ChanTheoryFirstBuyAnalyzer.analyze()`
-   打印完整的五步分析报告
-   可选：调用可视化模块绘制分析图表

---

## 四、与现有代码的关系

| 现有模块 | 复用方式 |
| --- | --- |
| `chan_strategy.py` Fractal/Pen/Segment | 导入复用分型识别、笔构建逻辑 |
| `indicators.py` calculate_ma/ema | 直接调用已有函数 |
| `market_data.py` | 复用K线获取接口 |
| `chan_plotter.py` | 可扩展绘图功能 |
| `base_strategy.py` | 继承实现策略接口 |
| `mtf_fractal_strategy.py` | 参考多周期数据获取模式 |

---

## 五、实现顺序

1.  **先完成基础定义**（用户要求）：
    -   在 `indicators.py` 追加新的指标函数
    -   在 `chan_first_buy_strategy.py` 中定义所有 `@dataclass` 数据结构
    -   实现 `ChanTheoryFirstBuyAnalyzer` 类的**框架骨架**（所有方法签名+空实现/返回默认值）

2.  **再填充核心逻辑**：
    -   实现 `_step1_check_trend_background`
    -   实现四个维度的判断方法
    -   实现综合判定和交易决策

3.  **最后组装与测试**：
    -   创建运行脚本
    -   获取实际数据运行验证

---

## 六、关键设计决策

1.  **中枢识别复用现有逻辑**：直接从 `chan_strategy.py` 导入分型/笔识别函数，在中枢识别上新增逻辑
2.  **不依赖MACD**：所有背驰判断基于价格行为、均线和成交量
3.  **配置可调**：每个维度的阈值、最低满足条件数均可配置
4.  **独立模块**：新策略独立于V1/V2/MTF，不修改现有策略代码
5.  **完整分析报告**：除交易信号外，输出可读的文字分析报告