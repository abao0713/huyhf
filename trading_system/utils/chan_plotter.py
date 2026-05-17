import sys
import os
import logging

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Optional, Any
from trading_system.strategies.chan_strategy import Fractal, Pen, Segment

# 配置日志
logger = logging.getLogger(__name__)


class ChanPlotter:
    """
    缠论绘图工具类

    用于可视化缠论分析结果，包括K线、分型、笔、线段和交易信号。

    属性说明：
    - kline_data: K线数据（DataFrame格式）
    - fractals: 分型数据列表
    - pens: 笔数据列表
    - segments: 线段数据列表
    - signals: 背驰信号列表
    - fig: matplotlib图形对象
    - ax: matplotlib坐标轴对象
    """

    def __init__(
        self,
        kline_data: pd.DataFrame,
        fractals: Optional[List[Fractal]] = None,
        pens: Optional[List[Pen]] = None,
        segments: Optional[List[Segment]] = None,
        signals: Optional[List[dict]] = None,
        strategy=None
    ):
        """
        初始化ChanPlotter

        参数：
        :param kline_data: K线数据DataFrame，必须包含open_time, open, high, low, close列
        :param fractals: 分型数据列表
        :param pens: 笔数据列表
        :param segments: 线段数据列表
        :param signals: 背驰信号列表，每个信号包含action, direction, stop_loss, reason
        :param strategy: 可选的策略对象（用于获取均线数据）
        """
        self.kline_data = kline_data
        self.fractals = fractals if fractals is not None else []
        self.pens = pens if pens is not None else []
        self.segments = segments if segments is not None else []
        self.signals = signals if signals is not None else []
        self.strategy = strategy
        
        self._setup_chinese_font()
        
        self.fig = None
        self.ax = None

    def _setup_chinese_font(self):
        """
        设置matplotlib中文支持
        """
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False

    def plot(self):
        """
        生成完整图表

        绘制顺序：
        1. 绘制K线（蜡烛图）
        2. 标记分型
        3. 绘制笔
        4. 绘制线段
        5. 标记交易信号

        返回：
        :return: (fig, ax) 图形和坐标轴对象
        """
        if self.kline_data.empty:
            raise ValueError("K线数据为空")

        self.fig, self.ax = plt.subplots(figsize=(16, 8))
        
        # 绘制K线
        self._plot_candlestick()
        
        # 绘制分型
        self._plot_fractals()
        
        # 绘制笔
        self._plot_pens()
        
        # 绘制线段
        self._plot_segments()

        # 绘制均线（如果策略支持）
        self._plot_moving_averages()

        # 绘制信号
        self._plot_signals()
        
        # 设置图表属性
        self._setup_plot_properties()
        
        return self.fig, self.ax

    def _plot_candlestick(self):
        """
        绘制K线蜡烛图
        """
        df = self.kline_data.reset_index(drop=True)
        x = df.index
        
        # 上涨K线（阳线）
        up = df[df['close'] >= df['open']]
        self.ax.bar(
            up.index,
            up['close'] - up['open'],
            bottom=up['open'],
            width=0.6,
            color='red',
            alpha=0.8
        )
        self.ax.vlines(
            up.index,
            up['low'],
            up['high'],
            color='red',
            linewidth=1
        )
        
        # 下跌K线（阴线）
        down = df[df['close'] < df['open']]
        self.ax.bar(
            down.index,
            down['close'] - down['open'],
            bottom=down['open'],
            width=0.6,
            color='green',
            alpha=0.8
        )
        self.ax.vlines(
            down.index,
            down['low'],
            down['high'],
            color='green',
            linewidth=1
        )

    def _plot_fractals(self):
        """
        绘制分型标记
        """
        if not self.fractals:
            return
        
        for fractal in self.fractals:
            x = fractal.idx
            if fractal.type == 'top':
                # 顶分型标记为向下的三角形
                self.ax.scatter(
                    x,
                    fractal.high,
                    marker='v',
                    color='orange',
                    s=100,
                    zorder=5,
                    label='顶分型' if x == self.fractals[0].idx else ""
                )
                # 添加分型类型标注
                self.ax.text(
                    x,
                    fractal.high * 1.002,
                    '顶',
                    fontsize=10,
                    color='orange',
                    ha='center'
                )
            else:
                # 底分型标记为向上的三角形
                self.ax.scatter(
                    x,
                    fractal.low,
                    marker='^',
                    color='blue',
                    s=100,
                    zorder=5,
                    label='底分型' if x == self.fractals[0].idx else ""
                )
                # 添加分型类型标注
                self.ax.text(
                    x,
                    fractal.low * 0.998,
                    '底',
                    fontsize=10,
                    color='blue',
                    ha='center'
                )

    def _plot_pens(self):
        """
        绘制笔
        """
        if not self.pens:
            return
        
        for i, pen in enumerate(self.pens):
            start_x = pen.start_fractal.idx
            end_x = pen.end_fractal.idx
            
            if pen.direction == 'up':
                # 上升笔：从底分型到顶分型
                start_y = pen.start_fractal.low
                end_y = pen.end_fractal.high
                color = 'red'
                label = '上升笔' if i == 0 else ""
            else:
                # 下降笔：从顶分型到底分型
                start_y = pen.start_fractal.high
                end_y = pen.end_fractal.low
                color = 'green'
                label = '下降笔' if i == 0 else ""
            
            self.ax.plot(
                [start_x, end_x],
                [start_y, end_y],
                color=color,
                linewidth=2,
                linestyle='-',
                zorder=4,
                label=label
            )
            
            # 添加笔的方向标注
            mid_x = (start_x + end_x) / 2
            mid_y = (start_y + end_y) / 2
            self.ax.text(
                mid_x,
                mid_y,
                pen.direction,
                fontsize=9,
                color=color,
                ha='center',
                va='center'
            )

    def _plot_segments(self):
        """
        绘制线段（确保所有线段连续连接）
        
        核心逻辑：
        - 按时间顺序遍历所有线段
        - 每个线段的终点自动成为下一个线段的起点
        - 上升线和下降线交替连接，形成完整的价格走势
        """
        if not self.segments:
            return
        
        # 收集所有线段的点（按顺序）
        all_segment_points = []  # [(x, y, direction), ...]
        
        for i, segment in enumerate(self.segments):
            # 获取当前线段的起止点
            start_x = segment.start_pen.start_fractal.idx
            end_x = segment.end_pen.end_fractal.idx
            
            if segment.direction == 'up':
                # 上升线段：从低点到高点
                start_y = segment.start_pen.start_fractal.low
                end_y = segment.end_pen.end_fractal.high
            else:
                # 下降线段：从高点到低点
                start_y = segment.start_pen.start_fractal.high
                end_y = segment.end_pen.end_fractal.low
            
            # 第一个线段：添加起点和终点
            if i == 0:
                all_segment_points.append((start_x, start_y, segment.direction))
                all_segment_points.append((end_x, end_y, segment.direction))
            else:
                # 后续线段：只添加终点（起点应该与前一个线段的终点重合或接近）
                all_segment_points.append((end_x, end_y, segment.direction))
        
        # 绘制连续的线段路径
        if len(all_segment_points) >= 2:
            xs = [p[0] for p in all_segment_points]
            ys = [p[1] for p in all_segment_points]
            
            # 使用不同颜色区分上升/下降
            # 方法：分段绘制，根据方向改变颜色
            for j in range(len(all_segment_points) - 1):
                x1, y1, dir1 = all_segment_points[j]
                x2, y2, dir2 = all_segment_points[j + 1]
                
                # 根据方向选择颜色
                if dir2 == 'up':
                    color = 'darkred'
                    label = '上升线段' if j == 0 else ""
                else:
                    color = 'darkgreen'
                    label = '下降线段' if j == 0 else ""
                
                self.ax.plot(
                    [x1, x2],
                    [y1, y2],
                    color=color,
                    linewidth=3,
                    linestyle='--',
                    zorder=3,
                    label=label
                )

    def _plot_moving_averages(self):
        """
        绘制均线（MA20, MA60, MA120）

        从strategy对象获取均线数据并绘制
        使用不同颜色和透明度区分

        防御性检查：如果strategy对象不存在或没有均线数据，则跳过绘制
        """
        if not self.strategy or not hasattr(self.strategy, 'ma_short'):
            logger.debug("[ChanPlotter] 未提供策略对象或策略对象无均线数据，跳过均线绘制")
            return

        if self.strategy.ma_short.empty:
            return

        # MA20 - 蓝色实线（短期支撑/压力）
        if len(self.strategy.ma_short) > 0:
            self.ax.plot(
                range(len(self.strategy.ma_short)),
                self.strategy.ma_short.values,
                color='blue',
                linewidth=1.5,
                alpha=0.7,
                label='MA20',
                zorder=2
            )

        # MA60 - 橙色实线（中期趋势）
        if hasattr(self.strategy, 'ma_medium') and len(self.strategy.ma_medium) > 0:
            self.ax.plot(
                range(len(self.strategy.ma_medium)),
                self.strategy.ma_medium.values,
                color='orange',
                linewidth=1.5,
                alpha=0.7,
                label='MA60',
                zorder=2
            )

        # MA120 - 紫色实线（长期方向）
        if hasattr(self.strategy, 'ma_long') and len(self.strategy.ma_long) > 0:
            self.ax.plot(
                range(len(self.strategy.ma_long)),
                self.strategy.ma_long.values,
                color='purple',
                linewidth=1.5,
                alpha=0.6,
                label='MA120',
                zorder=2
            )

        logger.info("[ChanPlotter] 已绘制均线: MA20(蓝), MA60(橙), MA120(紫)")

    def _get_signal_style(self, signal_type):
        """
        根据信号类型返回绘图样式

        Returns:
            (marker, color, edgecolor, label, facecolor, marker_size)
        """
        styles = {
            "OPEN_LONG": (
                "^", "deepskyblue", "blue", "做多", "lightcyan", 220
            ),
            "OPEN_SHORT": (
                "v", "darkorange", "darkred", "做空", "navajowhite", 220
            ),
            "PARTIAL_CLOSE": (
                "D", "mediumpurple", "purple", "平60%", "lavender", 180
            ),
            "CLOSE_REMAINING": (
                "s", "sienna", "brown", "平剩余", "bisque", 180
            ),
            "STOP_LOSS": (
                "X", "red", "darkred", "止损", "mistyrose", 200
            ),
        }
        return styles.get(signal_type, ("o", "gray", "black", "信号", "white", 150))

    def _plot_signals(self):
        """
        绘制交易信号（做多/做空/平仓60%/剩余平仓/止损）

        每种信号有独立的图形标识，并显示具体价格。
        """
        if not self.signals:
            logger.warning("没有交易信号需要绘制")
            return

        df = self.kline_data.reset_index(drop=True)

        timestamp_to_idx = {}
        for idx, row in df.iterrows():
            if 'open_time' in row:
                timestamp = pd.to_datetime(row['open_time'])
                timestamp_to_idx[timestamp] = idx

        logger.info(f"开始绘制 {len(self.signals)} 个交易信号")

        used_labels = set()

        for i, signal in enumerate(self.signals):
            action = signal.get('action', '')
            reason = signal.get('reason', '')
            signal_type = signal.get('signal_type', '')
            trade_price = signal.get('price', 0)

            if action not in ['BUY', 'SELL']:
                continue

            signal_idx = None

            if 'timestamp' in signal and signal['timestamp']:
                try:
                    signal_time = pd.to_datetime(signal['timestamp'])
                    for ts in sorted(timestamp_to_idx.keys()):
                        if ts >= signal_time:
                            signal_idx = timestamp_to_idx[ts]
                            break
                except Exception as e:
                    logger.warning(f"信号 {i} 时间解析失败: {e}")

            if signal_idx is None:
                valid_signals = [s for s in self.signals if s.get('action') in ['BUY', 'SELL']]
                total_signals = len(valid_signals)
                current_signal_num = len([s for j, s in enumerate(self.signals[:i+1]) if s.get('action') in ['BUY', 'SELL']])
                position_ratio = current_signal_num / max(total_signals, 1)
                signal_idx = int(position_ratio * (len(df) - 1))
                signal_idx = max(0, min(signal_idx, len(df) - 1))

            if signal_idx is None or signal_idx >= len(df):
                logger.warning(f"信号 {i} 索引无效: {signal_idx}")
                continue

            marker, color, edgecolor, type_label, facecolor, marker_size = self._get_signal_style(signal_type)

            if action == 'BUY':
                low_price = df.iloc[signal_idx]['low']
                y_pos = low_price * 0.995
            else:
                high_price = df.iloc[signal_idx]['high']
                y_pos = high_price * 1.005

            show_label = type_label if type_label not in used_labels else ""
            if show_label:
                used_labels.add(type_label)

            self.ax.scatter(
                [signal_idx],
                [y_pos],
                marker=marker,
                color=color,
                s=marker_size,
                zorder=6,
                label=show_label,
                edgecolors=edgecolor,
                linewidths=2
            )

            short_reason = reason[:8] if reason else ""
            price_str = f"${trade_price:.2f}" if trade_price else ""

            self.ax.annotate(
                f"{type_label}\n{price_str}",
                xy=(signal_idx, y_pos),
                xytext=(signal_idx + 5, y_pos + (5 if action == 'SELL' else -5)),
                fontsize=9,
                color=color,
                fontweight='bold',
                ha='left',
                va='bottom' if action == 'SELL' else 'top',
                bbox=dict(
                    boxstyle='round,pad=0.3',
                    facecolor=facecolor,
                    edgecolor=edgecolor,
                    alpha=0.9
                ),
                arrowprops=dict(
                    arrowstyle='->',
                    color=color,
                    connectionstyle='arc3,rad=0'
                )
            )

            logger.info(f"绘制{type_label} {i}: 位置={signal_idx}, 价格={y_pos:.2f}, 原因={reason}")

        logger.info(f"交易信号绘制完成")

    def _setup_plot_properties(self):
        """
        设置图表属性
        """
        # 设置标题
        self.ax.set_title('缠论分析图表', fontsize=16, pad=20)
        
        # 设置坐标轴标签
        self.ax.set_xlabel('K线索引', fontsize=12)
        self.ax.set_ylabel('价格', fontsize=12)
        
        # 设置网格
        self.ax.grid(True, linestyle='--', alpha=0.3)
        
        # 设置图例
        self.ax.legend(loc='upper left', fontsize=10)
        
        # 调整布局
        plt.tight_layout()

    def save(self, filename: str):
        """
        保存图表为PNG文件

        参数：
        :param filename: 保存路径和文件名
        """
        if self.fig is None:
            self.plot()
        
        self.fig.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close(self.fig)


if __name__ == "__main__":
    # 测试代码
    import numpy as np
    
    # 生成测试K线数据
    dates = pd.date_range('2024-01-01', periods=50, freq='D')
    np.random.seed(42)
    opens = 40000 + np.cumsum(np.random.randn(50) * 500)
    closes = opens + np.random.randn(50) * 300
    highs = np.maximum(opens, closes) + np.random.rand(50) * 200
    lows = np.minimum(opens, closes) - np.random.rand(50) * 200
    
    test_data = pd.DataFrame({
        'open_time': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes
    })
    
    # 生成测试分型数据
    test_fractals = [
        Fractal(idx=5, type='bottom', high=highs[5], low=lows[5], timestamp=dates[5]),
        Fractal(idx=12, type='top', high=highs[12], low=lows[12], timestamp=dates[12]),
        Fractal(idx=18, type='bottom', high=highs[18], low=lows[18], timestamp=dates[18]),
        Fractal(idx=25, type='top', high=highs[25], low=lows[25], timestamp=dates[25]),
        Fractal(idx=32, type='bottom', high=highs[32], low=lows[32], timestamp=dates[32]),
        Fractal(idx=40, type='top', high=highs[40], low=lows[40], timestamp=dates[40]),
    ]
    
    # 生成测试笔数据
    test_pens = [
        Pen(
            start_fractal=test_fractals[0],
            end_fractal=test_fractals[1],
            direction='up',
            high=highs[12],
            low=lows[5],
            start_time=dates[5],
            end_time=dates[12]
        ),
        Pen(
            start_fractal=test_fractals[1],
            end_fractal=test_fractals[2],
            direction='down',
            high=highs[12],
            low=lows[18],
            start_time=dates[12],
            end_time=dates[18]
        ),
        Pen(
            start_fractal=test_fractals[2],
            end_fractal=test_fractals[3],
            direction='up',
            high=highs[25],
            low=lows[18],
            start_time=dates[18],
            end_time=dates[25]
        ),
        Pen(
            start_fractal=test_fractals[3],
            end_fractal=test_fractals[4],
            direction='down',
            high=highs[25],
            low=lows[32],
            start_time=dates[25],
            end_time=dates[32]
        ),
        Pen(
            start_fractal=test_fractals[4],
            end_fractal=test_fractals[5],
            direction='up',
            high=highs[40],
            low=lows[32],
            start_time=dates[32],
            end_time=dates[40]
        ),
    ]
    
    # 生成测试线段数据
    test_segments = [
        Segment(
            start_pen=test_pens[0],
            end_pen=test_pens[2],
            direction='up',
            pens=test_pens[0:3]
        ),
        Segment(
            start_pen=test_pens[2],
            end_pen=test_pens[4],
            direction='down',
            pens=test_pens[2:5]
        ),
    ]
    
    # 生成测试信号
    test_signals = [
        {
            'action': 'BUY',
            'direction': 'up',
            'stop_loss': lows[32],
            'reason': '30m底背驰'
        }
    ]
    
    # 创建绘图器并绘制
    plotter = ChanPlotter(
        kline_data=test_data,
        fractals=test_fractals,
        pens=test_pens,
        segments=test_segments,
        signals=test_signals
    )
    
    fig, ax = plotter.plot()
    
    # 保存测试图表
    output_path = 'test_chan_plot.png'
    plotter.save(output_path)
    print(f"测试图表已保存到: {output_path}")