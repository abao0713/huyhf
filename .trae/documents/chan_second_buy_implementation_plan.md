# 缠论第二类买点（二买）判断与做多入场框架 — 实现计划

## 一、任务概述

基于已实现的"一买"（底背驰做多）框架，新增"二买"（第二类买点）分析逻辑。二买是确认性买点，其存在完全依赖一买，核心判定标准是：一买后的回调不破一买低点，且处于第一个上涨中枢的构建过程中。

## 二、二买核心判断逻辑（来自用户规范）

```
A[一买确认] → B[一买后首段上涨] → C[上涨后出现回调]
C → D{回调低点 > 一买低点?}
D -- 否 → E[二买不成立]
D -- 是 → F[二买区域确立]
F → G[30M小级别背驰验证]
G -- 是 → H[第二类买点确认 → 执行入场]
```

**强度分级**：
- 强势二买：回调低点位于第一个上涨中枢上沿上方
- 标准二买：回调低点落入第一个上涨中枢区间内部
- 弱势二买：回调低点低于中枢下沿但高于一买低点

---

## 三、实现文件清单

| 序号 | 文件 | 操作 | 说明 |
| --- | --- | --- | --- |
| 1 | `trading_system/strategies/chan_first_buy_strategy.py` | **修改** | 修复 line 88 缩进 + 新增 `SecondBuyAnalysisResult` 数据结构 + 7个二买分析方法 + 二买报告 |
| 2 | `trading_system/strategies/__init__.py` | **修改** | 新增 `SecondBuyAnalysisResult`、`run_second_buy_analysis` 导出 |
| 3 | `run_first_buy_analysis.py` | **修改** | 新增 `--direction second-buy` 参数 |

---

## 四、详细实现步骤

### 步骤1：修复 `chan_first_buy_strategy.py` 已有缺陷

- 修复 line 88 `down_segments` 缩进（应为 4 空格，位于 dataclass 内部）

### 步骤2：新增 `SecondBuyAnalysisResult` 数据结构

```python
@dataclass
class SecondBuyAnalysisResult:
    """二买完整分析结果"""
    first_buy_confirmed: bool          # 一买是否已确认
    first_buy_low: float               # 一买最低点
    first_buy_idx: int                 # 一买点在df中的索引
    has_rise_pullback: bool            # 是否存在一买后的"上涨+回调"结构
    first_rising_zhongshu: Optional[ZhongShu]  # 第一个上涨中枢
    pullback_low: float                # 回调最低点
    pullback_low_idx: int              # 回调最低点索引
    core_condition_met: bool           # 核心条件：回调低点 > 一买低点
    strength_class: str                # 强度分级: 'strong'/'standard'/'weak'
    lower_tf_divergence: bool          # 30M小级别背驰确认
    volume_shrinking: bool             # 回调缩量
    ma_support: bool                   # 均线支撑
    momentum_weakening: bool           # 回调力度减弱
    second_buy_confirmed: bool         # 二买综合确认
    suggested_entry: float             # 建议入场价
    stop_loss: float                   # 止损（一买低点下方）
    targets: List[float]               # 目标位
    position_advice: Dict[str, float]  # 仓位建议
    details: List[str]                 # 详细分析文本
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None
```

### 步骤3：新增 `ChanTheoryFirstBuyAnalyzer` 做空方法

#### 3.1 主入口方法
```python
def analyze_second_buy(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame,
                       first_buy_result: FirstBuyAnalysisResult) -> SecondBuyAnalysisResult:
```

#### 3.2 核心方法链

```python
def _sb_find_first_buy_point(self, df: pd.DataFrame,
                              first_buy_result: FirstBuyAnalysisResult) -> Tuple[int, float]:
    """定位一买最低点在df中的索引和价格"""
    # 策略：找到最后一个下跌中枢的end_idx之后的全局最低点

def _sb_check_rise_pullback_structure(self, df: pd.DataFrame,
                                       first_buy_idx: int) -> Tuple[bool, Optional[ZhongShu], int, float]:
    """检查一买后的"上涨+回调"结构，识别第一个上涨中枢"""

def _sb_classify_strength(self, pullback_low: float, zhongshu: ZhongShu,
                           first_buy_low: float) -> str:
    """强度分级：强势/标准/弱势"""

def _sb_check_lower_tf_divergence(self, df_30m: pd.DataFrame,
                                   first_buy_low: float) -> bool:
    """30分钟小级别背驰确认"""

def _sb_auxiliary_verification(self, df: pd.DataFrame, first_buy_idx: int) -> Tuple[bool, bool, bool]:
    """辅助验证：volume_shrinking, ma_support, momentum_weakening"""

def _sb_trading_decision(self, result: SecondBuyAnalysisResult,
                          df: pd.DataFrame) -> Dict[str, Any]:
    """入场价、止损(一买低点下方)、目标位、仓位(>一买仓位)"""

def generate_second_buy_report(self, result: SecondBuyAnalysisResult) -> str:
    """生成二买分析可读文字报告"""
```

#### 3.3 `_sb_check_rise_pullback_structure` 详细算法

```
1. 从 first_buy_idx 开始取 df 子集
2. 对子集运行 _find_fractals + _build_pens
3. 从笔列表中找出第一段上升笔（方向='up'）
4. 如果第一段上升笔后有一笔下降（回调），则回调结构存在
5. 对该段运行 _identify_zhongshu(pens, direction='up')
   - 如果生成了中枢，这是"第一个上涨中枢"
6. 记录上升笔高点和回调笔低点
7. 返回 (has_structure, zhongshu, pullback_idx, pullback_low)
```

#### 3.4 `_sb_check_lower_tf_divergence` 详细算法

```
1. 在30分钟图上定位一买点之后的数据段
2. 然后定位回调段（30分钟上的内部结构）
3. 对回调段运行 _find_fractals + _build_pens
4. 检查回调段是否存在下跌趋势+中枢+背驰结构
5. 如果30分钟最后一段下跌出现斜率衰减/K线增多/量缩等特征 → 背驰成立
```

### 步骤4：扩展 `ChanFirstBuyStrategy` 策略类

```python
# 新增属性
self.one_buy_low: Optional[float] = None
self.one_buy_idx: Optional[int] = None

# 新增方法
def run_second_buy_analysis(self) -> SecondBuyAnalysisResult:
def get_second_buy_signal(self) -> Optional[Dict[str, Any]]:
```

### 步骤5：新增便捷函数

```python
async def run_second_buy_analysis(symbol: str = 'ETHUSDC') -> SecondBuyAnalysisResult:
```

### 步骤6：更新 `run_first_buy_analysis.py`

新增 `--direction second-buy`：
```bash
python run_first_buy_analysis.py --symbol ETHUSDC --direction second-buy
```
执行流程：先做一买分析，一买确认后自动进行二买分析。

### 步骤7：更新 `__init__.py`

新增导出：`SecondBuyAnalysisResult`、`run_second_buy_analysis`

---

## 五、关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 是否需要先跑一买 | **是** | 二买绝对依赖一买，"没有一买就无所谓二买" |
| 一买点如何定位 | 从df中查找最后下跌中枢之后的最低点 | 最直接、最准确 |
| 第一个上涨中枢如何识别 | 对一买后的df子集运行分型+笔+中枢识别 | 复用现有工具 |
| 30M背驰判断 | 检查30M回调段是否出现下跌趋势+中枢 | 复用现有逻辑，但不做完整的四大维度 |
| 止损设置 | 放在一买最低点下方1%-2% | 用户明确要求 |
| 仓位 | 首仓30%-40%（>一买的20%-30%） | 二买是确认性买点，可重于一买 |

---

## 六、实现顺序

1. 修复 line 88 缩进缺陷
2. 新增 `SecondBuyAnalysisResult` 数据结构
3. 实现 `_sb_find_first_buy_point` + `_sb_check_rise_pullback_structure` + `_sb_classify_strength`
4. 实现 `_sb_check_lower_tf_divergence` + `_sb_auxiliary_verification`
5. 实现 `_sb_trading_decision` + `generate_second_buy_report`
6. 实现主入口 `analyze_second_buy`
7. 扩展 `ChanFirstBuyStrategy` + `run_second_buy_analysis`
8. 更新 `run_first_buy_analysis.py` + `__init__.py`
9. 验证测试