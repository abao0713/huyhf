"""
Crypto_Chan_4H_Master_v1 回测可视化模块

基于 mplfinance 实现专业的缠论回测图表。
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import mplfinance as mpf
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class ChanBacktestVisualizer:
    """
    缠论回测可视化器

    支持绘制：
    - 主图：K线 + 中枢 + 交易信号 + 止损线 + 盈亏区域
    - 副图1：MACD + 背驰标注
    - 副图2：ATR + 资金费率
    """

    def __init__(self, df_4h: pd.DataFrame, zhongshu_list: List[Any],
                 trade_history: List[Dict[str, Any]], macd_data: Dict[str, pd.Series],
                 atr_data: pd.Series, funding_rate: List[Tuple[pd.Timestamp, float]] = None):
        """
        初始化可视化器

        Args:
            df_4h: 4H K线数据（必须包含 open_time, open, high, low, close, volume）
            zhongshu_list: 中枢列表（每个中枢需要有 start_idx, end_idx, upper, lower）
            trade_history: 交易记录列表
            macd_data: MACD 数据（字典，包含 'macd', 'signal', 'histogram'）
            atr_data: ATR 数据
            funding_rate: 资金费率列表（可选，格式：[(timestamp, rate), ...]）
        """
        # 预处理数据：设置时间索引
        self.df = df_4h.copy()
        if 'open_time' in self.df.columns:
            self.df.set_index('open_time', inplace=True)
        else:
            self.df.index = pd.to_datetime(self.df.index)

        self.zhongshu_list = zhongshu_list
        self.trade_history = trade_history
        self.macd_data = macd_data
        self.atr_data = atr_data
        self.funding_rate = funding_rate or []

        # 配置样式
        self.style = 'yahoo'  # 或 'nightclouds'
        self.figsize = (14, 10)

    def plot(self, save_path: Optional[Path] = None, show: bool = True):
        """
        绘制完整回测图表

        Args:
            save_path: 保存路径（如 None 则不保存）
            show: 是否显示图表
        """
        # 准备附加图表数据
        addplots = self._prepare_additional_plots()

        # 绘制基础图表
        fig, axes = mpf.plot(
            self.df,
            type='candle',
            style=self.style,
            figratio=(12, 8),
            figsize=self.figsize,
            title='Crypto_Chan_4H_Master_v1 回测分析',
            ylabel='价格 (USDC)',
            volume=True,
            addplot=addplots,
            returnfig=True
        )

        # 在主图上添加中枢、信号等
        self._add_overlays(fig, axes)

        # 保存或显示
        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches='tight', facecolor='white')
            logger.info(f"图表已保存: {save_path}")

        if show:
            plt.show()

        plt.close(fig)

    def _prepare_additional_plots(self) -> List[Any]:
        """准备附加图表数据（MACD, ATR, 资金费率）"""
        addplots = []

        # 副图1: MACD (panel 1)
        if self.macd_data.get('macd') is not None:
            macd_line = self.macd_data['macd']
            signal_line = self.macd_data['signal']
            histogram = self.macd_data['histogram']

            # 重命名以便图例显示
            macd_line.name = 'MACD'
            signal_line.name = 'Signal'

            addplots.append(mpf.make_addplot(macd_line, panel=1, color='blue'))
            addplots.append(mpf.make_addplot(signal_line, panel=1, color='red'))
            addplots.append(mpf.make_addplot(histogram, panel=1, type='bar', color='gray'))

        # 副图2: ATR (panel 2)
        if self.atr_data is not None and len(self.atr_data) > 0:
            atr = self.atr_data.copy()
            atr.name = 'ATR'
            addplots.append(mpf.make_addplot(atr, panel=2, color='purple'))

        # 副图3: 资金费率（如果有）(panel 3)
        if self.funding_rate:
            fr_df = pd.DataFrame(self.funding_rate, columns=['open_time', 'funding_rate'])
            fr_df.set_index('open_time', inplace=True)
            fr_df = fr_df.reindex(self.df.index, fill_value=0)
            fr_df.name = 'Funding Rate'
            addplots.append(mpf.make_addplot(fr_df, panel=3, color='orange'))

        return addplots

    def _add_overlays(self, fig, axes):
        """
        在主图上添加叠加层：中枢、信号箭头、止损线、盈亏区域

        Args:
            fig: matplotlib Figure 对象
            axes: mplfinance 返回的 axes 数组
        """
        # 找到主图（通常是第一个 subplot）
        main_ax = axes[0] if isinstance(axes, list) else axes

        # 1. 绘制中枢（金色矩形）
        self._draw_zhongshu_rectangles(main_ax)

        # 2. 绘制交易信号（箭头 + 文字）
        self._draw_trade_signals(main_ax)

        # 3. 绘制止损线（黑虚线）
        self._draw_stop_loss_lines(main_ax)

        # 4. 绘制盈亏区域（绿色盈利 / 红色亏损）
        self._draw_pnl_regions(main_ax)

        # 5. 在 MACD 图上标注背驰
        if len(axes) >= 2:
            self._annotate_divergence(axes[1])

        # 添加图例
        self._add_custom_legend(main_ax)

    def _draw_zhongshu_rectangles(self, ax):
        """绘制中枢（金色矩形）"""
        for zs in self.zhongshu_list:
            if not hasattr(zs, 'start_idx') or not hasattr(zs, 'end_idx'):
                continue

            # 获取中枢对应的时间范围
            if zs.start_idx < len(self.df) and zs.end_idx < len(self.df):
                start_time = self.df.index[zs.start_idx]
                end_time = self.df.index[min(zs.end_idx, len(self.df) - 1)]

                # 绘制金色矩形
                rect = patches.Rectangle(
                    (start_time, zs.lower),
                    (end_time - start_time),
                    (zs.upper - zs.lower),
                    linewidth=1,
                    edgecolor='gold',
                    facecolor='gold',
                    alpha=0.15,
                    label='中枢' if zs == self.zhongshu_list[0] else ""
                )
                ax.add_patch(rect)

                # 标注中枢方向
                direction_text = '↑' if hasattr(zs, 'direction') and zs.direction == 'up' else '↓'
                mid_y = (zs.upper + zs.lower) / 2
                mid_time = start_time + (end_time - start_time) / 2
                ax.text(mid_time, mid_y, direction_text,
                        color='darkgoldenrod', fontsize=8, ha='center', va='center')

    def _draw_trade_signals(self, ax):
        """绘制交易信号（箭头 + 开平仓文字）"""
        # 记录已绘制的开仓位置，用于后续匹配平仓
        open_positions = {}  # key: direction, value: list of trades
        
        for trade in self.trade_history:
            action = trade.get('action', '')
            price = trade.get('price', 0)
            reason = trade.get('reason', '')

            if not price:
                continue

            # 获取时间戳
            timestamp = trade.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = pd.Timestamp(timestamp)

            # 尝试精确匹配时间戳，若失败则找最近的时间点
            if timestamp not in self.df.index:
                # 尝试用 nearest 方式匹配
                try:
                    idx_pos = self.df.index.get_indexer([timestamp], method='nearest')[0]
                    if idx_pos >= 0:
                        timestamp = self.df.index[idx_pos]
                    else:
                        continue
                except Exception:
                    continue

            # 判断信号类型
            is_open_long = action in ('OPEN_LONG', 'OPEN_LONG_HEDGE')
            is_open_short = action in ('OPEN_SHORT', 'OPEN_SHORT_HEDGE')
            is_close_long = action in ('CLOSE_LONG', 'CLOSE_LONG_PARTIAL')
            is_close_short = action in ('CLOSE_SHORT', 'CLOSE_SHORT_PARTIAL')

            # ─── 绘制开仓信号箭头 ───
            if is_open_long:
                arrow_style = '↑'
                color = 'limegreen'
                offset = self.df.loc[timestamp, 'low'] * 0.025
                y_pos = self.df.loc[timestamp, 'low'] - offset
                label = f"开多\n${price:.2f}"
                
                ax.annotate(arrow_style, (timestamp, y_pos),
                            xytext=(0, 0), textcoords='offset points',
                            fontsize=16, color=color, ha='center', va='center',
                            arrowprops=dict(arrowstyle='->', color=color, lw=2))
                ax.text(timestamp, y_pos, label,
                        color=color, fontsize=7, ha='center', va='bottom')
                
                # 记录开仓信息供平仓匹配
                open_positions[('long', timestamp)] = trade
                
            elif is_open_short:
                arrow_style = '↓'
                color = 'red'
                offset = self.df.loc[timestamp, 'high'] * 0.025
                y_pos = self.df.loc[timestamp, 'high'] + offset
                label = f"开空\n${price:.2f}"
                
                ax.annotate(arrow_style, (timestamp, y_pos),
                            xytext=(0, 0), textcoords='offset points',
                            fontsize=16, color=color, ha='center', va='center',
                            arrowprops=dict(arrowstyle='->', color=color, lw=2))
                ax.text(timestamp, y_pos, label,
                        color=color, fontsize=7, ha='center', va='top')
                
                # 记录开仓信息供平仓匹配
                open_positions[('short', timestamp)] = trade

            # ─── 绘制平仓信号标记 ───
            elif is_close_long or is_close_short:
                pnl = trade.get('pnl', 0)
                close_color = 'green' if pnl > 0 else ('red' if pnl < 0 else 'gray')
                
                if is_close_long:
                    y_pos = self.df.loc[timestamp, 'high'] + self.df.loc[timestamp, 'high'] * 0.015
                    label = f"平多\nPnL:${pnl:.2f}"
                else:
                    y_pos = self.df.loc[timestamp, 'low'] - self.df.loc[timestamp, 'low'] * 0.015
                    label = f"平空\nPnL:${pnl:.2f}"
                
                # 平仓圆点
                ax.text(timestamp, y_pos, '●',
                        color=close_color, fontsize=12, ha='center', va='center')
                ax.text(timestamp, y_pos, label,
                        color=close_color, fontsize=6, ha='center',
                        va='bottom' if is_close_long else 'top')

    def _draw_stop_loss_lines(self, ax):
        """绘制止损线（黑色虚线）"""
        for trade in self.trade_history:
            action = trade.get('action', '')
            if 'CLOSE' in action or ('OPEN_LONG' not in action and 'OPEN_SHORT' not in action):
                continue

            stop_loss = trade.get('stop_loss', 0)
            if not stop_loss:
                continue

            timestamp = trade.get('timestamp')
            if isinstance(timestamp, str):
                timestamp = pd.Timestamp(timestamp)

            if timestamp not in self.df.index:
                continue

            # 绘制水平虚线
            close_time = trade.get('close_time', self.df.index[-1])
            if isinstance(close_time, str):
                close_time = pd.Timestamp(close_time)

            ax.hlines(y=stop_loss, xmin=timestamp, xmax=close_time,
                     colors='black', linestyles='--', linewidths=1, alpha=0.5, label='止损')

    def _draw_pnl_regions(self, ax):
        """绘制盈亏区域（绿色盈利 / 红色亏损）"""
        # 将交易按持仓周期分组
        positions = []

        for trade in self.trade_history:
            action = trade.get('action', '')
            price = trade.get('price', 0)
            timestamp = trade.get('timestamp')

            is_open_long = 'OPEN_LONG' in action
            is_open_short = 'OPEN_SHORT' in action
            is_close_long = 'CLOSE_LONG' in action
            is_close_short = 'CLOSE_SHORT' in action

            if is_open_long:
                positions.append({'direction': 'long', 'open_time': timestamp, 'open_price': price, 'trades': [trade]})
            elif is_open_short:
                positions.append({'direction': 'short', 'open_time': timestamp, 'open_price': price, 'trades': [trade]})
            elif (is_close_long or is_close_short) and positions:
                # 匹配最近的持仓
                for pos in reversed(positions):
                    if (is_close_long and pos['direction'] == 'long') or \
                       (is_close_short and pos['direction'] == 'short'):
                        pos['close_time'] = timestamp
                        pos['close_price'] = price
                        pos['pnl'] = trade.get('pnl', 0)
                        pos['trades'].append(trade)
                        break

        # 绘制盈亏区域
        for pos in positions:
            if 'close_time' not in pos or 'close_price' not in pos:
                continue

            open_time = pos['open_time']
            close_time = pos['close_time']
            pnl = pos.get('pnl', 0)

            if isinstance(open_time, str):
                open_time = pd.Timestamp(open_time)
            if isinstance(close_time, str):
                close_time = pd.Timestamp(close_time)

            # 获取持仓期间的价格范围
            mask = (self.df.index >= open_time) & (self.df.index <= close_time)
            period_df = self.df[mask]

            if len(period_df) == 0:
                continue

            # 确定填充颜色
            color = 'green' if pnl > 0 else 'red'
            alpha = 0.15

            # 绘制填充区域
            ax.fill_between(period_df.index,
                           period_df['low'],
                           period_df['high'],
                           color=color, alpha=alpha,
                           label='盈利' if pnl > 0 else '亏损')

    def _annotate_divergence(self, macd_ax):
        """在 MACD 图上标注背驰"""
        # 找出背驰点（从交易记录中提取）
        divergence_points = []

        for trade in self.trade_history:
            reason = trade.get('reason', '').lower()
            if '背驰' in reason:
                timestamp = trade.get('timestamp')
                if isinstance(timestamp, str):
                    timestamp = pd.Timestamp(timestamp)

                divergence_points.append((timestamp, '底背驰' if '底' in reason else '顶背驰'))

        # 在 MACD 图上标注
        for timestamp, label in divergence_points:
            if timestamp not in self.df.index:
                continue

            # 找到对应的位置
            y_position = macd_ax.get_ylim()[0] if '底背驰' in label else macd_ax.get_ylim()[1]
            y_position = y_position * 0.9 if '底背驰' in label else y_position * 0.1

            macd_ax.annotate(label, (timestamp, y_position),
                           fontsize=8, color='orange', ha='center', va='center',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.3))

    def _add_custom_legend(self, ax):
        """添加自定义图例"""
        # 收集所有图例元素
        legend_elements = [
            patches.Patch(facecolor='gold', edgecolor='gold', alpha=0.15, label='中枢'),
            patches.Patch(facecolor='green', alpha=0.15, label='盈利持仓'),
            patches.Patch(facecolor='red', alpha=0.15, label='亏损持仓'),
        ]

        ax.legend(handles=legend_elements, loc='upper left', fontsize=8)


def plot_backtest_from_report(
    report: 'BacktestReportV2',
    df_4h: pd.DataFrame,
    zhongshu_list: List[Any],
    macd_data: Dict[str, pd.Series],
    atr_data: pd.Series,
    funding_rate: List[Tuple[pd.Timestamp, float]] = None,
    save_path: Optional[Path] = None,
    show: bool = True
):
    """
    从回测报告生成图表（便捷函数）

    Args:
        report: BacktestReportV2 回测报告
        df_4h: 4H K线数据
        zhongshu_list: 中枢列表
        macd_data: MACD 数据
        atr_data: ATR 数据
        funding_rate: 资金费率列表（可选）
        save_path: 保存路径
        show: 是否显示图表
    """
    visualizer = ChanBacktestVisualizer(
        df_4h=df_4h,
        zhongshu_list=zhongshu_list,
        trade_history=report.trade_history,
        macd_data=macd_data,
        atr_data=atr_data,
        funding_rate=funding_rate
    )

    # 自动生成保存路径
    if save_path is None:
        save_path = Path('backtest_plots') / f"{report.symbol}_backtest_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path.parent.mkdir(parents=True, exist_ok=True)

    visualizer.plot(save_path=save_path, show=show)
    return save_path


if __name__ == "__main__":
    # 测试代码
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    print("ChanBacktestVisualizer 模块加载成功")
    print("使用方法:")
    print("  from trading_system.strategies.visualization import plot_backtest_from_report")
    print("  plot_backtest_from_report(report, df_4h, zhongshu_list, macd_data, atr_data)")