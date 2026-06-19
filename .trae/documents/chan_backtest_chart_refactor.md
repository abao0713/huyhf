# 缠论回测图表重构方案

## 概要

删除旧的图表生成逻辑（`ChanPlotter` 和 `ChanBacktestVisualizer`），新建一个专业级两面板回测图表模块，严格按照用户提供的缠论可视化规范生成 PNG。

---

## 当前状态分析

### 现有图表生成代码（需删除）

| 文件 | 类/函数 | 说明 |
|------|---------|------|
| `trading_system/utils/chan_plotter.py` | `ChanPlotter` | 单面板简单缠论图表（K线+分型+笔+线段+信号），使用 matplotlib，无人引用 |
| `trading_system/strategies/visualization.py` | `ChanBacktestVisualizer` + `plot_backtest_from_report()` | 多面板回测图表（mplfinance），带中枢矩形、交易信号、止损线、盈亏区域、MACD、ATR、资金费率 |

### 引用关系

- `run_crypto_chan_backtest.py` 第 34 行导入 `plot_backtest_from_report` 和 `ChanBacktestVisualizer`
- `run_crypto_chan_backtest.py` 第 353-364 行调用 `plot_backtest_from_report()` 生成图表
- `chan_plotter.py` 无外部引用（仅日志文件中有提及）

### 现有数据结构

- `Fractal`: idx, type(top/bottom), high, low, timestamp
- `Pen`: start_fractal, end_fractal, direction(up/down), high, low, start_time, end_time, macd_area
- `Segment`: start_pen, end_pen, direction, pens
- `ZhongShu`: start_idx, end_idx, upper, lower, direction, zhongshu_range
- `ChanAnalysisResult`: fractals, pens, segments, zhongshu_list, beichi_bottom/top, last_bottom_low, last_top_high
- `BacktestReportV2`: trade_history (list of dict with timestamp, action, price, pnl, reason, etc.)

---

## 拟议变更

### 1. 删除旧文件

**删除 `trading_system/utils/chan_plotter.py`** — 完整删除 `ChanPlotter` 类及其测试代码

**删除 `trading_system/strategies/visualization.py`** — 完整删除 `ChanBacktestVisualizer` 类和 `plot_backtest_from_report()` 函数

### 2. 新建 `trading_system/strategies/chan_backtest_chart.py`

新模块 `ChanBacktestChart` 类，严格按用户 Prompt 实现：

#### 布局结构
- **两面板**: Price Panel (70% 高度) + MACD Panel (30% 高度)
- 使用 `matplotlib`（非 mplfinance），风格 `seaborn-v0_8-whitegrid`
- 输出 1920×1080 PNG，150 DPI

#### Panel 1 — 价格面板（元素及绘制顺序）

| 序号 | 元素 | 实现方式 | 颜色/样式 |
|------|------|----------|-----------|
| 1 | 日本蜡烛图 | `ax.bar` + `ax.vlines`，阳线红/阴线绿 | 红 `#FF0000` / 绿 `#00FF00` |
| 2 | 分型标记 | 顶分型红色向下三角 `v`，底分型绿色向上三角 `^`，无标签 | 顶红/底绿，小尺寸 |
| 3 | 笔 (Bi) | `ax.plot` 连接分型，上升笔绿/下降笔红，实线加粗 | 绿 `#00FF00` / 红 `#FF0000` |
| 4 | 线段 (Duan) | `ax.plot` 叠加在笔上，粗蓝线 | 道奇蓝 `#1E90FF` |
| 5 | 中枢 (Zhong Shu) | `ax.axhspan` 半透明黄色矩形 + ZG/ZD 虚线 | 黄色 `yellow` alpha=0.2 |
| 6 | 买卖点信号 | `plt.annotate` 箭头，1B 蓝↑、2B 橙↑、3B 紫↑、1S 红↓、2S 品红↓、3S 灰↓ | 蓝/橙/紫/红/品红/灰 |
| 7 | 背驰连线 | 跨两面板的虚线连接，底背驰绿虚线，顶背驰红虚线 | 亮绿 `#32CD32` / 猩红 `#DC143C` |

#### Panel 2 — MACD 面板

| 序号 | 元素 | 实现方式 |
|------|------|----------|
| 1 | MACD 柱状图 | `ax.bar` 正红负绿 |
| 2 | DIF 线 | `ax.plot` 蓝色 |
| 3 | DEA 线 | `ax.plot` 红色 |
| 4 | 背驰连线 | 与 Panel 1 对应的背驰虚线连接 |

#### 类接口设计

```python
class ChanBacktestChart:
    def __init__(
        self,
        df: pd.DataFrame,           # OHLCV 数据
        fractals: List[Fractal],    # 分型列表
        pens: List[Pen],            # 笔列表
        segments: List[Segment],    # 线段列表
        zhongshu_list: List[ZhongShu],  # 中枢列表
        buy_sell_points: List[Dict],    # 买卖点信号 [{"type": "1B", "idx": int, "price": float}, ...]
        macd_data: Dict[str, pd.Series],  # {"macd": ..., "signal": ..., "histogram": ...}
        divergence_lines: List[Dict],     # 背驰连线 [{"type": "bull"/"bear", "price_idx1": int, "price_idx2": int, "macd_idx1": int, "macd_idx2": int}, ...]
        title: str = "缠论回测分析",
    ):
        ...

    def plot(self) -> Tuple[plt.Figure, Tuple[plt.Axes, plt.Axes]]:
        """生成图表，返回 (fig, (ax_price, ax_macd))"""
        ...

    def save(self, filepath: str, dpi: int = 150) -> str:
        """保存为 PNG，返回文件路径"""
        ...
```

#### 颜色映射常量

```python
COLOR_BI_UP = '#00FF00'       # 绿
COLOR_BI_DOWN = '#FF0000'     # 红
COLOR_DUAN = '#1E90FF'        # 道奇蓝
COLOR_ZHONGSHU = 'yellow'     # 黄
COLOR_DIVERGENCE_BULL = '#32CD32'  # 亮绿
COLOR_DIVERGENCE_BEAR = '#DC143C'  # 猩红
COLOR_SIGNAL_1B = 'blue'      # 一买
COLOR_SIGNAL_2B = 'orange'    # 二买
COLOR_SIGNAL_3B = 'purple'    # 三买
COLOR_SIGNAL_1S = 'red'       # 一卖
COLOR_SIGNAL_2S = 'magenta'   # 二卖
COLOR_SIGNAL_3S = 'gray'      # 三卖
```

#### 关键实现细节

1. **箭头偏移**: 买卖点箭头使用 `y_offset = (df['high'].max() - df['low'].min()) * 0.03` 防止被K线遮挡
2. **中枢绘制**: 使用 `ax.axhspan(ymin, ymax, xmin=start/total, xmax=end/total, ...)` 其中横轴为 0~N-1 的整数索引
3. **背驰检测**: 在 `ChanBacktestChart` 中根据输入数据判断背驰，在 Price 和 MACD 面板同时绘制虚线连接
4. **图例**: 包含 Bi、Duan、Zhong Shu、1B/2B/3B、Divergence
5. **中文字体**: 设置 `SimHei` 后备 `DejaVu Sans`

### 3. 更新 `run_crypto_chan_backtest.py`

- 删除第 34 行 `from trading_system.strategies.visualization import plot_backtest_from_report, ChanBacktestVisualizer`
- 新增 `from trading_system.strategies.chan_backtest_chart import ChanBacktestChart`
- 修改第 343-364 行图表生成逻辑，改为调用 `ChanBacktestChart` 并传入完整的缠论分析数据

---

## 假设与决策

1. **数据可用性**: 回测引擎 `CryptoChan4HBacktestEngine` 已有 `strategy._chan_4h` 提供分型、笔、线段、中枢数据，`strategy._macd_4h` 提供 MACD 数据
2. **买卖点信号**: 当前 trade_history 使用 `OPEN_LONG/OPEN_SHORT` 等动作类型，新图表需要 `buy_sell_points` 参数，由调用方从 trade_history 中提取或标注信号类型（1B/2B/3B/1S/2S/3S）。若 trade_history 中的 `action` 字段不足以区分买卖点类型，先用 `reason` 字段或 `action` 类型做映射，后续可扩展
3. **背驰连线**: 背驰数据从 `_chan_4h.beichi_bottom/beichi_top` 和笔的 MACD 面积关系中提取，在图表中自动计算和绘制背驰连线
4. **删除范围**: 同时删除 `chan_plotter.py` 和 `visualization.py`，因为 `ChanPlotter` 无人引用，`ChanBacktestVisualizer` 仅被 `run_crypto_chan_backtest.py` 引用

---

## 验证步骤

1. 运行 `python run_crypto_chan_backtest.py --fast --no-show` 验证回测正常运行且图表生成不报错
2. 检查生成的 PNG 文件（`trading_system/backtest/` 目录下），确认：
   - 两面板布局比例正确（70/30）
   - K线、分型、笔、线段、中枢、信号、MACD 均有正确显示
   - 颜色方案符合规范
   - 图例完整
   - 分辨率 1920×1080
3. 确认 `chan_plotter.py` 和 `visualization.py` 已删除后无 import 错误