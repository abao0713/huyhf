"""
缠论回测图表生成模块（简化版 - 仅主图）

基于 Matplotlib 生成专业级缠论回测分析图表：
- 单面板布局：仅价格面板（横轴时间，纵轴价格）
- 包含K线、分型、笔、线段、中枢、买卖点信号
- 输出 1920x1080 PNG，150 DPI

颜色映射（缠论标准配色）：
  COLOR_BI_UP = '#00FF00'       # 绿
  COLOR_BI_DOWN = '#FF0000'     # 红
  COLOR_DUAN = '#1E90FF'        # 道奇蓝
  COLOR_ZHONGSHU = 'yellow'     # 黄
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

# 将项目根目录加入 path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from trading_system.strategies.chan_strategy import Fractal, Pen, Segment

logger = logging.getLogger(__name__)

# ==============================================================================
# 缠论标准配色常量
# ==============================================================================
COLOR_BI_UP = '#00CC00'
COLOR_BI_DOWN = '#FF0000'
COLOR_DUAN = '#1E90FF'
COLOR_ZHONGSHU = '#FFD700'

# 买卖点信号颜色
COLOR_SIGNAL_1B = '#0066FF'
COLOR_SIGNAL_2B = '#FF8C00'
COLOR_SIGNAL_3B = '#9932CC'
COLOR_SIGNAL_1S = '#FF0000'
COLOR_SIGNAL_2S = '#FF00FF'
COLOR_SIGNAL_3S = '#808080'

SIGNAL_COLOR_MAP = {
    '1B': COLOR_SIGNAL_1B,
    '2B': COLOR_SIGNAL_2B,
    '3B': COLOR_SIGNAL_3B,
    '1S': COLOR_SIGNAL_1S,
    '2S': COLOR_SIGNAL_2S,
    '3S': COLOR_SIGNAL_3S,
}


class ChanBacktestChart:
    """
    缠论回测图表生成器（仅主图）

    单面板专业级回测分析图：
    - 横轴：具体时间
    - 纵轴：价格
    - 包含：K线、分型、笔、线段、中枢、买卖点信号

    使用示例:
        chart = ChanBacktestChart(
            df=df_4h,
            fractals=chan_result.fractals,
            pens=chan_result.pens,
            segments=chan_result.segments,
            zhongshu_list=chan_result.zhongshu_list,
            buy_sell_points=buy_sell_points,
        )
        chart.save("output.png")
    """

    def __init__(
        self,
        df: pd.DataFrame,
        fractals: Optional[List[Fractal]] = None,
        pens: Optional[List[Pen]] = None,
        segments: Optional[List] = None,
        zhongshu_list: Optional[List] = None,
        buy_sell_points: Optional[List[Dict]] = None,
        title: str = "缠论回测分析",
    ):
        """
        初始化图表生成器

        Args:
            df: OHLCV DataFrame，必须包含 open, high, low, close 列，以及 open_time 列
            fractals: 分型列表
            pens: 笔列表
            segments: 线段列表
            zhongshu_list: 中枢列表 (每个有 start_idx, end_idx, upper, lower)
            buy_sell_points: 买卖点信号列表
                [{"type": "1B"|"2B"|"3B"|"1S"|"2S"|"3S", "idx": int, "price": float}, ...]
            title: 图表标题
        """
        self.df = df.reset_index(drop=True)
        self.fractals = fractals if fractals is not None else []
        self.pens = pens if pens is not None else []
        self.segments = segments if segments is not None else []
        self.zhongshu_list = zhongshu_list if zhongshu_list is not None else []
        self.buy_sell_points = buy_sell_points if buy_sell_points is not None else []
        self.title = title

        self._setup_style()
        self.fig = None
        self.ax = None

        self._price_range = 0.0
        self._n_points = len(self.df)

        # 构建时间轴
        self._timestamps = self._build_timestamps()

    def _build_timestamps(self) -> pd.Series:
        """构建时间序列"""
        if 'open_time' in self.df.columns:
            return pd.to_datetime(self.df['open_time'])
        elif 'timestamp' in self.df.columns:
            return pd.to_datetime(self.df['timestamp'])
        else:
            return pd.Series(range(self._n_points))

    def _setup_style(self):
        """设置 matplotlib 样式和中文字体"""
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
        except Exception:
            try:
                plt.style.use('seaborn-whitegrid')
            except Exception:
                pass

        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    # ======================================================================
    # 主绘图入口
    # ======================================================================

    def plot(self) -> Tuple[plt.Figure, plt.Axes]:
        """
        生成完整图表

        Returns:
            (fig, ax)
        """
        if self.df.empty:
            raise ValueError("K线数据为空")

        self._price_range = self.df['high'].max() - self.df['low'].min()
        self._n_points = len(self.df)

        # 创建图形：单面板
        self.fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
        gs = self.fig.add_gridspec(
            1, 1, top=0.94, bottom=0.08, left=0.05, right=0.98
        )

        self.ax = self.fig.add_subplot(gs[0])

        # 绘制各元素
        self._plot_candlesticks()
        self._plot_fractals()
        self._plot_pens()
        self._plot_segments()
        self._plot_zhongshu()
        self._plot_buy_sell_signals()

        # 设置属性
        self._setup_axes()

        return self.fig, self.ax

    # ======================================================================
    # 绘制方法
    # ======================================================================

    def _plot_candlesticks(self):
        """绘制日本蜡烛图"""
        df = self.df
        x = df.index

        up = df[df['close'] >= df['open']]
        down = df[df['close'] < df['open']]

        body_width = max(0.4, min(0.8, 20.0 / max(len(df), 1)))

        # 阳线 (红)
        if len(up) > 0:
            self.ax.bar(
                up.index, up['close'] - up['open'],
                bottom=up['open'], width=body_width,
                color='red', alpha=0.85, zorder=2
            )
            self.ax.vlines(
                up.index, up['low'], up['high'],
                color='red', linewidth=0.8, zorder=2
            )

        # 阴线 (绿)
        if len(down) > 0:
            self.ax.bar(
                down.index, down['close'] - down['open'],
                bottom=down['open'], width=body_width,
                color='green', alpha=0.85, zorder=2
            )
            self.ax.vlines(
                down.index, down['low'], down['high'],
                color='green', linewidth=0.8, zorder=2
            )

    def _plot_fractals(self):
        """绘制分型标记（小三角形，无标签）"""
        if not self.fractals:
            return

        for fractal in self.fractals:
            try:
                idx = fractal.idx
                if idx < 0 or idx >= self._n_points:
                    continue
            except Exception:
                continue

            if fractal.type == 'top':
                self.ax.scatter(
                    idx, fractal.high,
                    marker='v', color='red', s=30, zorder=6, alpha=0.9
                )
            else:
                self.ax.scatter(
                    idx, fractal.low,
                    marker='^', color='green', s=30, zorder=6, alpha=0.9
                )

    def _plot_pens(self):
        """绘制笔（连接分型的实线）"""
        if not self.pens:
            return

        first_up = True
        first_down = True

        for pen in self.pens:
            try:
                start_x = pen.start_fractal.idx
                end_x = pen.end_fractal.idx
            except Exception:
                continue

            if start_x < 0 or end_x >= self._n_points:
                continue

            if pen.direction == 'up':
                start_y = pen.start_fractal.low
                end_y = pen.end_fractal.high
                color = COLOR_BI_UP
                label = 'Bi (上升)' if first_up else ""
                first_up = False
            else:
                start_y = pen.start_fractal.high
                end_y = pen.end_fractal.low
                color = COLOR_BI_DOWN
                label = 'Bi (下降)' if first_down else ""
                first_down = False

            self.ax.plot(
                [start_x, end_x], [start_y, end_y],
                color=color, linewidth=2.0, linestyle='-',
                zorder=4, label=label, alpha=0.85
            )

    def _plot_segments(self):
        """绘制线段（粗蓝线叠加在笔上）"""
        if not self.segments:
            return

        first_seg = True

        for segment in self.segments:
            try:
                start_x = segment.start_pen.start_fractal.idx
                end_x = segment.end_pen.end_fractal.idx
            except Exception:
                continue

            if start_x < 0 or end_x >= self._n_points:
                continue

            if segment.direction == 'up':
                start_y = segment.start_pen.start_fractal.low
                end_y = segment.end_pen.end_fractal.high
            else:
                start_y = segment.start_pen.start_fractal.high
                end_y = segment.end_pen.end_fractal.low

            label = 'Duan (线段)' if first_seg else ""
            first_seg = False

            self.ax.plot(
                [start_x, end_x], [start_y, end_y],
                color=COLOR_DUAN, linewidth=3.5, linestyle='-',
                zorder=3, label=label, alpha=0.8
            )

    def _plot_zhongshu(self):
        """绘制中枢（半透明黄色矩形 + ZG/ZD 虚线）"""
        if not self.zhongshu_list:
            return

        first_zs = True
        n = self._n_points

        for zs in self.zhongshu_list:
            try:
                start_idx = zs.start_idx
                end_idx = zs.end_idx
                upper = zs.upper
                lower = zs.lower
            except Exception:
                continue

            if start_idx >= n or end_idx >= n:
                continue
            if start_idx < 0 or end_idx < 0:
                continue

            # 半透明黄色矩形
            xmin = start_idx / n
            xmax = min(end_idx / n, 1.0)

            label = 'Zhong Shu (中枢)' if first_zs else ""
            first_zs = False

            self.ax.axhspan(
                lower, upper,
                xmin=xmin, xmax=xmax,
                facecolor=COLOR_ZHONGSHU, alpha=0.18, zorder=1,
                label=label
            )

            # ZG (上沿) 虚线
            self.ax.hlines(
                y=upper, xmin=start_idx, xmax=end_idx,
                colors='gold', linestyles='dashed', linewidths=0.8,
                alpha=0.6, zorder=1
            )

            # ZD (下沿) 虚线
            self.ax.hlines(
                y=lower, xmin=start_idx, xmax=end_idx,
                colors='gold', linestyles='dashed', linewidths=0.8,
                alpha=0.6, zorder=1
            )

    def _plot_buy_sell_signals(self):
        """绘制买卖点信号箭头（大箭头 + 标签）"""
        if not self.buy_sell_points or self._n_points == 0:
            return

        y_offset = self._price_range * 0.03
        used_labels = set()

        for sp in self.buy_sell_points:
            signal_type = sp.get('type', '')
            idx = sp.get('idx', -1)
            price = sp.get('price', 0)

            if idx < 0 or idx >= self._n_points:
                continue

            color = SIGNAL_COLOR_MAP.get(signal_type, 'gray')
            is_buy = signal_type in ('1B', '2B', '3B')

            if is_buy:
                arrow_y = self.df.iloc[idx]['low'] - y_offset
                arrow_dir = '↑'
                va = 'top'
            else:
                arrow_y = self.df.iloc[idx]['high'] + y_offset
                arrow_dir = '↓'
                va = 'bottom'

            show_label = signal_type if signal_type not in used_labels else ""
            if show_label:
                used_labels.add(signal_type)

            # 绘制大箭头
            self.ax.annotate(
                arrow_dir,
                xy=(idx, arrow_y),
                fontsize=20, color=color, ha='center', va='center',
                fontweight='bold', zorder=7,
                arrowprops=dict(
                    arrowstyle='->', color=color, lw=2.0,
                    connectionstyle='arc3,rad=0'
                )
            )

            # 标注信号类型（带背景框）
            label_y = arrow_y - y_offset * 0.5 if is_buy else arrow_y + y_offset * 0.5
            self.ax.text(
                idx, label_y,
                signal_type,
                fontsize=11, color=color, ha='center', va=va,
                fontweight='bold', zorder=7,
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor='white', edgecolor=color, alpha=0.9,
                    linewidth=1.5
                )
            )

    # ======================================================================
    # 图表属性设置
    # ======================================================================

    def _setup_axes(self):
        """设置坐标轴属性、标题、图例"""
        # 标题
        self.ax.set_title(self.title, fontsize=18, fontweight='bold', pad=15)
        self.ax.set_ylabel('Price', fontsize=12)
        self.ax.set_xlabel('Time', fontsize=12)
        self.ax.grid(True, linestyle='--', alpha=0.3)

        # 设置 X 轴为时间格式
        if isinstance(self._timestamps.iloc[0], pd.Timestamp):
            # 使用实际时间戳作为 X 轴
            self.ax.set_xticks(range(0, self._n_points, max(1, self._n_points // 20)))
            self.ax.set_xticklabels(
                [self._timestamps.iloc[i].strftime('%Y-%m-%d %H:%M') 
                 for i in range(0, self._n_points, max(1, self._n_points // 20))],
                rotation=45, ha='right', fontsize=9
            )
        else:
            self.ax.set_xlabel('K线索引', fontsize=12)

        # 图例
        handles, labels = self.ax.get_legend_handles_labels()
        if handles:
            self.ax.legend(
                handles, labels,
                loc='upper left', fontsize=9, ncol=2,
                framealpha=0.9
            )

        # 调整 Y 轴范围防止信号被裁剪
        y_min, y_max = self.ax.get_ylim()
        padding = self._price_range * 0.08
        self.ax.set_ylim(y_min - padding, y_max + padding)

    # ======================================================================
    # 保存
    # ======================================================================

    def save(self, filepath: str, dpi: int = 150) -> str:
        """
        保存图表为 PNG 文件

        Args:
            filepath: 保存路径
            dpi: 分辨率，默认 150

        Returns:
            保存的文件路径
        """
        if self.fig is None:
            self.plot()

        save_path = Path(filepath)
        save_path.parent.mkdir(parents=True, exist_ok=True)

        self.fig.savefig(
            str(save_path), dpi=dpi, bbox_inches='tight',
            facecolor='white', edgecolor='none'
        )
        plt.close(self.fig)
        logger.info(f"图表已保存: {save_path}")
        return str(save_path)


# ==============================================================================
# 便捷函数
# ==============================================================================

def generate_backtest_chart(
    df: pd.DataFrame,
    fractals: List[Fractal],
    pens: List[Pen],
    segments: List,
    zhongshu_list: List,
    buy_sell_points: List[Dict],
    save_path: Optional[str] = None,
    title: str = "缠论回测分析",
) -> str:
    """
    快速生成回测图表的便捷函数

    Args:
        df: OHLCV DataFrame
        fractals: 分型列表
        pens: 笔列表
        segments: 线段列表
        zhongshu_list: 中枢列表
        buy_sell_points: 买卖点信号列表
        save_path: 保存路径
        title: 图表标题

    Returns:
        保存的文件路径
    """
    chart = ChanBacktestChart(
        df=df,
        fractals=fractals,
        pens=pens,
        segments=segments,
        zhongshu_list=zhongshu_list,
        buy_sell_points=buy_sell_points,
        title=title,
    )
    chart.plot()
    return chart.save(save_path, dpi=150)


if __name__ == "__main__":
    # 测试代码
    print("ChanBacktestChart 模块加载成功")
    print("使用方法:")
    print("  from trading_system.strategies.chan_backtest_chart import ChanBacktestChart, generate_backtest_chart")
    print("  chart = ChanBacktestChart(df=..., fractals=..., pens=..., ...)")
    print("  chart.save('output.png')")
