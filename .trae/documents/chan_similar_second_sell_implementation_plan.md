# 缠论类第二类卖点（类二卖）实现计划

## 一、概述

类二卖是类二买的完全镜像，发生在**第二个及之后的下跌中枢**构建过程中，是下跌趋势"主跌浪"中的做空加仓信号。

### 与类二买的核心映射

| 维度 | 类二买（做多） | 类二卖（做空） |
|------|---------------|---------------|
| 趋势方向 | 上涨趋势 | 下跌趋势 |
| 结构位置 | 第2+个**上涨**中枢构建中 | 第2+个**下跌**中枢构建中 |
| 核心条件 | 回调低点 > **前中枢上沿** | 反弹高点 < **前中枢下沿** |
| 强度(strong) | pullback_low >= upper × 1.02 | bounce_high <= lower × 0.98 |
| 止损 | 前中枢上沿 × 0.98 | 前中枢下沿 × 1.02 |
| 目标 | 新中枢上沿 → 等幅 → 1.618倍 | 新中枢下沿 → 等幅 → 1.618倍 |
| 仓位 | 加仓25%+25%（已有底仓） | 加仓25%+25%（已有空头仓位） |
| 风险回报 | ≥ 1:3 | ≥ 1:3 |

---

## 二、新增 DataClass

### `SimilarSecondSellAnalysisResult`

**文件**: `trading_system/strategies/chan_first_buy_strategy.py`

在 `SimilarSecondBuyAnalysisResult` 之后插入（约L189之后）：

```python
@dataclass
class SimilarSecondSellAnalysisResult:
    downtrend_established: bool
    falling_zhongshu_count: int
    previous_zhongshu: Optional[ZhongShu] = None
    previous_zhongshu_lower: float = 0.0
    has_breakdown_bounce: bool = False
    new_zhongshu: Optional[ZhongShu] = None
    bounce_high: float = 0.0
    bounce_high_idx: int = -1
    core_condition_met: bool = False
    strength_class: str = ''
    lower_tf_divergence: bool = False
    volume_shrinking: bool = False
    ma_resistance: bool = False
    momentum_weakening: bool = False
    similar_second_sell_confirmed: bool = False
    suggested_entry: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_advice: Dict[str, float] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None
```

**字段说明**（仅列出与类二买不同的）：

| 字段 | 类二买对应 | 含义 |
|------|-----------|------|
| `downtrend_established` | `uptrend_established` | 下跌趋势是否确立（一卖已确认） |
| `falling_zhongshu_count` | `rising_zhongshu_count` | 下跌中枢数量 |
| `previous_zhongshu_lower` | `previous_zhongshu_upper` | 前中枢下沿（类二卖参照物） |
| `has_breakdown_bounce` | `has_breakout_pullback` | 中枢跌破+反弹结构 |
| `bounce_high` | `pullback_low` | 反弹高点（而非回调低点） |
| `ma_resistance` | `ma_support` | 均线压力（而非均线支撑） |
| `similar_second_sell_confirmed` | `similar_second_buy_confirmed` | 类二卖确认标志 |

---

## 三、新增 Analyzer 方法

全部在 `ChanTheoryFirstBuyAnalyzer` 类中，共10个方法（前缀 `_css_` = class-two Second Sell）。

### 3.1 `analyze_similar_second_sell(df_4h, df_30m, first_sell_result)` — 主入口

**流程**：
```
前提检查：一卖必须已确认 (first_sell_result.divergence_confirmed)
→ 定位一卖点（复用 _ss_find_first_sell_point）
→ _css_find_falling_zhongshu — 找到一卖后所有下跌中枢（≥2个）
→ _css_check_breakdown_structure — 检查跌破+反弹结构
  - previous_zhongshu = zhongshu_list[-2]
→ 核心条件：反弹高点 < 前中枢下沿
→ _css_classify_strength — 强度分级
→ _css_check_lower_tf_divergence — 30M上涨背驰
→ _css_auxiliary_verification — 辅助验证（缩量/均线压力/力度减弱）
→ 综合判定：核心条件 + 小级别背驰 + 辅助信号≥2
→ _css_trading_decision — 交易决策
```

### 3.2 `_css_find_falling_zhongshu(df, first_sell_idx)` 

镜像 `_csb_find_rising_zhongshu`，差异：
- 起始索引为一卖索引
- `_identify_zhongshu(pens, direction='down')`

### 3.3 `_css_check_breakdown_structure(df, prev_zhongshu, zhongshu_list)`

镜像 `_csb_check_breakout_structure`，差异：
- 检查价格是否向下跌破前中枢下沿（`low < prev_zhongshu.lower`）
- 找向上的笔（反弹笔），取其最高点作为 `bounce_high`
- 新中枢 = `zhongshu_list[-1]`

### 3.4 `_css_classify_strength(bounce_high, prev_zhongshu, new_zhongshu)`

镜像 `_csb_classify_strength`，差异：
```python
lower = prev_zhongshu.lower
if bounce_high <= lower * 0.98:      # 远低于前中枢下沿
    return 'strong'
elif bounce_high < lower:             # 在前中枢下沿下方
    return 'standard'
else:
    return 'weak'
```

### 3.5 `_css_check_lower_tf_divergence(df_30m, ref_lower)` — 30M上涨背驰

镜像 `_csb_check_lower_tf_divergence`，差异：
- 找**高点**（`extremes.get('highs', [])`）而非低点
- 价格创新高但斜率平缓（`slope > 0 and slope < 2.0`）→ 上涨背驰
- 过滤：`last_price > ref_lower * 1.1`（反弹高点在参考价位附近）
- 可选：量价背离（价涨量缩）

### 3.6 `_css_auxiliary_verification(df, prev_zhongshu_end_idx)` — 辅助验证

镜像 `_csb_auxiliary_verification`，差异：
- `ma_resistance` 替代 `ma_support`：当前最高价 < MA20 或 MA60（价格在均线下方 = 均线压力）
- 力度对比：找第一笔下跌和第一笔反弹，反弹笔幅度 < 下跌笔幅度 × 0.8 为力度减弱
- 交易方向：`current_high < ma20 * 1.02 or current_high < ma60 * 1.02`

### 3.7 `_css_trading_decision(result, df)` — 交易决策

镜像 `_csb_trading_decision`，差异：
- 止损：`previous_zhongshu_lower * 1.02`（前中枢下沿上方）
- 目标位：
  1. 新中枢下沿（`new_zhongshu.lower`）
  2. 等幅目标（`latest_close - prev_range`）
  3. 1.618倍目标（`latest_close - prev_range * 1.618`）
- 如果有历史低点，加入目标列表
- 目标排序：`sorted(targets, reverse=True)`（做空看跌，从高到低）
- 仓位：首仓25%、加仓25%、最大50%（加仓信号）

### 3.8 `generate_similar_second_sell_report(result)` — 报告生成

镜像 `generate_similar_second_buy_report`，差异：
- 标题：`缠论类第二类卖点（类二卖）分析报告`
- 前提：一卖确认 + 下跌中枢数量
- 核心条件：反弹高点 vs 前中枢下沿
- 小级别验证：30M**上涨**背驰
- 辅助验证：均线**压力**（非支撑）
- 交易执行：止损（前中枢下沿上方）

---

## 四、扩展 ChanFirstBuyStrategy 类

### 4.1 `run_similar_second_sell_analysis()`

```python
def run_similar_second_sell_analysis(self) -> SimilarSecondSellAnalysisResult:
    if self.latest_sell_result is None or not self.latest_sell_result.divergence_confirmed:
        self.run_sell_analysis()
    result = self.analyzer.analyze_similar_second_sell(
        self.df_4h, self.df_30m, self.latest_sell_result)
    return result
```

关键：依赖 `latest_sell_result`（而非 `latest_result`）。

### 4.2 `get_similar_second_sell_signal()`

```python
def get_similar_second_sell_signal(self) -> Optional[Dict[str, Any]]:
    result = self.run_similar_second_sell_analysis()
    if not result.similar_second_sell_confirmed:
        return {'action': 'HOLD', 'reason': '类二卖条件不满足'}
    return {
        'action': 'SELL',
        'entry_price': result.suggested_entry,
        'stop_loss': result.stop_loss,
        'targets': result.targets,
        'position_advice': result.position_advice,
        'note': '类二卖为加仓信号',
    }
```

---

## 五、模块级便捷函数

```python
async def run_similar_second_sell_analysis(symbol: str = 'ETHUSDC') -> SimilarSecondSellAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return SimilarSecondSellAnalysisResult(
            downtrend_established=False, falling_zhongshu_count=0,
            details=['数据获取失败'],
        )

    strategy.run_sell_analysis()
    result = strategy.run_similar_second_sell_analysis()
    report = strategy.analyzer.generate_similar_second_sell_report(result)
    print(report)
    return result
```

---

## 六、__init__.py 导出

添加：
- `SimilarSecondSellAnalysisResult`（import + `__all__`）
- `run_similar_second_sell_analysis`（import + `__all__`）

---

## 七、CLI 入口扩展

`run_first_buy_analysis.py`：
- `choices` 添加 `'similar-second-sell'`
- 帮助文字添加 `similar-second-sell=类二卖`
- 添加处理分支：

```python
elif args.direction == 'similar-second-sell':
    strategy.run_sell_analysis()
    result = strategy.run_similar_second_sell_analysis()
    report = strategy.analyzer.generate_similar_second_sell_report(result)
    print(report)
    signal = strategy.get_similar_second_sell_signal()
```

---

## 八、验证测试

1. 导入验证：`from chan_first_buy_strategy import SimilarSecondSellAnalysisResult`
2. 模块导出验证：`from strategies import SimilarSecondSellAnalysisResult`
3. CLI验证：`python run_first_buy_analysis.py --help` 确认 `similar-second-sell` 出现

---

## 九、执行顺序

```
步骤1：新增 SimilarSecondSellAnalysisResult dataclass
步骤2：用Python脚本批量插入10个 _css_* 方法 + analyze_similar_second_sell + 报告生成
步骤3：修复可能的 \n 转义和 f-string 反斜杠问题
步骤4：扩展 ChanFirstBuyStrategy（2个方法）+ 模块级函数
步骤5：更新 __init__.py
步骤6：更新 run_first_buy_analysis.py CLI
步骤7：验证测试 + 清理临时文件
```

全部遵循已有的镜像模式，以 `_css_*` 为前缀（class-two Second Sell），对标 `_csb_*`。