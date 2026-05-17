# 缠论类第二类买点（类二买）实现计划

## 一、概述

类二买是缠论趋势延续买点，发生在**第二个及之后的上涨中枢**构建过程中，是上升趋势"空中加油"后的加仓信号。与二买的核心区别：

| 维度 | 二买 | 类二买 |
|------|------|--------|
| 结构位置 | 第一个上涨中枢构建中 | 第二个及之后上涨中枢构建中 |
| 参照物 | 回调低点 > 一买低点 | 回调低点 > 前一个中枢上沿 |
| 市场阶段 | 趋势反转确认（底部刚形成） | 趋势主升延续（上涨已确立） |
| 止损 | 一买低点 × 0.98 | 前中枢上沿下方 |
| 用途 | 首次入场（底仓） | 加仓/追加仓位 |

---

## 二、新增 DataClass

### `SimilarSecondBuyAnalysisResult`

**文件**: `trading_system/strategies/chan_first_buy_strategy.py`

在 `SecondSellAnalysisResult` 之后插入（约L162之后）：

```python
@dataclass
class SimilarSecondBuyAnalysisResult:
    uptrend_established: bool
    rising_zhongshu_count: int
    previous_zhongshu: Optional[ZhongShu] = None
    previous_zhongshu_upper: float = 0.0
    has_breakout_pullback: bool = False
    new_zhongshu: Optional[ZhongShu] = None
    pullback_low: float = 0.0
    pullback_low_idx: int = -1
    core_condition_met: bool = False
    strength_class: str = ''
    lower_tf_divergence: bool = False
    volume_shrinking: bool = False
    ma_support: bool = False
    momentum_weakening: bool = False
    similar_second_buy_confirmed: bool = False
    suggested_entry: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_advice: Dict[str, float] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None
```

**字段说明**：
| 字段 | 含义 |
|------|------|
| `uptrend_established` | 上升趋势是否确立（一买已确认） |
| `rising_zhongshu_count` | 上升趋势中已识别的中枢数量 |
| `previous_zhongshu` | 前一个被突破的上涨中枢 |
| `previous_zhongshu_upper` | 前中枢上沿价格 |
| `has_breakout_pullback` | 是否存在中枢突破+回调结构 |
| `new_zhongshu` | 正在构筑的新中枢 |
| `pullback_low` / `pullback_low_idx` | 回调低点价格和索引 |
| `core_condition_met` | 核心条件：回调低点 > 前中枢上沿 |
| `strength_class` | 强度分级：strong / standard / weak |
| `lower_tf_divergence` | 30M小级别下跌背驰 |
| `volume_shrinking` | 回调缩量 |
| `ma_support` | 均线多头支撑 |
| `momentum_weakening` | 回调力度减弱 |
| `similar_second_buy_confirmed` | 类二买最终确认 |
| `suggested_entry` | 建议入场价 |
| `stop_loss` | 止损价（前中枢上沿下方） |
| `targets` | 目标位列表 |
| `position_advice` | 仓位建议（加仓用，含已有底仓提示） |

---

## 三、新增 Analyzer 方法

全部在 `ChanTheoryFirstBuyAnalyzer` 类中，共8个方法。

### 3.1 `analyze_similar_second_buy(df_4h, df_30m, first_buy_result)` — 主入口

**流程**：
```
1. 前提检查：一买必须已确认 (first_buy_result.divergence_confirmed)
2. 步骤1：_csb_find_rising_zhongshu — 找到一买后所有上涨中枢
   - 需要 >= 2 个中枢，否则终止
3. 步骤2：_csb_check_breakout_structure — 检查中枢突破+回调结构
   - previous_zhongshu = zhongshu_list[-2]（倒数第二个）
   - 验证股价突破该中枢上沿后回调
4. 步骤3：核心几何条件 — 回调低点 > 前中枢上沿
5. 步骤4：_csb_classify_strength — 强度分级
6. 步骤5：_csb_check_lower_tf_divergence — 30M下跌背驰
7. 步骤6：_csb_auxiliary_verification — 辅助验证
8. 综合判定：核心条件 + 小级别背驰 + 辅助信号
9. 步骤7：_csb_trading_decision — 生成交易决策
```

### 3.2 `_csb_find_rising_zhongshu(df, first_buy_idx)` — 找到一买后所有上涨中枢

```python
def _csb_find_rising_zhongshu(self, df, first_buy_idx):
    """
    返回一买之后在上升趋势中识别出的所有上涨中枢列表
    需要从一买索引处开始重新构建笔和中枢
    """
```

**逻辑**：
1. 取 `df.iloc[first_buy_idx:]` 之后的数据
2. 用 `hg1=3` 调用 `_find_fractals` + `_build_pens`
3. 调用 `_identify_zhongshu(pens, direction='up')`
4. 返回中枢列表（索引需要加上 `first_buy_idx` 偏移量）

### 3.3 `_csb_check_breakout_structure(df, prev_zhongshu, zhongshu_list)` — 中枢突破+回调结构

```python
def _csb_check_breakout_structure(self, df, prev_zhongshu, zhongshu_list):
    """
    检查：
    1. 前中枢之后是否有价格突破其上沿
    2. 突破后是否有回调
    3. 回调正在形成新中枢
    返回: (has_structure, new_zhongshu, pullback_idx, pullback_low)
    """
```

**逻辑**：
1. 从前中枢 `end_idx` 开始检查
2. 确认价格曾突破 `prev_zhongshu.upper`（后续K线high > prev_zhongshu.upper）
3. 在突破后寻找回调低点（从 `zhongshu_list[-1]` 的构建笔中找最低的向下笔低点）
4. 新中枢 = `zhongshu_list[-1]`（如果存在）

### 3.4 `_csb_classify_strength(pullback_low, prev_zhongshu, new_zhongshu)` — 强度分级

```python
def _csb_classify_strength(self, pullback_low, prev_zhongshu, new_zhongshu):
```

| 级别 | 条件 | 含义 |
|------|------|------|
| `strong` | pullback_low >> prev_zhongshu.upper（远高于，甚至不触及短期均线）| 强势调整，多头极强 |
| `standard` | pullback_low 在 prev_zhongshu.upper 附近获得支撑 | 标准类二买 |
| `weak` | pullback_low 贴近 prev_zhongshu.upper（接近跌破）| 警示信号 |

具体量化：
- **strong**: `pullback_low >= prev_zhongshu.upper * 1.02`
- **standard**: `prev_zhongshu.upper < pullback_low < prev_zhongshu.upper * 1.02`
- **weak**: 其他

### 3.5 `_csb_check_lower_tf_divergence(df_30m, ref_upper)` — 30M下跌背驰

参照 `_sb_check_lower_tf_divergence` 但方向相反（寻找下跌背驰用于做多）：
- 30M级别最近两个低点：价格新低但下跌斜率平缓（< 2.0）
- 或：价格新低但成交量明显萎缩
- `ref_upper` 用于过滤：只考虑在参考价位附近的低点

### 3.6 `_csb_auxiliary_verification(df, prev_zhongshu_end_idx)` — 辅助验证

参照 `_sb_auxiliary_verification`，但基准点改为前中枢结束索引：

| 验证项 | 逻辑 |
|--------|------|
| 回调缩量 | 前中枢突破后：前半段成交量均值 > 后半段 |
| 均线支撑 | 当前最低价 > MA20 或 MA60（均线多头排列） |
| 力度减弱 | 回调下跌笔幅度 < 突破上涨笔幅度 × 0.8 |

### 3.7 `_csb_trading_decision(result, df)` — 交易决策

```python
def _csb_trading_decision(self, result, df):
```

**与二买的差异**：
- 入场价：当前收盘价
- **止损：前中枢上沿下方**（`previous_zhongshu.upper × 0.98`），而非一买低点
- 目标位：
  1. 新中枢上沿（`new_zhongshu.upper`）
  2. 等幅目标（前段上涨幅度 × 1.0）
  3. 1.618倍目标
- 仓位（加仓性质，轻于二买首仓）：
  - 首仓 25%、加仓 25%、最大总仓 50%

### 3.8 `generate_similar_second_buy_report(result)` — 报告生成

参照 `generate_second_buy_report`，报告结构：
1. 前提检查（一买确认 + 中枢数量）
2. 第一步：中枢定位（前中枢 + 突破 + 新中枢）
3. 第二步：核心几何条件（回调低点 vs 前中枢上沿）
4. 第三步：小级别验证（30M下跌背驰）
5. 辅助验证（缩量/均线/力度）
6. 综合判定
7. 交易执行（入场/止损/目标/仓位）

---

## 四、扩展 ChanFirstBuyStrategy 类

### 4.1 `run_similar_second_buy_analysis()`

```python
def run_similar_second_buy_analysis(self) -> SimilarSecondBuyAnalysisResult:
    if self.latest_result is None or not self.latest_result.divergence_confirmed:
        self.run_analysis()
    result = self.analyzer.analyze_similar_second_buy(
        self.df_4h, self.df_30m, self.latest_result)
    return result
```

### 4.2 `get_similar_second_buy_signal()`

```python
def get_similar_second_buy_signal(self) -> Optional[Dict[str, Any]]:
    result = self.run_similar_second_buy_analysis()
    if not result.similar_second_buy_confirmed:
        return {'action': 'HOLD', 'reason': '类二买条件不满足'}
    return {
        'action': 'BUY',
        'entry_price': result.suggested_entry,
        'stop_loss': result.stop_loss,
        'targets': result.targets,
        'position_advice': result.position_advice,
        'note': '类二买为加仓信号',
    }
```

---

## 五、模块级便捷函数

```python
async def run_similar_second_buy_analysis(symbol: str = 'ETHUSDC') -> SimilarSecondBuyAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return SimilarSecondBuyAnalysisResult(
            uptrend_established=False, rising_zhongshu_count=0,
            details=['数据获取失败'],
        )

    strategy.run_analysis()
    result = strategy.run_similar_second_buy_analysis()
    report = strategy.analyzer.generate_similar_second_buy_report(result)
    print(report)
    return result
```

---

## 六、__init__.py 导出

添加：
- `SimilarSecondBuyAnalysisResult`（import + `__all__`）
- `run_similar_second_buy_analysis`（import + `__all__`）

---

## 七、CLI 入口扩展

`run_first_buy_analysis.py`：
- `choices` 添加 `'similar-second-buy'`
- 帮助文字添加 `similar-second-buy=类二买`
- 添加处理分支：

```python
elif args.direction == 'similar-second-buy':
    strategy.run_analysis()
    result = strategy.run_similar_second_buy_analysis()
    report = strategy.analyzer.generate_similar_second_buy_report(result)
    print(report)
    signal = strategy.get_similar_second_buy_signal()
```

---

## 八、验证测试

1. 导入验证：`python -c "from trading_system.strategies.chan_first_buy_strategy import SimilarSecondBuyAnalysisResult; print('OK')"`
2. 模块导出验证：`python -c "from trading_system.strategies import SimilarSecondBuyAnalysisResult; print('OK')"`
3. CLI 验证：`python run_first_buy_analysis.py --help` 确认 `similar-second-buy` 出现

---

## 九、执行顺序

```
步骤1：新增 SimilarSecondBuyAnalysisResult dataclass
步骤2：新增 8 个 _csb_* + analyze_similar_second_buy + generate_similar_second_buy_report 方法
步骤3：修复可能的 \n 转义问题
步骤4：扩展 ChanFirstBuyStrategy + 模块级函数
步骤5：更新 __init__.py
步骤6：更新 run_first_buy_analysis.py
步骤7：验证测试
```

步骤2的8个方法统称为 `_csb_*` ，前缀 `csb` = `class-two Second Buy`。