import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
import numpy as np

from .base_strategy import BaseStrategy
from .chan_strategy import Fractal, Pen
from ..data.market_data import get_30m_klines
from ..binance.client import BinanceRestClient
from ..utils.indicators import (
    calculate_ma,
    calculate_price_slope,
    calculate_deviation_rate,
    calculate_ma_slope,
    calculate_volume_ratio,
    detect_volume_price_pattern,
    detect_volume_price_pattern_uptrend,
    count_klines_between_points,
    find_price_extremes,
    binance_klines_to_dataframe,
)

logger = logging.getLogger(__name__)


@dataclass
class ZhongShu:
    start_idx: int
    end_idx: int
    upper: float
    lower: float
    direction: str
    zhongshu_range: float = 0.0


@dataclass
class DownSegment:
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    slope: float
    kline_count: int
    bounce_strength_avg: float = 0.0


@dataclass
class UpSegment:
    start_idx: int
    end_idx: int
    start_price: float
    end_price: float
    slope: float
    kline_count: int
    pullback_strength_avg: float = 0.0


@dataclass
class DimensionResult:
    name: str
    satisfied: bool
    details: List[str] = field(default_factory=list)


@dataclass
class FirstBuyAnalysisResult:
    has_downtrend: bool
    zhongshu_count: int
    in_final_exit_segment: bool
    trend_details: str
    dimensions: List[DimensionResult] = field(default_factory=list)
    satisfied_count: int = 0
    divergence_confirmed: bool = False
    entry_conditions_met: bool = False
    suggested_entry_price: float = 0.0
    stop_loss_price: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_advice: Dict[str, float] = field(default_factory=dict)
    second_buy_zone: Optional[Tuple[float, float]] = None
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None
    zhongshu_list: List[ZhongShu] = field(default_factory=list)
    down_segments: List[DownSegment] = field(default_factory=list)


@dataclass
class FirstSellAnalysisResult:
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


@dataclass
class SecondBuyAnalysisResult:
    first_buy_confirmed: bool
    first_buy_low: float
    first_buy_idx: int
    has_rise_pullback: bool
    first_rising_zhongshu: Optional[ZhongShu] = None
    pullback_low: float = 0.0
    pullback_low_idx: int = -1
    core_condition_met: bool = False
    strength_class: str = ''
    lower_tf_divergence: bool = False
    volume_shrinking: bool = False
    ma_support: bool = False
    momentum_weakening: bool = False
    second_buy_confirmed: bool = False
    suggested_entry: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_advice: Dict[str, float] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None


@dataclass
class SecondSellAnalysisResult:
    first_sell_confirmed: bool
    first_sell_high: float
    first_sell_idx: int
    has_fall_bounce: bool
    first_falling_zhongshu: Optional[ZhongShu] = None
    bounce_high: float = 0.0
    bounce_high_idx: int = -1
    core_condition_met: bool = False
    strength_class: str = ''
    lower_tf_divergence: bool = False
    volume_shrinking: bool = False
    ma_resistance: bool = False
    momentum_weakening: bool = False
    second_sell_confirmed: bool = False
    suggested_entry: float = 0.0
    stop_loss: float = 0.0
    targets: List[float] = field(default_factory=list)
    position_advice: Dict[str, float] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)
    df_4h: Optional[pd.DataFrame] = None
    df_30m: Optional[pd.DataFrame] = None
    timestamp: Optional[str] = None


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


class ChanTheoryFirstBuyAnalyzer:

    def __init__(
        self,
        deviation_ratio_threshold: float = 0.8,
        volume_shrink_threshold: float = 0.7,
        slope_flatten_threshold: float = 0.3,
        min_zhongshu_for_buy: int = 2,
        min_dimensions_for_divergence: int = 2,
    ):
        self.deviation_ratio_threshold = deviation_ratio_threshold
        self.volume_shrink_threshold = volume_shrink_threshold
        self.slope_flatten_threshold = slope_flatten_threshold
        self.min_zhongshu_for_buy = min_zhongshu_for_buy
        self.min_dimensions_for_divergence = min_dimensions_for_divergence

    def analyze(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame) -> FirstBuyAnalysisResult:
        result = FirstBuyAnalysisResult(
            has_downtrend=False,
            zhongshu_count=0,
            in_final_exit_segment=False,
            trend_details='',
            df_4h=df_4h,
            df_30m=df_30m,
            timestamp=datetime.now().isoformat(),
        )

        if df_4h.empty:
            result.trend_details = '4H数据为空，无法进行分析'
            return result

        has_downtrend, zhongshu_count, in_final, details, zhongshu_list, pens = self._step1_check_trend_background(df_4h)
        result.has_downtrend = has_downtrend
        result.zhongshu_count = zhongshu_count
        result.in_final_exit_segment = in_final
        result.trend_details = details
        result.zhongshu_list = zhongshu_list

        if not has_downtrend or zhongshu_count < self.min_zhongshu_for_buy:
            result.trend_details += '\n不满足一买前提条件，终止分析。'
            return result

        down_segments = self._identify_down_segments(df_4h)
        result.down_segments = down_segments

        low_points = self._find_low_points(df_4h)

        dim1 = self._step2_dimension1_price_structure(df_4h, down_segments)
        dim2 = self._step2_dimension2_ma_system(df_4h, low_points)
        dim3 = self._step2_dimension3_volume_verification(df_4h, low_points)
        dim4 = self._step2_dimension4_mtf_confirmation(df_4h, df_30m)

        result.dimensions = [dim1, dim2, dim3, dim4]

        satisfied_count, divergence_confirmed = self._step3_comprehensive_judgment(result.dimensions)
        result.satisfied_count = satisfied_count
        result.divergence_confirmed = divergence_confirmed

        decision = self._step4_trading_decision(result, df_4h)
        result.entry_conditions_met = decision.get('entry_conditions_met', False)
        result.suggested_entry_price = decision.get('suggested_entry_price', 0.0)
        result.stop_loss_price = decision.get('stop_loss_price', 0.0)
        result.targets = decision.get('targets', [])
        result.position_advice = decision.get('position_advice', {})
        result.second_buy_zone = decision.get('second_buy_zone', None)

        return result

    def _step1_check_trend_background(self, df: pd.DataFrame) -> Tuple[bool, int, bool, str, List[ZhongShu], List[Pen]]:
        fractals = self._find_fractals(df, hg1=5)
        pens = self._build_pens(fractals)
        zhongshu_list = self._identify_zhongshu(pens, direction='down')

        has_downtrend = False
        details_parts = []

        if len(pens) < 4:
            details_parts.append('笔数量不足（<4），无法形成下跌趋势结构')
        else:
            down_pens = [p for p in pens if p.direction == 'down']
            up_pens = [p for p in pens if p.direction == 'up']

            if len(down_pens) >= 2:
                first_down = down_pens[0]
                last_down = down_pens[-1]

                if last_down.end_fractal.low < first_down.start_fractal.high:
                    has_downtrend = True
                    price_range = first_down.start_fractal.high - last_down.end_fractal.low
                    if price_range > 0:
                        pct = (price_range / first_down.start_fractal.high) * 100
                        details_parts.append(f'存在明确下跌趋势，跌幅约{pct:.1f}%')
                    else:
                        details_parts.append('存在明确下跌趋势结构')

                    if up_pens:
                        bounce_prices = [round(p.end_fractal.high, 2) for p in up_pens if p.direction == 'up']
                        details_parts.append(f'下跌途中出现{len(up_pens)}次反弹')
                else:
                    details_parts.append('未形成明确下跌趋势，价格未持续走低')
            else:
                details_parts.append('下跌笔不足2笔，趋势不明朗')

        zhongshu_count = len(zhongshu_list)

        if zhongshu_count > 0:
            details_parts.append(f'检测到{zhongshu_count}个下跌中枢')
            for i, zs in enumerate(zhongshu_list):
                details_parts.append(f'  中枢{i + 1}: [{zs.lower:.4f}, {zs.upper:.4f}]')
        else:
            details_parts.append('未检测到下跌中枢')
            if len(pens) >= 4:
                details_parts.append('（可能笔的重叠程度不足以形成中枢）')

        in_final_exit = False
        if zhongshu_count >= self.min_zhongshu_for_buy and has_downtrend:
            last_zs = zhongshu_list[-1]
            current_price = df['close'].iloc[-1]
            if current_price < last_zs.lower:
                in_final_exit = True
                details_parts.append(f'当前价格{current_price:.4f}低于最后中枢下沿{last_zs.lower:.4f}，处于向下离开段')
            else:
                in_final_exit = True
                details_parts.append(f'当前价格在最后中枢({last_zs.lower:.4f}-{last_zs.upper:.4f})附近，处于离开段末端')
        elif zhongshu_count >= self.min_zhongshu_for_buy:
            last_zs = zhongshu_list[-1]
            current_price = df['close'].iloc[-1]
            if current_price < last_zs.lower:
                in_final_exit = True
                details_parts.append(f'当前价格低于最后中枢下沿，处于向下离开段')

        return has_downtrend, zhongshu_count, in_final_exit, '\n'.join(details_parts), zhongshu_list, pens

    def _step2_dimension1_price_structure(self, df: pd.DataFrame, down_segments: List[DownSegment]) -> DimensionResult:
        dim = DimensionResult(name='走势结构力度对比', satisfied=False)

        if len(down_segments) < 2:
            dim.details.append('下跌段不足2个，无法进行结构力度对比')
            return dim

        last_seg = down_segments[-1]
        prev_seg = down_segments[-2]

        sub1 = False
        sub2 = False
        sub3 = False

        if abs(prev_seg.slope) > 0.001:
            if abs(last_seg.slope) < abs(prev_seg.slope):
                sub1 = True
                dim.details.append(f'✓ 斜率对比：最后一段斜率({last_seg.slope:.4f}) < 前一段({prev_seg.slope:.4f})，下跌角度减小')
            else:
                dim.details.append(f'✗ 斜率对比：最后一段斜率({last_seg.slope:.4f}) >= 前一段({prev_seg.slope:.4f})，下跌角度未减小')
        else:
            dim.details.append('✗ 斜率对比：前一段斜率接近0，无法有效对比')

        if last_seg.kline_count > prev_seg.kline_count:
            sub2 = True
            dim.details.append(f'✓ 复杂度对比：最后一段K线数({last_seg.kline_count}) > 前一段({prev_seg.kline_count})，结构更复杂')
        else:
            time_ratio = last_seg.kline_count / max(prev_seg.kline_count, 1)
            if time_ratio > 0.8:
                sub2 = True
                dim.details.append(f'✓ 复杂度对比：最后一段耗时与前期接近(比例{time_ratio:.2f})，耗时充分')
            else:
                dim.details.append(f'✗ 复杂度对比：最后一段K线数({last_seg.kline_count}) <= 前一段({prev_seg.kline_count})，复杂度不足')

        if last_seg.bounce_strength_avg > prev_seg.bounce_strength_avg:
            sub3 = True
            dim.details.append(f'✓ 波动收敛：最后一段反弹力度({last_seg.bounce_strength_avg:.6f}) > 前一段({prev_seg.bounce_strength_avg:.6f})，反弹增强')
        else:
            low_diff = abs(last_seg.end_price - prev_seg.end_price)
            if low_diff < abs(prev_seg.start_price - prev_seg.end_price) * 0.5:
                sub3 = True
                dim.details.append(f'✓ 波动收敛：低点间距收敛，下跌笔幅度减小')
            else:
                dim.details.append(f'✗ 波动收敛：反弹力度未增强，低点间距未明显收敛')

        if sub1 or sub2 or sub3:
            dim.satisfied = True

        return dim

    def _step2_dimension2_ma_system(self, df: pd.DataFrame, low_points: List[Dict]) -> DimensionResult:
        dim = DimensionResult(name='均线系统观察', satisfied=False)

        if len(low_points) < 2:
            dim.details.append('阶段性低点不足2个，无法进行乖离率对比')
            return dim

        close = df['close']
        sub1 = False
        sub2 = False

        ma60 = calculate_ma(close, 60)
        ma120 = calculate_ma(close, 120)

        if ma60.notna().any() and ma120.notna().any():
            latest_low = low_points[-1]
            prev_low = low_points[-2]

            latest_idx = latest_low['idx']
            prev_idx = prev_low['idx']

            if latest_idx < len(df) and prev_idx < len(df):
                latest_ma60_val = ma60.iloc[latest_idx]
                prev_ma60_val = ma60.iloc[prev_idx]

                if not pd.isna(latest_ma60_val) and not pd.isna(prev_ma60_val) and prev_ma60_val != 0:
                    latest_dev60 = abs((df['low'].iloc[latest_idx] - latest_ma60_val) / latest_ma60_val)
                    prev_dev60 = abs((df['low'].iloc[prev_idx] - prev_ma60_val) / prev_ma60_val)

                    if prev_dev60 > 0:
                        ratio = latest_dev60 / prev_dev60
                        if ratio < self.deviation_ratio_threshold:
                            sub1 = True
                            dim.details.append(f'✓ 乖离率变化：最新乖离率/前次乖离率={ratio:.3f} < {self.deviation_ratio_threshold}，显著缩小')
                        else:
                            dim.details.append(f'✗ 乖离率变化：最新乖离率/前次乖离率={ratio:.3f} >= {self.deviation_ratio_threshold}，未显著缩小')
                    else:
                        dim.details.append('✗ 乖离率变化：前次乖离率为0，无法计算比例')
                else:
                    dim.details.append('✗ 乖离率变化：均线数据不足，无法计算')
            else:
                dim.details.append('✗ 乖离率变化：低点索引越界')
        else:
            dim.details.append('✗ 乖离率变化：60/120均线数据不足')

        if len(close) >= 130:
            ma60_slope = calculate_ma_slope(close, 60, lookback=10)
            ma120_slope = calculate_ma_slope(close, 120, lookback=10)

            abs60 = abs(ma60_slope)
            abs120 = abs(ma120_slope)

            if abs60 > 0.001 or abs120 > 0.001:
                if abs60 < 0.001 or (ma60_slope < 0 and abs60 < self.slope_flatten_threshold * abs60):
                    sub2 = True
                if abs120 < 0.001 or (ma120_slope < 0 and abs120 < self.slope_flatten_threshold):
                    sub2 = True

            if sub2:
                dim.details.append(f'✓ 均线形态：MA60斜率={ma60_slope:.6f}，MA120斜率={ma120_slope:.6f}，均线走平或放缓')
            else:
                dim.details.append(f'✗ 均线形态：MA60斜率={ma60_slope:.6f}，MA120斜率={ma120_slope:.6f}，未明显走平')

            if abs60 <= 0.001 or abs120 <= 0.001:
                dim.details.append(f'  至少有一条均线斜率接近零(走平)')
                if not sub2:
                    sub2 = True
        else:
            dim.details.append('✗ 均线形态：数据不足以计算MA60/MA120斜率')

        if sub1 or sub2:
            dim.satisfied = True

        return dim

    def _step2_dimension3_volume_verification(self, df: pd.DataFrame, low_points: List[Dict]) -> DimensionResult:
        dim = DimensionResult(name='成交量辅助验证', satisfied=False)

        if 'volume' not in df.columns:
            dim.details.append('数据中缺少成交量字段')
            return dim

        sub1 = False
        sub2 = False

        if len(low_points) >= 2:
            latest_low = low_points[-1]
            prev_low = low_points[-2]

            latest_vol = df['volume'].iloc[latest_low['idx']]
            prev_vol = df['volume'].iloc[prev_low['idx']]

            if prev_vol > 0:
                ratio = calculate_volume_ratio(latest_vol, prev_vol)
                if ratio < self.volume_shrink_threshold:
                    sub1 = True
                    dim.details.append(f'✓ 价跌量缩：最新低点量/前次低点量={ratio:.3f} < {self.volume_shrink_threshold}，显著萎缩')
                else:
                    dim.details.append(f'✗ 价跌量缩：最新低点量/前次低点量={ratio:.3f} >= {self.volume_shrink_threshold}，未显著萎缩')
            else:
                dim.details.append('✗ 价跌量缩：前次低点成交量为0，无法计算')
        else:
            dim.details.append('✗ 价跌量缩：阶段性低点不足2个')

        pattern = detect_volume_price_pattern(df, recent_bars=min(40, len(df)))
        sub2 = pattern.get('pattern_shifted', False)
        dim.details.append(f'量价关系：{pattern.get("detail", "检测失败")}')

        if sub1 or sub2:
            dim.satisfied = True

        return dim

    def _step2_dimension4_mtf_confirmation(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame) -> DimensionResult:
        dim = DimensionResult(name='多级别联立确认', satisfied=False)

        if df_30m.empty or len(df_30m) < 50:
            dim.details.append('30分钟K线数据不足')
            return dim

        fractals_30m = self._find_fractals(df_30m, hg1=5)
        pens_30m = self._build_pens(fractals_30m)
        zhongshu_30m = self._identify_zhongshu(pens_30m, direction='down')

        down_pens_30m = [p for p in pens_30m if p.direction == 'down']
        has_trend_30m = len(down_pens_30m) >= 2
        has_zhongshu_30m = len(zhongshu_30m) >= 1

        if has_trend_30m and has_zhongshu_30m:
            dim.satisfied = True
            dim.details.append(f'✓ 30分钟出现下跌趋势+{len(zhongshu_30m)}个下跌中枢，存在背驰结构')
        elif has_trend_30m:
            dim.satisfied = True
            dim.details.append(f'✓ 30分钟出现下跌趋势（{len(down_pens_30m)}个下跌笔），存在背驰特征')
        elif has_zhongshu_30m:
            dim.satisfied = True
            dim.details.append(f'✓ 30分钟出现{len(zhongshu_30m)}个下跌中枢，趋势结构明确')
        else:
            dim.satisfied = False
            dim.details.append(f'✗ 30分钟未出现清晰的下跌趋势结构')

        if not dim.satisfied:
            low_points_30m = self._find_low_points(df_30m)
            if len(low_points_30m) >= 2:
                latest_vol = df_30m['volume'].iloc[low_points_30m[-1]['idx']] if 'volume' in df_30m.columns else 0
                prev_vol = df_30m['volume'].iloc[low_points_30m[-2]['idx']] if 'volume' in df_30m.columns else 0
                if prev_vol > 0 and latest_vol / prev_vol < self.volume_shrink_threshold:
                    dim.satisfied = True
                    dim.details.append(f'✓ 30分钟量价背离：最新低点量显著萎缩')

        return dim

    def _step3_comprehensive_judgment(self, dimensions: List[DimensionResult]) -> Tuple[int, bool]:
        satisfied_count = sum(1 for d in dimensions if d.satisfied)
        divergence_confirmed = satisfied_count >= self.min_dimensions_for_divergence
        return satisfied_count, divergence_confirmed

    def _step4_trading_decision(self, result: FirstBuyAnalysisResult, df: pd.DataFrame) -> Dict[str, Any]:
        decision = {
            'entry_conditions_met': False,
            'suggested_entry_price': 0.0,
            'stop_loss_price': 0.0,
            'targets': [],
            'position_advice': {
                'first_entry': 0.25,
                'add_position': 0.35,
                'max_total': 0.55,
            },
            'second_buy_zone': None,
        }

        if not result.divergence_confirmed:
            return decision

        latest_low = df['low'].min()
        latest_close = df['close'].iloc[-1]

        has_bottom_fractal = self._check_bottom_fractal_confirm(df, lookback=8)

        if has_bottom_fractal:
            decision['entry_conditions_met'] = True

        decision['suggested_entry_price'] = round(latest_close, 4)
        decision['stop_loss_price'] = round(latest_low * 0.98, 4)

        if result.zhongshu_list:
            last_zs = result.zhongshu_list[-1]
            targets = [
                round(last_zs.lower, 4),
                round(last_zs.upper, 4),
            ]
            if len(result.zhongshu_list) >= 2:
                prev_zs = result.zhongshu_list[-2]
                targets.append(round(prev_zs.lower, 4))
                targets.append(round(prev_zs.upper, 4))
            if result.down_segments:
                targets.append(round(result.down_segments[0].start_price, 4))
            targets.sort()
            decision['targets'] = targets

        last_low_price = latest_low
        for seg in result.down_segments:
            if seg.end_price < last_low_price or last_low_price == 0:
                last_low_price = seg.end_price

        if result.has_downtrend and last_low_price > 0:
            decision['second_buy_zone'] = (round(last_low_price, 4), round(last_low_price * 1.02, 4))

        return decision

    def _step5_followup_checkpoints(self, result: FirstBuyAnalysisResult) -> List[str]:
        points = [
            '【二买确认】等待一买后上涨一笔的回调，不破一买低点即确认二买',
            '【中枢演化】观察上涨过程中中枢的构建与离开力度，新中枢不跌破旧中枢上沿为强势',
            '【级别扩展】关注4小时上涨是否引发日线级别转折，日线出现底分型则级别扩展确认',
        ]
        return points

    def _identify_zhongshu(self, pens: List[Pen], direction: str = 'down') -> List[ZhongShu]:
        zhongshu_list = []

        if len(pens) < 3:
            return zhongshu_list

        for i in range(len(pens) - 2):
            p1 = pens[i]
            p2 = pens[i + 1]
            p3 = pens[i + 2]

            high_values = [p.high for p in [p1, p2, p3]]
            low_values = [p.low for p in [p1, p2, p3]]

            overlap_high = min(high_values)
            overlap_low = max(low_values)

            if overlap_low < overlap_high:
                zs = ZhongShu(
                    start_idx=p1.start_fractal.idx,
                    end_idx=p3.end_fractal.idx,
                    upper=overlap_high,
                    lower=overlap_low,
                    direction=direction,
                    zhongshu_range=overlap_high - overlap_low,
                )
                zhongshu_list.append(zs)
                i += 2

        merged = []
        for zs in zhongshu_list:
            overlap = False
            for m in merged:
                if zs.lower < m.upper and zs.upper > m.lower:
                    m.upper = max(m.upper, zs.upper)
                    m.lower = min(m.lower, zs.lower)
                    m.end_idx = max(m.end_idx, zs.end_idx)
                    overlap = True
                    break
            if not overlap:
                merged.append(zs)

        return merged

    def _identify_down_segments(self, df: pd.DataFrame) -> List[DownSegment]:
        segments = []

        if df.empty or len(df) < 10:
            return segments

        extremes = find_price_extremes(df, window=5)
        lows = extremes.get('lows', [])

        for i in range(len(lows) - 1):
            start_idx = lows[i]
            end_idx = lows[i + 1]

            if start_idx >= end_idx:
                continue

            seg_data = df.iloc[start_idx:end_idx + 1]
            start_price = df['low'].iloc[start_idx]
            end_price = df['low'].iloc[end_idx]

            slope = calculate_price_slope(seg_data['close'])
            kline_count = count_klines_between_points(df, start_idx, end_idx)

            bounce_sum = 0.0
            bounce_count = 0
            prev_low = start_price
            for j in range(start_idx + 1, end_idx):
                current_low = df['low'].iloc[j]
                if current_low > prev_low:
                    bounce = (current_low - prev_low) / max(prev_low, 0.0001)
                    bounce_sum += bounce
                    bounce_count += 1
                prev_low = current_low

            bounce_avg = bounce_sum / max(bounce_count, 1)

            segments.append(DownSegment(
                start_idx=start_idx,
                end_idx=end_idx,
                start_price=start_price,
                end_price=end_price,
                slope=slope,
                kline_count=kline_count,
                bounce_strength_avg=bounce_avg,
            ))

        return segments

    def _find_low_points(self, df: pd.DataFrame) -> List[Dict]:
        """找到所有阶段性低点（价格+成交量+时间）"""
        low_points = []

        if df.empty:
            return low_points

        extremes = find_price_extremes(df, window=5)
        low_indices = extremes.get('lows', [])

        for idx in low_indices:
            point = {
                'idx': idx,
                'price': df['low'].iloc[idx],
                'volume': df['volume'].iloc[idx] if 'volume' in df.columns else 0,
                'time': str(df.index[idx]) if isinstance(df.index, pd.DatetimeIndex) else str(idx),
            }
            low_points.append(point)

        low_points.sort(key=lambda x: x['price'])
        return low_points

    def _check_bottom_fractal_confirm(self, df: pd.DataFrame, lookback: int = 8) -> bool:
        """确认底分型停顿/验证信号"""
        if len(df) < lookback + 3:
            return False

        recent = df.iloc[-(lookback + 3):]

        for i in range(1, len(recent) - 1):
            current = recent.iloc[i]
            left = recent.iloc[i - 1:i]
            right = recent.iloc[i + 1:i + 2]

            if len(left) == 0 or len(right) == 0:
                continue

            if current['low'] < left['low'].min() and current['low'] < right['low'].min():
                if len(right) > 0:
                    recent_close = df['close'].iloc[-1]
                    recent_low = df['low'].iloc[-3:].min()
                    if recent_low > current['low']:
                        return True

        return False

    def _find_fractals(self, df: pd.DataFrame, hg1: int = 5) -> List[Fractal]:
        """分型识别（简化版，复用于非策略类的独立分析）"""
        fractals = []
        n = len(df)

        for i in range(hg1, n - hg1):
            left_high = df.iloc[i - hg1:i]['high'].max()
            left_low = df.iloc[i - hg1:i]['low'].min()
            right_high = df.iloc[i + 1:i + hg1 + 1]['high'].max()
            right_low = df.iloc[i + 1:i + hg1 + 1]['low'].min()

            current = df.iloc[i]

            if current['high'] > left_high and current['high'] > right_high:
                fractals.append(Fractal(
                    idx=i,
                    type='top',
                    high=current['high'],
                    low=current['low'],
                    timestamp=current['open_time'] if 'open_time' in df.columns else pd.Timestamp.now(),
                ))

            if current['low'] < left_low and current['low'] < right_low:
                fractals.append(Fractal(
                    idx=i,
                    type='bottom',
                    high=current['high'],
                    low=current['low'],
                    timestamp=current['open_time'] if 'open_time' in df.columns else pd.Timestamp.now(),
                ))

        return fractals

    def _build_pens(self, fractals: List[Fractal]) -> List[Pen]:
        """笔构建（简化版）"""
        if len(fractals) < 2:
            return []

        pens = []
        i = 0

        while i < len(fractals) - 1:
            f1 = fractals[i]
            j = i + 1
            while j < len(fractals) and fractals[j].type == f1.type:
                if f1.type == 'top':
                    if fractals[j].high > f1.high:
                        f1 = fractals[j]
                        i = j
                else:
                    if fractals[j].low < f1.low:
                        f1 = fractals[j]
                        i = j
                j += 1

            if j < len(fractals):
                f2 = fractals[j]
                if f1.type == 'top' and f2.type == 'bottom':
                    direction = 'down'
                    high = f1.high
                    low = f2.low
                else:
                    direction = 'up'
                    high = f2.high
                    low = f1.low

                if (direction == 'up' and low >= high) or (direction == 'down' and high <= low):
                    i = j
                    continue

                pen = Pen(
                    start_fractal=f1,
                    end_fractal=f2,
                    direction=direction,
                    high=high,
                    low=low,
                    start_time=f1.timestamp,
                    end_time=f2.timestamp,
                    macd_area=0.0,
                )

                pens.append(pen)
            i = j

        return pens

    def generate_report(self, result: FirstBuyAnalysisResult) -> str:
        """生成可读的文字分析报告"""
        lines = []
        lines.append('=' * 60)
        lines.append('  缠论4H第一类买点（一买）背驰判断分析报告')
        lines.append('=' * 60)
        lines.append(f'分析时间：{result.timestamp}')
        lines.append('')

        lines.append('【第一步】趋势背景确认')
        lines.append('-' * 40)
        lines.append(result.trend_details)
        if not result.has_downtrend or result.zhongshu_count < self.min_zhongshu_for_buy:
            lines.append('')
            lines.append('>> 结论：不满足一买前提条件，终止分析。')
            return '\n'.join(lines)
        lines.append('')

        lines.append('【第二步】四大背驰判断维度')
        lines.append('-' * 40)
        for dim in result.dimensions:
            status = '✓ 满足' if dim.satisfied else '✗ 不满足'
            lines.append(f'维度：{dim.name} — {status}')
            for detail in dim.details:
                lines.append(f'  {detail}')
            lines.append('')

        lines.append('【第三步】背驰综合判定')
        lines.append('-' * 40)
        dim_status = []
        for dim in result.dimensions:
            dim_status.append(f'  {dim.name}：{"满足" if dim.satisfied else "不满足"}')
        lines.extend(dim_status)
        lines.append(f'总计满足维度数：{result.satisfied_count}个')
        if result.divergence_confirmed:
            lines.append('>> 判定结果：背驰成立 — 一买确认')
        else:
            lines.append('>> 判定结果：背驰不成立（满足维度<2）— 无一买信号')
        lines.append('')

        if result.divergence_confirmed:
            lines.append('【第四步】做多决策与策略')
            lines.append('-' * 40)
            lines.append(f'进场条件满足：{"是" if result.entry_conditions_met else "否（等待底分型确认）"}')
            lines.append(f'建议进场价格：{result.suggested_entry_price}')
            lines.append(f'止损价格：{result.stop_loss_price}')
            lines.append(f'目标位：')
            for i, t in enumerate(result.targets):
                lines.append(f'  目标{i + 1}：{t}')
            lines.append(f'仓位建议：首仓{result.position_advice.get("first_entry", 0.25) * 100:.0f}% | 加仓{result.position_advice.get("add_position", 0.35) * 100:.0f}% | 最大{result.position_advice.get("max_total", 0.55) * 100:.0f}%')
            lines.append('')

            lines.append('【第五步】后续跟踪要点')
            lines.append('-' * 40)
            for point in self._step5_followup_checkpoints(result):
                lines.append(f'  - {point}')

        lines.append('')
        lines.append('=' * 60)
        return '\n'.join(lines)

    def analyze_sell(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame) -> FirstSellAnalysisResult:
        result = FirstSellAnalysisResult(
            has_uptrend=False,
            zhongshu_count=0,
            in_final_breakout_segment=False,
            trend_details='',
            df_4h=df_4h,
            df_30m=df_30m,
            timestamp=datetime.now().isoformat(),
        )

        if df_4h.empty:
            result.trend_details = '4H数据为空，无法进行分析'
            return result

        has_uptrend, zhongshu_count, in_final, details, zhongshu_list, pens = self._step1_check_uptrend_background(df_4h)
        result.has_uptrend = has_uptrend
        result.zhongshu_count = zhongshu_count
        result.in_final_breakout_segment = in_final
        result.trend_details = details
        result.zhongshu_list = zhongshu_list

        if not has_uptrend or zhongshu_count < self.min_zhongshu_for_buy:
            result.trend_details += '\n不满足一卖前提条件（需上涨趋势+至少2个上涨中枢），终止分析。'
            return result

        up_segments = self._identify_up_segments(df_4h)
        result.up_segments = up_segments

        high_points = self._find_high_points(df_4h)

        dim1 = self._step2_sell_dimension1_price_structure(df_4h, up_segments)
        dim2 = self._step2_sell_dimension2_ma_system(df_4h, high_points)
        dim3 = self._step2_sell_dimension3_volume_verification(df_4h, high_points)
        dim4 = self._step2_sell_dimension4_mtf_confirmation(df_4h, df_30m)

        result.dimensions = [dim1, dim2, dim3, dim4]

        satisfied_count, divergence_confirmed = self._step3_sell_comprehensive_judgment(result.dimensions)
        result.satisfied_count = satisfied_count
        result.divergence_confirmed = divergence_confirmed

        decision = self._step4_sell_trading_decision(result, df_4h)
        result.entry_conditions_met = decision.get('entry_conditions_met', False)
        result.suggested_entry_price = decision.get('suggested_entry_price', 0.0)
        result.stop_loss_price = decision.get('stop_loss_price', 0.0)
        result.targets = decision.get('targets', [])
        result.position_advice = decision.get('position_advice', {})
        result.second_sell_zone = decision.get('second_sell_zone', None)

        return result

    def _step1_check_uptrend_background(self, df: pd.DataFrame) -> Tuple[bool, int, bool, str, List[ZhongShu], List[Pen]]:
        fractals = self._find_fractals(df, hg1=5)
        pens = self._build_pens(fractals)
        zhongshu_list = self._identify_zhongshu(pens, direction='up')

        has_uptrend = False
        details_parts = []

        if len(pens) < 4:
            details_parts.append('笔数量不足（<4），无法形成上涨趋势结构')
        else:
            up_pens = [p for p in pens if p.direction == 'up']
            down_pens = [p for p in pens if p.direction == 'down']

            if len(up_pens) >= 2:
                first_up = up_pens[0]
                last_up = up_pens[-1]

                if last_up.end_fractal.high > first_up.start_fractal.low:
                    has_uptrend = True
                    price_range = last_up.end_fractal.high - first_up.start_fractal.low
                    if price_range > 0:
                        pct = (price_range / first_up.start_fractal.low) * 100
                        details_parts.append(f'存在明确上涨趋势，涨幅约{pct:.1f}%')
                    else:
                        details_parts.append('存在明确上涨趋势结构')

                    if down_pens:
                        details_parts.append(f'上涨途中出现{len(down_pens)}次回调')
                else:
                    details_parts.append('未形成明确上涨趋势，价格未持续走高')
            else:
                details_parts.append('上涨笔不足2笔，趋势不明朗')

        zhongshu_count = len(zhongshu_list)

        if zhongshu_count > 0:
            details_parts.append(f'检测到{zhongshu_count}个上涨中枢')
            for i, zs in enumerate(zhongshu_list):
                details_parts.append(f'  中枢{i + 1}: [{zs.lower:.4f}, {zs.upper:.4f}]')
        else:
            details_parts.append('未检测到上涨中枢')
            if len(pens) >= 4:
                details_parts.append('（可能笔的重叠程度不足以形成中枢）')

        in_final_breakout = False
        if zhongshu_count >= self.min_zhongshu_for_buy and has_uptrend:
            last_zs = zhongshu_list[-1]
            current_price = df['close'].iloc[-1]
            if current_price > last_zs.upper:
                in_final_breakout = True
                details_parts.append(f'当前价格{current_price:.4f}高于最后中枢上沿{last_zs.upper:.4f}，处于向上离开段')
            else:
                in_final_breakout = True
                details_parts.append(f'当前价格在最后中枢({last_zs.lower:.4f}-{last_zs.upper:.4f})附近，处于离开段末端')

        return has_uptrend, zhongshu_count, in_final_breakout, '\n'.join(details_parts), zhongshu_list, pens

    def _step2_sell_dimension1_price_structure(self, df: pd.DataFrame, up_segments: List[UpSegment]) -> DimensionResult:
        dim = DimensionResult(name='走势结构力度衰减', satisfied=False)

        if len(up_segments) < 2:
            dim.details.append('上涨段不足2个，无法进行结构力度对比')
            return dim

        last_seg = up_segments[-1]
        prev_seg = up_segments[-2]

        sub1 = False
        sub2 = False
        sub3 = False

        if abs(prev_seg.slope) > 0.001:
            if abs(last_seg.slope) < abs(prev_seg.slope):
                sub1 = True
                dim.details.append(f'✓ 斜率衰减：最后一段斜率({last_seg.slope:.4f}) < 前一段({prev_seg.slope:.4f})，上涨势头减弱')
            else:
                dim.details.append(f'✗ 斜率衰减：最后一段斜率({last_seg.slope:.4f}) >= 前一段({prev_seg.slope:.4f})，上涨势头未减弱')
        else:
            dim.details.append('✗ 斜率衰减：前一段斜率接近0，无法有效对比')

        if last_seg.kline_count > prev_seg.kline_count:
            sub2 = True
            dim.details.append(f'✓ 结构复杂化：最后一段K线数({last_seg.kline_count}) > 前一段({prev_seg.kline_count})，耗时更长结构更复杂')
        else:
            time_ratio = last_seg.kline_count / max(prev_seg.kline_count, 1)
            if time_ratio > 0.8:
                sub2 = True
                dim.details.append(f'✓ 结构复杂化：最后一段耗时与前期接近(比例{time_ratio:.2f})，耗时充分')
            else:
                dim.details.append(f'✗ 结构复杂化：最后一段K线数({last_seg.kline_count}) <= 前一段({prev_seg.kline_count})，复杂度不足')

        if last_seg.pullback_strength_avg > prev_seg.pullback_strength_avg:
            sub3 = True
            dim.details.append(f'✓ 波动收敛：最后一段回调力度({last_seg.pullback_strength_avg:.6f}) > 前一段({prev_seg.pullback_strength_avg:.6f})，回调增强')
        else:
            high_diff = abs(last_seg.end_price - prev_seg.end_price)
            if high_diff < abs(prev_seg.start_price - prev_seg.end_price) * 0.5:
                sub3 = True
                dim.details.append(f'✓ 波动收敛：高点间距收敛，上涨笔幅度减小')
            else:
                dim.details.append(f'✗ 波动收敛：回调力度未增强，高点间距未明显收敛')

        if sub1 or sub2 or sub3:
            dim.satisfied = True

        return dim

    def _step2_sell_dimension2_ma_system(self, df: pd.DataFrame, high_points: List[Dict]) -> DimensionResult:
        dim = DimensionResult(name='均线系统背离', satisfied=False)

        if len(high_points) < 2:
            dim.details.append('阶段性高点不足2个，无法进行乖离率对比')
            return dim

        close = df['close']
        sub1 = False
        sub2 = False

        ma60 = calculate_ma(close, 60)

        if ma60.notna().any():
            latest_high = high_points[-1]
            prev_high = high_points[-2]

            latest_idx = latest_high['idx']
            prev_idx = prev_high['idx']

            if latest_idx < len(df) and prev_idx < len(df):
                latest_ma60_val = ma60.iloc[latest_idx]
                prev_ma60_val = ma60.iloc[prev_idx]

                if not pd.isna(latest_ma60_val) and not pd.isna(prev_ma60_val) and prev_ma60_val != 0:
                    latest_dev60 = abs((df['high'].iloc[latest_idx] - latest_ma60_val) / latest_ma60_val)
                    prev_dev60 = abs((df['high'].iloc[prev_idx] - prev_ma60_val) / prev_ma60_val)

                    if prev_dev60 > 0:
                        ratio = latest_dev60 / prev_dev60
                        if ratio < self.deviation_ratio_threshold:
                            sub1 = True
                            dim.details.append(f'✓ 乖离缩小：最新乖离率/前次乖离率={ratio:.3f} < {self.deviation_ratio_threshold}，显著缩小')
                        else:
                            dim.details.append(f'✗ 乖离缩小：最新乖离率/前次乖离率={ratio:.3f} >= {self.deviation_ratio_threshold}，未显著缩小')
                    else:
                        dim.details.append('✗ 乖离缩小：前次乖离率为0，无法计算比例')
                else:
                    dim.details.append('✗ 乖离缩小：均线数据不足，无法计算')
            else:
                dim.details.append('✗ 乖离缩小：高点索引越界')
        else:
            dim.details.append('✗ 乖离缩小：MA60均线数据不足')

        if len(close) >= 70:
            ma60_slope = calculate_ma_slope(close, 60, lookback=10)

            if abs(ma60_slope) < self.slope_flatten_threshold or ma60_slope <= 0:
                sub2 = True
                dim.details.append(f'✓ 均线走平：MA60斜率={ma60_slope:.6f}，上升斜率明显放缓或走平')
            else:
                dim.details.append(f'✗ 均线走平：MA60斜率={ma60_slope:.6f}，上升斜率仍较陡')
        else:
            dim.details.append('✗ 均线走平：数据不足以计算MA60斜率')

        if sub1 or sub2:
            dim.satisfied = True

        return dim

    def _step2_sell_dimension3_volume_verification(self, df: pd.DataFrame, high_points: List[Dict]) -> DimensionResult:
        dim = DimensionResult(name='成交量验证', satisfied=False)

        if 'volume' not in df.columns:
            dim.details.append('数据中缺少成交量字段')
            return dim

        sub1 = False
        sub2 = False

        if len(high_points) >= 2:
            latest_high = high_points[-1]
            prev_high = high_points[-2]

            latest_vol = df['volume'].iloc[latest_high['idx']]
            prev_vol = df['volume'].iloc[prev_high['idx']]

            if prev_vol > 0:
                ratio = calculate_volume_ratio(latest_vol, prev_vol)
                if ratio < self.volume_shrink_threshold:
                    sub1 = True
                    dim.details.append(f'✓ 价升量缩：最新高点量/前次高点量={ratio:.3f} < {self.volume_shrink_threshold}，显著萎缩')
                else:
                    dim.details.append(f'✗ 价升量缩：最新高点量/前次高点量={ratio:.3f} >= {self.volume_shrink_threshold}，未显著萎缩')
            else:
                dim.details.append('✗ 价升量缩：前次高点成交量为0，无法计算')
        else:
            dim.details.append('✗ 价升量缩：阶段性高点不足2个')

        pattern = detect_volume_price_pattern_uptrend(df, recent_bars=min(40, len(df)))
        sub2 = pattern.get('pattern_shifted', False)
        dim.details.append(f'量价结构：{pattern.get("detail", "检测失败")}')

        if sub1 or sub2:
            dim.satisfied = True

        return dim

    def _step2_sell_dimension4_mtf_confirmation(self, df_4h: pd.DataFrame, df_30m: pd.DataFrame) -> DimensionResult:
        dim = DimensionResult(name='多级别联立确认', satisfied=False)

        if df_30m.empty or len(df_30m) < 50:
            dim.details.append('30分钟K线数据不足')
            return dim

        fractals_30m = self._find_fractals(df_30m, hg1=5)
        pens_30m = self._build_pens(fractals_30m)
        zhongshu_30m = self._identify_zhongshu(pens_30m, direction='up')

        up_pens_30m = [p for p in pens_30m if p.direction == 'up']
        has_trend_30m = len(up_pens_30m) >= 2
        has_zhongshu_30m = len(zhongshu_30m) >= 1

        if has_trend_30m and has_zhongshu_30m:
            dim.satisfied = True
            dim.details.append(f'✓ 30分钟出现上涨趋势+{len(zhongshu_30m)}个上涨中枢，存在顶背驰结构')
        elif has_trend_30m:
            dim.satisfied = True
            dim.details.append(f'✓ 30分钟出现上涨趋势（{len(up_pens_30m)}个上涨笔），存在背驰特征')
        elif has_zhongshu_30m:
            dim.satisfied = True
            dim.details.append(f'✓ 30分钟出现{len(zhongshu_30m)}个上涨中枢，趋势结构明确')
        else:
            dim.satisfied = False
            dim.details.append(f'✗ 30分钟未出现清晰的上涨趋势结构')

        if not dim.satisfied:
            high_points_30m = self._find_high_points(df_30m)
            if len(high_points_30m) >= 2:
                latest_vol = df_30m['volume'].iloc[high_points_30m[-1]['idx']] if 'volume' in df_30m.columns else 0
                prev_vol = df_30m['volume'].iloc[high_points_30m[-2]['idx']] if 'volume' in df_30m.columns else 0
                if prev_vol > 0 and latest_vol / prev_vol < self.volume_shrink_threshold:
                    dim.satisfied = True
                    dim.details.append(f'✓ 30分钟量价背离：最新高点量显著萎缩')

        return dim

    def _step3_sell_comprehensive_judgment(self, dimensions: List[DimensionResult]) -> Tuple[int, bool]:
        satisfied_count = sum(1 for d in dimensions if d.satisfied)
        divergence_confirmed = satisfied_count >= self.min_dimensions_for_divergence
        return satisfied_count, divergence_confirmed

    def _step4_sell_trading_decision(self, result: FirstSellAnalysisResult, df: pd.DataFrame) -> Dict[str, Any]:
        decision = {
            'entry_conditions_met': False,
            'suggested_entry_price': 0.0,
            'stop_loss_price': 0.0,
            'targets': [],
            'position_advice': {
                'first_entry': 0.25,
                'add_position': 0.35,
                'max_total': 0.55,
            },
            'second_sell_zone': None,
        }

        if not result.divergence_confirmed:
            return decision

        latest_high = df['high'].max()
        latest_close = df['close'].iloc[-1]

        has_top_fractal = self._check_top_fractal_confirm(df, lookback=8)

        if has_top_fractal:
            decision['entry_conditions_met'] = True

        decision['suggested_entry_price'] = round(latest_close, 4)
        decision['stop_loss_price'] = round(latest_high * 1.02, 4)

        if result.zhongshu_list:
            last_zs = result.zhongshu_list[-1]
            targets = [
                round(last_zs.upper, 4),
                round(last_zs.lower, 4),
            ]
            if len(result.zhongshu_list) >= 2:
                prev_zs = result.zhongshu_list[-2]
                targets.append(round(prev_zs.upper, 4))
                targets.append(round(prev_zs.lower, 4))
            if result.up_segments:
                targets.append(round(result.up_segments[0].start_price, 4))
            targets.sort(reverse=True)
            decision['targets'] = targets

        last_high_price = latest_high
        for seg in result.up_segments:
            if seg.end_price > last_high_price and last_high_price > 0:
                last_high_price = seg.end_price

        if result.has_uptrend and last_high_price > 0:
            decision['second_sell_zone'] = (round(last_high_price * 0.98, 4), round(last_high_price, 4))

        return decision

    def _step5_sell_followup_checkpoints(self, result: FirstSellAnalysisResult) -> List[str]:
        points = [
            '【二卖确认】等待一卖后下跌一笔的反弹，不破一卖高点即确认二卖',
            '【中枢演化】观察下跌过程中中枢的构建与下跌力度，新中枢不升破旧中枢下沿即为强势下跌',
            '【级别扩展】关注4小时下跌是否引发日线级别转折，日线出现顶分型则级别扩展确认',
        ]
        return points

    def _identify_up_segments(self, df: pd.DataFrame) -> List[UpSegment]:
        segments = []

        if df.empty or len(df) < 10:
            return segments

        extremes = find_price_extremes(df, window=5)
        highs = extremes.get('highs', [])

        for i in range(len(highs) - 1):
            start_idx = highs[i]
            end_idx = highs[i + 1]

            if start_idx >= end_idx:
                continue

            seg_data = df.iloc[start_idx:end_idx + 1]
            start_price = df['high'].iloc[start_idx]
            end_price = df['high'].iloc[end_idx]

            slope = calculate_price_slope(seg_data['close'])
            kline_count = count_klines_between_points(df, start_idx, end_idx)

            pullback_sum = 0.0
            pullback_count = 0
            prev_high = start_price
            for j in range(start_idx + 1, end_idx):
                current_high = df['high'].iloc[j]
                if current_high < prev_high:
                    pullback = (prev_high - current_high) / max(prev_high, 0.0001)
                    pullback_sum += pullback
                    pullback_count += 1
                prev_high = current_high

            pullback_avg = pullback_sum / max(pullback_count, 1)

            segments.append(UpSegment(
                start_idx=start_idx,
                end_idx=end_idx,
                start_price=start_price,
                end_price=end_price,
                slope=slope,
                kline_count=kline_count,
                pullback_strength_avg=pullback_avg,
            ))

        return segments

    def _find_high_points(self, df: pd.DataFrame) -> List[Dict]:
        high_points = []

        if df.empty:
            return high_points

        extremes = find_price_extremes(df, window=5)
        high_indices = extremes.get('highs', [])

        for idx in high_indices:
            point = {
                'idx': idx,
                'price': df['high'].iloc[idx],
                'volume': df['volume'].iloc[idx] if 'volume' in df.columns else 0,
                'time': str(df.index[idx]) if isinstance(df.index, pd.DatetimeIndex) else str(idx),
            }
            high_points.append(point)

        high_points.sort(key=lambda x: x['price'], reverse=True)
        return high_points

    def _check_top_fractal_confirm(self, df: pd.DataFrame, lookback: int = 8) -> bool:
        if len(df) < lookback + 3:
            return False

        recent = df.iloc[-(lookback + 3):]

        for i in range(1, len(recent) - 1):
            current = recent.iloc[i]
            left = recent.iloc[i - 1:i]
            right = recent.iloc[i + 1:i + 2]

            if len(left) == 0 or len(right) == 0:
                continue

            if current['high'] > left['high'].max() and current['high'] > right['high'].max():
                if len(right) > 0:
                    recent_close = df['close'].iloc[-1]
                    recent_high = df['high'].iloc[-3:].max()
                    if recent_high < current['high']:
                        return True

        return False

    def generate_sell_report(self, result: FirstSellAnalysisResult) -> str:
        lines = []
        lines.append('=' * 60)
        lines.append('  缠论4H第一类卖点（一卖）顶背驰判断分析报告')
        lines.append('=' * 60)
        lines.append(f'分析时间：{result.timestamp}')
        lines.append('')

        lines.append('【第一步】趋势背景确认')
        lines.append('-' * 40)
        lines.append(result.trend_details)
        if not result.has_uptrend or result.zhongshu_count < self.min_zhongshu_for_buy:
            lines.append('')
            lines.append('>> 结论：不满足一卖前提条件，终止分析。')
            return '\n'.join(lines)
        lines.append('')

        lines.append('【第二步】四大背驰判断维度')
        lines.append('-' * 40)
        for dim in result.dimensions:
            status = '✓ 满足' if dim.satisfied else '✗ 不满足'
            lines.append(f'维度：{dim.name} — {status}')
            for detail in dim.details:
                lines.append(f'  {detail}')
            lines.append('')

        lines.append('【第三步】背驰综合判定')
        lines.append('-' * 40)
        dim_status = []
        for dim in result.dimensions:
            dim_status.append(f'  {dim.name}：{"满足" if dim.satisfied else "不满足"}')
        lines.extend(dim_status)
        lines.append(f'总计满足维度数：{result.satisfied_count}个')
        if result.divergence_confirmed:
            lines.append('>> 判定结果：顶背驰成立 — 一卖确认')
        else:
            lines.append('>> 判定结果：顶背驰不成立（满足维度<2）— 无一卖信号')
        lines.append('')

        if result.divergence_confirmed:
            lines.append('【第四步】做空决策与策略')
            lines.append('-' * 40)
            lines.append(f'进场条件满足：{"是" if result.entry_conditions_met else "否（等待顶分型确认）"}')
            lines.append(f'建议进场价格：{result.suggested_entry_price}')
            lines.append(f'止损价格：{result.stop_loss_price}')
            lines.append(f'目标位（从高到低）：')
            for i, t in enumerate(result.targets):
                lines.append(f'  目标{i + 1}：{t}')
            lines.append(f'仓位建议：首仓{result.position_advice.get("first_entry", 0.25) * 100:.0f}% | 加仓{result.position_advice.get("add_position", 0.35) * 100:.0f}% | 最大{result.position_advice.get("max_total", 0.55) * 100:.0f}%')
            lines.append('')

            lines.append('【第五步】后续跟踪要点')
            lines.append('-' * 40)
            checkpoints = ['【二卖确认】等待一卖后下跌一笔的反弹，不破一卖高点即确认二卖',
                           '【中枢演化】观察下跌过程中中枢的构建与下跌力度，新中枢不升破旧中枢下沿即为强势下跌',
                           '【级别扩展】关注4小时下跌是否引发日线级别转折，日线出现顶分型则级别扩展确认']
            for point in checkpoints:
                lines.append(f'  - {point}')

        lines.append('')
        lines.append('=' * 60)
        return '\n'.join(lines)



    def analyze_second_buy(self, df_4h, df_30m, first_buy_result):
        result = SecondBuyAnalysisResult(
            first_buy_confirmed=False, first_buy_low=0.0, first_buy_idx=-1,
            has_rise_pullback=False,
            df_4h=df_4h, df_30m=df_30m, timestamp=datetime.now().isoformat(),
        )
        if not first_buy_result.divergence_confirmed:
            result.details.append('前提不满足：一买未确认，无法进行二买分析')
            return result
        result.first_buy_confirmed = True
        buy_idx, buy_low = self._sb_find_first_buy_point(df_4h, first_buy_result)
        result.first_buy_idx = buy_idx
        result.first_buy_low = buy_low
        result.details.append(f'一买定位：索引{buy_idx}，最低价{buy_low:.4f}')
        has_structure, zhongshu, pullback_idx, pullback_low = self._sb_check_rise_pullback_structure(df_4h, buy_idx)
        result.has_rise_pullback = has_structure
        result.first_rising_zhongshu = zhongshu
        result.pullback_low_idx = pullback_idx
        result.pullback_low = pullback_low
        if not has_structure:
            result.details.append('结构不满足：一买后未出现清晰的上涨+回调结构')
            return result
        if pullback_low > buy_low:
            result.core_condition_met = True
            result.details.append(f'核心条件满足：回调低点{pullback_low:.4f} > 一买低点{buy_low:.4f}')
        else:
            result.core_condition_met = False
            result.details.append(f'核心条件不满足：回调低点{pullback_low:.4f} <= 一买低点{buy_low:.4f}，二买不成立')
            return result
        if zhongshu is not None:
            result.strength_class = self._sb_classify_strength(pullback_low, zhongshu, buy_low)
            result.details.append(f'强度分级：{result.strength_class}二买')
        else:
            result.strength_class = 'weak'
            result.details.append('强度分级：弱势二买（未形成明确上涨中枢）')
        result.lower_tf_divergence = self._sb_check_lower_tf_divergence(df_30m, buy_low)
        if result.lower_tf_divergence:
            result.details.append('30M小级别：确认背驰结构')
        else:
            result.details.append('30M小级别：未确认背驰结构')
        vol, ma_sup, mom = self._sb_auxiliary_verification(df_4h, buy_idx)
        result.volume_shrinking = vol
        result.ma_support = ma_sup
        result.momentum_weakening = mom
        aux_signals = []
        if vol: aux_signals.append('回调缩量')
        if ma_sup: aux_signals.append('均线支撑')
        if mom: aux_signals.append('力度减弱')
        if aux_signals:
            result.details.append(f'辅助验证：{", ".join(aux_signals)}')
        aux_count = sum([vol, ma_sup, mom])
        if result.core_condition_met and result.lower_tf_divergence and aux_count >= 2:
            result.second_buy_confirmed = True
            result.details.append('>> 二买综合确认成立')
        elif result.core_condition_met and result.lower_tf_divergence:
            result.second_buy_confirmed = True
            result.details.append('>> 二买综合确认成立（核心条件+小级别背驰满足）')
        else:
            result.second_buy_confirmed = False
            result.details.append('>> 二买条件不完全满足，建议等待')
        if result.second_buy_confirmed:
            decision = self._sb_trading_decision(result, df_4h)
            result.suggested_entry = decision.get('suggested_entry', 0.0)
            result.stop_loss = decision.get('stop_loss', 0.0)
            result.targets = decision.get('targets', [])
            result.position_advice = decision.get('position_advice', {})
        return result

    def _sb_find_first_buy_point(self, df, first_buy_result):
        if not first_buy_result.zhongshu_list:
            low_idx = df['low'].idxmin()
            if isinstance(low_idx, int):
                return low_idx, df['low'].iloc[low_idx]
            return len(df) - 1, df['low'].iloc[-1]
        last_zs = first_buy_result.zhongshu_list[-1]
        search_start = last_zs.end_idx
        if search_start >= len(df):
            search_start = len(df) - 10
        sub_df = df.iloc[search_start:]
        if sub_df.empty:
            return len(df) - 1, df['low'].iloc[-1]
        low_val = sub_df['low'].min()
        low_idx = int(sub_df['low'].values.argmin()) + search_start
        return low_idx, low_val

    def _sb_check_rise_pullback_structure(self, df, first_buy_idx):
        if first_buy_idx < 0 or first_buy_idx >= len(df) - 5:
            return False, None, -1, 0.0
        post_buy_df = df.iloc[first_buy_idx:].reset_index(drop=True)
        if len(post_buy_df) < 8:
            return False, None, -1, 0.0
        fractals = self._find_fractals(post_buy_df, hg1=3)
        pens = self._build_pens(fractals)
        up_pens = [p for p in pens if p.direction == 'up']
        down_pens = [p for p in pens if p.direction == 'down']
        if not up_pens:
            return False, None, -1, 0.0
        first_up = up_pens[0]
        pullback_found = False
        pullback_idx = -1
        pullback_low = float('inf')
        for p in down_pens:
            if p.start_fractal.idx >= first_up.end_fractal.idx:
                pullback_found = True
                if p.low < pullback_low:
                    pullback_low = p.low
                    pullback_idx = p.end_fractal.idx
                break
        if not pullback_found:
            for i in range(first_up.end_fractal.idx, len(post_buy_df)):
                if post_buy_df['low'].iloc[i] < pullback_low:
                    pullback_low = post_buy_df['low'].iloc[i]
                    pullback_idx = i
            if pullback_idx > first_up.end_fractal.idx:
                pullback_found = True
        if not pullback_found:
            return False, None, -1, 0.0
        zhongshu = None
        if len(pens) >= 3:
            zhongshu_list = self._identify_zhongshu(pens, direction='up')
            if zhongshu_list:
                zhongshu = zhongshu_list[0]
        return True, zhongshu, pullback_idx + first_buy_idx, pullback_low

    def _sb_classify_strength(self, pullback_low, zhongshu, first_buy_low):
        if zhongshu is None:
            return 'weak'
        if pullback_low >= zhongshu.upper:
            return 'strong'
        elif pullback_low >= zhongshu.lower:
            return 'standard'
        else:
            return 'weak'

    def _sb_check_lower_tf_divergence(self, df_30m, first_buy_low):
        if df_30m.empty or len(df_30m) < 30:
            return False
        extremes = find_price_extremes(df_30m, window=5)
        lows_30m = extremes.get('lows', [])
        if len(lows_30m) < 2:
            return False
        close_30m = df_30m['close']
        recent_lows = [idx for idx in lows_30m if idx > len(df_30m) * 0.5]
        if len(recent_lows) < 2:
            recent_lows = lows_30m[-4:] if len(lows_30m) >= 4 else lows_30m
        if len(recent_lows) < 2:
            return False
        last_low_idx = recent_lows[-1]
        prev_low_idx = recent_lows[-2]
        if last_low_idx >= len(close_30m) or prev_low_idx >= len(close_30m):
            return False
        last_price = df_30m['low'].iloc[last_low_idx]
        prev_price = df_30m['low'].iloc[prev_low_idx]
        if last_price >= prev_price:
            return False
        if prev_low_idx < last_low_idx:
            seg1 = close_30m.iloc[prev_low_idx:last_low_idx]
            if len(seg1) >= 5:
                slope = calculate_price_slope(seg1)
                if slope < 0 and abs(slope) < 2.0:
                    return True
        if 'volume' in df_30m.columns:
            last_vol = df_30m['volume'].iloc[last_low_idx]
            prev_vol = df_30m['volume'].iloc[prev_low_idx]
            if prev_vol > 0 and last_vol / prev_vol < self.volume_shrink_threshold:
                return True
        return False

    def _sb_auxiliary_verification(self, df, first_buy_idx):
        volume_shrinking = False
        ma_support = False
        momentum_weakening = False
        if first_buy_idx < 0 or first_buy_idx >= len(df) - 10:
            return volume_shrinking, ma_support, momentum_weakening
        post_buy = df.iloc[first_buy_idx:]
        if 'volume' in df.columns and len(post_buy) >= 8:
            half = len(post_buy) // 2
            first_half_vol = post_buy['volume'].iloc[:half].mean()
            second_half_vol = post_buy['volume'].iloc[half:].mean()
            if first_half_vol > 0 and second_half_vol < first_half_vol:
                volume_shrinking = True
        close = df['close']
        if len(close) >= 30:
            ma20 = calculate_ma(close, 20)
            ma60 = calculate_ma(close, 60)
            if not pd.isna(ma20.iloc[-1]) and not pd.isna(ma60.iloc[-1]):
                current_low = df['low'].iloc[-1]
                if current_low > ma20.iloc[-1] * 0.98 or current_low > ma60.iloc[-1] * 0.98:
                    ma_support = True
        if len(post_buy) >= 8:
            fractals = self._find_fractals(post_buy, hg1=3)
            pens = self._build_pens(fractals)
            up_pen = next((p for p in pens if p.direction == 'up'), None)
            down_pen = next((p for p in pens if p.direction == 'down'), None)
            if up_pen is not None and down_pen is not None:
                up_range = up_pen.high - up_pen.low
                down_range = down_pen.high - down_pen.low
                if up_range > 0 and down_range < up_range * 0.8:
                    momentum_weakening = True
        return volume_shrinking, ma_support, momentum_weakening

    def _sb_trading_decision(self, result, df):
        decision = {
            'suggested_entry': 0.0, 'stop_loss': 0.0, 'targets': [],
            'position_advice': {'first_entry': 0.35, 'add_position': 0.35, 'max_total': 0.60},
        }
        latest_close = df['close'].iloc[-1]
        decision['suggested_entry'] = round(latest_close, 4)
        decision['stop_loss'] = round(result.first_buy_low * 0.98, 4)
        if result.first_rising_zhongshu is not None:
            zs = result.first_rising_zhongshu
            targets = [round(zs.upper, 4), round(zs.upper * 1.03, 4)]
            if result.df_4h is not None and len(result.df_4h) > 0:
                trend_high = result.df_4h['high'].iloc[:result.first_buy_idx].max()
                targets.append(round(trend_high, 4))
            targets.sort()
            decision['targets'] = targets
        else:
            decision['targets'] = [round(latest_close * 1.03, 4), round(latest_close * 1.05, 4)]
        return decision

    def generate_second_buy_report(self, result):
        lines = []
        lines.append('=' * 60)
        lines.append('  缠论第二类买点（二买）分析报告')
        lines.append('=' * 60)
        lines.append(f'分析时间：{result.timestamp}')
        lines.append('')
        lines.append('【前提检查】一买状态')
        lines.append('-' * 40)
        if not result.first_buy_confirmed:
            lines.append('一买未确认，终止二买分析。')
            return '\n'.join(lines)
        lines.append(f'一买已确认')
        lines.append(f'一买最低价：{result.first_buy_low:.4f}')
        lines.append(f'一买点索引：{result.first_buy_idx}')
        lines.append('')
        lines.append('【第一步】结构定位 — 一买后上涨+回调')
        lines.append('-' * 40)
        if not result.has_rise_pullback:
            lines.append('未出现清晰的上涨+回调结构，二买不成立。')
            return '\n'.join(lines)
        lines.append('一买后出现首段上涨 + 回调结构')
        if result.first_rising_zhongshu is not None:
            zs = result.first_rising_zhongshu
            lines.append(f'第一个上涨中枢：[{zs.lower:.4f}, {zs.upper:.4f}]')
        lines.append('')
        lines.append('【第二步】核心几何条件')
        lines.append('-' * 40)
        lines.append(f'一买最低点：{result.first_buy_low:.4f}')
        lines.append(f'回调最低点：{result.pullback_low:.4f}')
        if result.core_condition_met:
            lines.append('回调低点 > 一买低点 — 二买区域确立')
            lines.append(f'强度分级：{result.strength_class}二买')
        else:
            lines.append('回调低点 <= 一买低点 — 二买不成立')
            return '\n'.join(lines)
        lines.append('')
        lines.append('【第三步】小级别验证')
        lines.append('-' * 40)
        lines.append('30分钟级别背驰确认' if result.lower_tf_divergence else '30分钟级别未确认背驰')
        lines.append('')
        lines.append('【辅助验证】')
        lines.append('-' * 40)
        lines.append(f'回调缩量：{"是" if result.volume_shrinking else "否"}')
        lines.append(f'均线支撑：{"是" if result.ma_support else "否"}')
        lines.append(f'力度减弱：{"是" if result.momentum_weakening else "否"}')
        lines.append('')
        lines.append('【综合判定】')
        lines.append('-' * 40)
        for detail in result.details:
            lines.append(f'  {detail}')
        lines.append('')
        if result.second_buy_confirmed:
            lines.append('【交易执行】')
            lines.append('-' * 40)
            lines.append(f'建议入场价：{result.suggested_entry}')
            lines.append(f'止损（一买低点下方）：{result.stop_loss:.4f}')
            lines.append('目标位：')
            for i, t in enumerate(result.targets):
                lines.append(f'  目标{i + 1}：{t:.4f}')
            pct = result.position_advice
            lines.append(f'仓位建议：首仓{pct.get("first_entry", 0.35) * 100:.0f}% | 加仓{pct.get("add_position", 0.35) * 100:.0f}%')
        lines.append('')
        lines.append('=' * 60)
        return '\n'.join(lines)


    def analyze_second_sell(self, df_4h, df_30m, first_sell_result):
        result = SecondSellAnalysisResult(
            first_sell_confirmed=False, first_sell_high=0.0, first_sell_idx=-1,
            has_fall_bounce=False,
            df_4h=df_4h, df_30m=df_30m, timestamp=datetime.now().isoformat(),
        )
        if not first_sell_result.divergence_confirmed:
            result.details.append('前提不满足：一卖未确认，无法进行二卖分析')
            return result
        result.first_sell_confirmed = True
        sell_idx, sell_high = self._ss_find_first_sell_point(df_4h, first_sell_result)
        result.first_sell_idx = sell_idx
        result.first_sell_high = sell_high
        result.details.append(f'一卖定位：索引{sell_idx}，最高价{sell_high:.4f}')
        has_structure, zhongshu, bounce_idx, bounce_high = self._ss_check_fall_bounce_structure(df_4h, sell_idx)
        result.has_fall_bounce = has_structure
        result.first_falling_zhongshu = zhongshu
        result.bounce_high_idx = bounce_idx
        result.bounce_high = bounce_high
        if not has_structure:
            result.details.append('结构不满足：一卖后未出现清晰的下跌+反弹结构')
            return result
        if bounce_high < sell_high:
            result.core_condition_met = True
            result.details.append(f'核心条件满足：反弹高点{bounce_high:.4f} < 一卖高点{sell_high:.4f}')
        else:
            result.core_condition_met = False
            result.details.append(f'核心条件不满足：反弹高点{bounce_high:.4f} >= 一卖高点{sell_high:.4f}，二卖不成立')
            return result
        if zhongshu is not None:
            result.strength_class = self._ss_classify_strength(bounce_high, zhongshu, sell_high)
            result.details.append(f'强度分级：{result.strength_class}二卖')
        else:
            result.strength_class = 'weak'
            result.details.append('强度分级：弱势二卖（未形成明确下跌中枢）')
        result.lower_tf_divergence = self._ss_check_lower_tf_divergence(df_30m, sell_high)
        if result.lower_tf_divergence:
            result.details.append('30M小级别：确认上涨背驰结构')
        else:
            result.details.append('30M小级别：未确认上涨背驰')
        vol, ma_res, mom = self._ss_auxiliary_verification(df_4h, sell_idx)
        result.volume_shrinking = vol
        result.ma_resistance = ma_res
        result.momentum_weakening = mom
        aux_signals = []
        if vol: aux_signals.append('反弹缩量')
        if ma_res: aux_signals.append('均线压力')
        if mom: aux_signals.append('力度减弱')
        if aux_signals:
            result.details.append(f'辅助验证：{", ".join(aux_signals)}')
        aux_count = sum([vol, ma_res, mom])
        if result.core_condition_met and result.lower_tf_divergence and aux_count >= 2:
            result.second_sell_confirmed = True
            result.details.append('>> 二卖综合确认成立')
        elif result.core_condition_met and result.lower_tf_divergence:
            result.second_sell_confirmed = True
            result.details.append('>> 二卖综合确认成立（核心条件+小级别背驰满足）')
        else:
            result.second_sell_confirmed = False
            result.details.append('>> 二卖条件不完全满足，建议等待')
        if result.second_sell_confirmed:
            decision = self._ss_trading_decision(result, df_4h)
            result.suggested_entry = decision.get('suggested_entry', 0.0)
            result.stop_loss = decision.get('stop_loss', 0.0)
            result.targets = decision.get('targets', [])
            result.position_advice = decision.get('position_advice', {})
        return result

    def _ss_find_first_sell_point(self, df, first_sell_result):
        if not first_sell_result.zhongshu_list:
            high_idx = df['high'].idxmax()
            if isinstance(high_idx, int):
                return high_idx, df['high'].iloc[high_idx]
            return len(df) - 1, df['high'].iloc[-1]
        last_zs = first_sell_result.zhongshu_list[-1]
        search_start = last_zs.end_idx
        if search_start >= len(df):
            search_start = len(df) - 10
        sub_df = df.iloc[search_start:]
        if sub_df.empty:
            return len(df) - 1, df['high'].iloc[-1]
        high_val = sub_df['high'].max()
        high_idx = int(sub_df['high'].values.argmax()) + search_start
        return high_idx, high_val

    def _ss_check_fall_bounce_structure(self, df, first_sell_idx):
        if first_sell_idx < 0 or first_sell_idx >= len(df) - 5:
            return False, None, -1, 0.0
        post_sell_df = df.iloc[first_sell_idx:].reset_index(drop=True)
        if len(post_sell_df) < 8:
            return False, None, -1, 0.0
        fractals = self._find_fractals(post_sell_df, hg1=3)
        pens = self._build_pens(fractals)
        down_pens = [p for p in pens if p.direction == 'down']
        up_pens = [p for p in pens if p.direction == 'up']
        if not down_pens:
            return False, None, -1, 0.0
        first_down = down_pens[0]
        bounce_found = False
        bounce_idx = -1
        bounce_high = 0.0
        for p in up_pens:
            if p.start_fractal.idx >= first_down.end_fractal.idx:
                bounce_found = True
                if p.high > bounce_high:
                    bounce_high = p.high
                    bounce_idx = p.end_fractal.idx
                break
        if not bounce_found:
            for i in range(first_down.end_fractal.idx, len(post_sell_df)):
                if post_sell_df['high'].iloc[i] > bounce_high:
                    bounce_high = post_sell_df['high'].iloc[i]
                    bounce_idx = i
            if bounce_idx > first_down.end_fractal.idx:
                bounce_found = True
        if not bounce_found:
            return False, None, -1, 0.0
        zhongshu = None
        if len(pens) >= 3:
            zhongshu_list = self._identify_zhongshu(pens, direction='down')
            if zhongshu_list:
                zhongshu = zhongshu_list[0]
        return True, zhongshu, bounce_idx + first_sell_idx, bounce_high

    def _ss_classify_strength(self, bounce_high, zhongshu, first_sell_high):
        if zhongshu is None:
            return 'weak'
        if bounce_high <= zhongshu.lower:
            return 'strong'
        elif bounce_high <= zhongshu.upper:
            return 'standard'
        else:
            return 'weak'

    def _ss_check_lower_tf_divergence(self, df_30m, first_sell_high):
        if df_30m.empty or len(df_30m) < 30:
            return False
        extremes = find_price_extremes(df_30m, window=5)
        highs_30m = extremes.get('highs', [])
        if len(highs_30m) < 2:
            return False
        close_30m = df_30m['close']
        recent_highs = [idx for idx in highs_30m if idx > len(df_30m) * 0.5]
        if len(recent_highs) < 2:
            recent_highs = highs_30m[-4:] if len(highs_30m) >= 4 else highs_30m
        if len(recent_highs) < 2:
            return False
        last_high_idx = recent_highs[-1]
        prev_high_idx = recent_highs[-2]
        if last_high_idx >= len(close_30m) or prev_high_idx >= len(close_30m):
            return False
        last_price = df_30m['high'].iloc[last_high_idx]
        prev_price = df_30m['high'].iloc[prev_high_idx]
        if last_price <= prev_price:
            return False
        if prev_high_idx < last_high_idx:
            seg1 = close_30m.iloc[prev_high_idx:last_high_idx]
            if len(seg1) >= 5:
                slope = calculate_price_slope(seg1)
                if slope > 0 and slope < 2.0:
                    return True
        if 'volume' in df_30m.columns:
            last_vol = df_30m['volume'].iloc[last_high_idx]
            prev_vol = df_30m['volume'].iloc[prev_high_idx]
            if prev_vol > 0 and last_vol / prev_vol < self.volume_shrink_threshold:
                return True
        return False

    def _ss_auxiliary_verification(self, df, first_sell_idx):
        volume_shrinking = False
        ma_resistance = False
        momentum_weakening = False
        if first_sell_idx < 0 or first_sell_idx >= len(df) - 10:
            return volume_shrinking, ma_resistance, momentum_weakening
        post_sell = df.iloc[first_sell_idx:]
        if 'volume' in df.columns and len(post_sell) >= 8:
            half = len(post_sell) // 2
            first_half_vol = post_sell['volume'].iloc[:half].mean()
            second_half_vol = post_sell['volume'].iloc[half:].mean()
            if first_half_vol > 0 and second_half_vol < first_half_vol:
                volume_shrinking = True
        close = df['close']
        if len(close) >= 30:
            ma20 = calculate_ma(close, 20)
            ma60 = calculate_ma(close, 60)
            if not pd.isna(ma20.iloc[-1]) and not pd.isna(ma60.iloc[-1]):
                current_high = df['high'].iloc[-1]
                if current_high < ma20.iloc[-1] * 1.02 or current_high < ma60.iloc[-1] * 1.02:
                    ma_resistance = True
        if len(post_sell) >= 8:
            fractals = self._find_fractals(post_sell, hg1=3)
            pens = self._build_pens(fractals)
            down_pen = next((p for p in pens if p.direction == 'down'), None)
            up_pen = next((p for p in pens if p.direction == 'up'), None)
            if down_pen is not None and up_pen is not None:
                down_range = down_pen.high - down_pen.low
                up_range = up_pen.high - up_pen.low
                if down_range > 0 and up_range < down_range * 0.8:
                    momentum_weakening = True
        return volume_shrinking, ma_resistance, momentum_weakening

    def _ss_trading_decision(self, result, df):
        decision = {
            'suggested_entry': 0.0, 'stop_loss': 0.0, 'targets': [],
            'position_advice': {'first_entry': 0.35, 'add_position': 0.35, 'max_total': 0.60},
        }
        latest_close = df['close'].iloc[-1]
        decision['suggested_entry'] = round(latest_close, 4)
        decision['stop_loss'] = round(result.first_sell_high * 1.02, 4)
        if result.first_falling_zhongshu is not None:
            zs = result.first_falling_zhongshu
            targets = [round(zs.lower, 4), round(zs.lower * 0.97, 4)]
            if result.df_4h is not None and len(result.df_4h) > 0:
                trend_low = result.df_4h['low'].iloc[:result.first_sell_idx].min()
                targets.append(round(trend_low, 4))
            targets.sort(reverse=True)
            decision['targets'] = targets
        else:
            decision['targets'] = [round(latest_close * 0.97, 4), round(latest_close * 0.95, 4)]
        return decision

    def generate_second_sell_report(self, result):
        lines = []
        lines.append('=' * 60)
        lines.append('  缠论第二类卖点（二卖）分析报告')
        lines.append('=' * 60)
        lines.append(f'分析时间：{result.timestamp}')
        lines.append('')
        lines.append('【前提检查】一卖状态')
        lines.append('-' * 40)
        if not result.first_sell_confirmed:
            lines.append('一卖未确认，终止二卖分析。')
            return '\n'.join(lines)
        lines.append('一卖已确认')
        lines.append(f'一卖最高价：{result.first_sell_high:.4f}')
        lines.append(f'一卖点索引：{result.first_sell_idx}')
        lines.append('')
        lines.append('【第一步】结构定位 — 一卖后下跌+反弹')
        lines.append('-' * 40)
        if not result.has_fall_bounce:
            lines.append('未出现清晰的下跌+反弹结构，二卖不成立。')
            return '\n'.join(lines)
        lines.append('一卖后出现首段下跌 + 反弹结构')
        if result.first_falling_zhongshu is not None:
            zs = result.first_falling_zhongshu
            lines.append(f'第一个下跌中枢：[{zs.lower:.4f}, {zs.upper:.4f}]')
        lines.append('')
        lines.append('【第二步】核心几何条件')
        lines.append('-' * 40)
        lines.append(f'一卖最高点：{result.first_sell_high:.4f}')
        lines.append(f'反弹最高点：{result.bounce_high:.4f}')
        if result.core_condition_met:
            lines.append('反弹高点 < 一卖高点 — 二卖区域确立')
            lines.append(f'强度分级：{result.strength_class}二卖')
        else:
            lines.append('反弹高点 >= 一卖高点 — 二卖不成立')
            return '\n'.join(lines)
        lines.append('')
        lines.append('【第三步】小级别验证')
        lines.append('-' * 40)
        lines.append('30分钟级别上涨背驰确认' if result.lower_tf_divergence else '30分钟级别未确认上涨背驰')
        lines.append('')
        lines.append('【辅助验证】')
        lines.append('-' * 40)
        lines.append(f'反弹缩量：{"是" if result.volume_shrinking else "否"}')
        lines.append(f'均线压力：{"是" if result.ma_resistance else "否"}')
        lines.append(f'力度减弱：{"是" if result.momentum_weakening else "否"}')
        lines.append('')
        lines.append('【综合判定】')
        lines.append('-' * 40)
        for detail in result.details:
            lines.append(f'  {detail}')
        lines.append('')
        if result.second_sell_confirmed:
            lines.append('【交易执行】')
            lines.append('-' * 40)
            lines.append(f'建议入场价：{result.suggested_entry}')
            lines.append(f'止损（一卖高点上方）：{result.stop_loss:.4f}')
            lines.append('目标位：')
            for i, t in enumerate(result.targets):
                lines.append(f'  目标{i + 1}：{t:.4f}')
            pct = result.position_advice
            lines.append(f'仓位建议：首仓{pct.get("first_entry", 0.35) * 100:.0f}% | 加仓{pct.get("add_position", 0.35) * 100:.0f}%')
        lines.append('')
        lines.append('=' * 60)
        return '\n'.join(lines)

    def analyze_similar_second_buy(self, df_4h, df_30m, first_buy_result):
        result = SimilarSecondBuyAnalysisResult(
            uptrend_established=False, rising_zhongshu_count=0,
            df_4h=df_4h, df_30m=df_30m, timestamp=datetime.now().isoformat(),
        )
        if not first_buy_result.divergence_confirmed:
            result.details.append('\u524d\u63d0\u4e0d\u6ee1\u8db3\uff1a\u4e00\u4e70\u672a\u786e\u8ba4\uff0c\u65e0\u6cd5\u8fdb\u884c\u7c7b\u4e8c\u4e70\u5206\u6790')
            return result
        result.uptrend_established = True
        buy_idx, buy_low = self._sb_find_first_buy_point(df_4h, first_buy_result)
        result.details.append(f'\u4e00\u4e70\u5b9a\u4f4d\uff1a\u7d22\u5f15{buy_idx}\uff0c\u6700\u4f4e\u4ef7{buy_low:.4f}')
        zhongshu_list = self._csb_find_rising_zhongshu(df_4h, buy_idx)
        result.rising_zhongshu_count = len(zhongshu_list)
        result.details.append(f'\u4e0a\u6da8\u4e2d\u67a2\u6570\u91cf\uff1a{len(zhongshu_list)}')
        if len(zhongshu_list) < 2:
            result.details.append('\u7ed3\u6784\u4e0d\u6ee1\u8db3\uff1a\u9700\u8981\u81f3\u5c112\u4e2a\u4e0a\u6da8\u4e2d\u67a2\uff0c\u5f53\u524d\u4ec5{len(zhongshu_list)}\u4e2a')
            return result
        prev_zs = zhongshu_list[-2]
        result.previous_zhongshu = prev_zs
        result.previous_zhongshu_upper = prev_zs.upper
        result.details.append(f'\u524d\u4e2d\u67a2\uff1a[{prev_zs.lower:.4f}, {prev_zs.upper:.4f}]')
        has_structure, new_zs, pullback_idx, pullback_low = self._csb_check_breakout_structure(df_4h, prev_zs, zhongshu_list)
        result.has_breakout_pullback = has_structure
        result.new_zhongshu = new_zs
        result.pullback_low_idx = pullback_idx
        result.pullback_low = pullback_low
        if not has_structure:
            result.details.append('\u7ed3\u6784\u4e0d\u6ee1\u8db3\uff1a\u672a\u51fa\u73b0\u6e05\u6670\u7684\u4e2d\u67a2\u7a81\u7834+\u56de\u8c03\u7ed3\u6784')
            return result
        if pullback_low > prev_zs.upper:
            result.core_condition_met = True
            result.details.append(f'\u6838\u5fc3\u6761\u4ef6\u6ee1\u8db3\uff1a\u56de\u8c03\u4f4e\u70b9{pullback_low:.4f} > \u524d\u4e2d\u67a2\u4e0a\u6cbf{prev_zs.upper:.4f}')
        else:
            result.core_condition_met = False
            result.details.append(f'\u6838\u5fc3\u6761\u4ef6\u4e0d\u6ee1\u8db3\uff1a\u56de\u8c03\u4f4e\u70b9{pullback_low:.4f} <= \u524d\u4e2d\u67a2\u4e0a\u6cbf{prev_zs.upper:.4f}\uff0c\u7c7b\u4e8c\u4e70\u4e0d\u6210\u7acb')
            return result
        result.strength_class = self._csb_classify_strength(pullback_low, prev_zs, new_zs)
        result.details.append(f'\u5f3a\u5ea6\u5206\u7ea7\uff1a{result.strength_class}\u7c7b\u4e8c\u4e70')
        result.lower_tf_divergence = self._csb_check_lower_tf_divergence(df_30m, prev_zs.upper)
        if result.lower_tf_divergence:
            result.details.append('30M\u5c0f\u7ea7\u522b\uff1a\u786e\u8ba4\u4e0b\u8dcc\u80cc\u9a70\u7ed3\u6784')
        else:
            result.details.append('30M\u5c0f\u7ea7\u522b\uff1a\u672a\u786e\u8ba4\u4e0b\u8dcc\u80cc\u9a70')
        vol, ma_sup, mom = self._csb_auxiliary_verification(df_4h, prev_zs.end_idx)
        result.volume_shrinking = vol
        result.ma_support = ma_sup
        result.momentum_weakening = mom
        aux_signals = []
        if vol: aux_signals.append('\u56de\u8c03\u7f29\u91cf')
        if ma_sup: aux_signals.append('\u5747\u7ebf\u652f\u6491')
        if mom: aux_signals.append('\u529b\u5ea6\u51cf\u5f31')
        if aux_signals:
            result.details.append(f'\u8f85\u52a9\u9a8c\u8bc1\uff1a{", ".join(aux_signals)}')
        aux_count = sum([vol, ma_sup, mom])
        if result.core_condition_met and result.lower_tf_divergence and aux_count >= 2:
            result.similar_second_buy_confirmed = True
            result.details.append('>> \u7c7b\u4e8c\u4e70\u7efc\u5408\u786e\u8ba4\u6210\u7acb')
        elif result.core_condition_met and result.lower_tf_divergence:
            result.similar_second_buy_confirmed = True
            result.details.append('>> \u7c7b\u4e8c\u4e70\u7efc\u5408\u786e\u8ba4\u6210\u7acb\uff08\u6838\u5fc3\u6761\u4ef6+\u5c0f\u7ea7\u522b\u80cc\u9a70\u6ee1\u8db3\uff09')
        else:
            result.similar_second_buy_confirmed = False
            result.details.append('>> \u7c7b\u4e8c\u4e70\u6761\u4ef6\u4e0d\u5b8c\u5168\u6ee1\u8db3\uff0c\u5efa\u8bae\u7b49\u5f85')
        if result.similar_second_buy_confirmed:
            decision = self._csb_trading_decision(result, df_4h)
            result.suggested_entry = decision.get('suggested_entry', 0.0)
            result.stop_loss = decision.get('stop_loss', 0.0)
            result.targets = decision.get('targets', [])
            result.position_advice = decision.get('position_advice', {})
        return result

    def _csb_find_rising_zhongshu(self, df, first_buy_idx):
        if first_buy_idx < 0 or first_buy_idx >= len(df) - 10:
            return []
        post_buy_df = df.iloc[first_buy_idx:].reset_index(drop=True)
        if len(post_buy_df) < 10:
            return []
        fractals = self._find_fractals(post_buy_df, hg1=3)
        pens = self._build_pens(fractals)
        if len(pens) < 3:
            return []
        zhongshu_list = self._identify_zhongshu(pens, direction='up')
        for zs in zhongshu_list:
            zs.start_idx += first_buy_idx
            zs.end_idx += first_buy_idx
        return zhongshu_list

    def _csb_check_breakout_structure(self, df, prev_zhongshu, zhongshu_list):
        prev_end = prev_zhongshu.end_idx
        if prev_end >= len(df) - 3:
            return False, None, -1, 0.0
        post_break_df = df.iloc[prev_end:]
        breakout_found = False
        for i in range(len(post_break_df)):
            if post_break_df['high'].iloc[i] > prev_zhongshu.upper:
                breakout_found = True
                break
        if not breakout_found:
            return False, None, -1, 0.0
        new_zs = zhongshu_list[-1] if len(zhongshu_list) > 1 else None
        if new_zs is not None:
            new_start = new_zs.start_idx
            if new_start >= len(df):
                new_start = len(df) - 1
            pullback_segment = df.iloc[new_start:]
            if len(pullback_segment) >= 5:
                fractals = self._find_fractals(pullback_segment, hg1=3)
                pens = self._build_pens(fractals)
                down_pens = [p for p in pens if p.direction == 'down']
                pullback_low = float('inf')
                pullback_idx = -1
                for p in down_pens:
                    if p.low < pullback_low:
                        pullback_low = p.low
                        pullback_idx = p.end_fractal.idx + new_start
                if pullback_idx > -1:
                    return True, new_zs, pullback_idx, pullback_low
                pullback_low = pullback_segment['low'].min()
                pullback_idx = int(pullback_segment['low'].values.argmin()) + new_start
                return True, new_zs, pullback_idx, pullback_low
            return True, new_zs, len(df) - 1, df['low'].iloc[-1]
        return False, None, -1, 0.0

    def _csb_classify_strength(self, pullback_low, prev_zhongshu, new_zhongshu):
        upper = prev_zhongshu.upper
        if pullback_low >= upper * 1.02:
            return 'strong'
        elif pullback_low > upper:
            return 'standard'
        else:
            return 'weak'

    def _csb_check_lower_tf_divergence(self, df_30m, ref_upper):
        if df_30m.empty or len(df_30m) < 30:
            return False
        extremes = find_price_extremes(df_30m, window=5)
        lows_30m = extremes.get('lows', [])
        if len(lows_30m) < 2:
            return False
        close_30m = df_30m['close']
        recent_lows = [idx for idx in lows_30m if idx > len(df_30m) * 0.5]
        if len(recent_lows) < 2:
            recent_lows = lows_30m[-4:] if len(lows_30m) >= 4 else lows_30m
        if len(recent_lows) < 2:
            return False
        last_low_idx = recent_lows[-1]
        prev_low_idx = recent_lows[-2]
        if last_low_idx >= len(close_30m) or prev_low_idx >= len(close_30m):
            return False
        last_price = df_30m['low'].iloc[last_low_idx]
        prev_price = df_30m['low'].iloc[prev_low_idx]
        if last_price >= prev_price:
            return False
        if last_price < ref_upper * 0.9:
            return False
        if prev_low_idx < last_low_idx:
            seg1 = close_30m.iloc[prev_low_idx:last_low_idx]
            if len(seg1) >= 5:
                slope = calculate_price_slope(seg1)
                if slope < 0 and abs(slope) < 2.0:
                    return True
        if 'volume' in df_30m.columns:
            last_vol = df_30m['volume'].iloc[last_low_idx]
            prev_vol = df_30m['volume'].iloc[prev_low_idx]
            if prev_vol > 0 and last_vol / prev_vol < self.volume_shrink_threshold:
                return True
        return False

    def _csb_auxiliary_verification(self, df, prev_zhongshu_end_idx):
        volume_shrinking = False
        ma_support = False
        momentum_weakening = False
        if prev_zhongshu_end_idx < 0 or prev_zhongshu_end_idx >= len(df) - 10:
            return volume_shrinking, ma_support, momentum_weakening
        post_break = df.iloc[prev_zhongshu_end_idx:]
        if 'volume' in df.columns and len(post_break) >= 8:
            half = len(post_break) // 2
            first_half_vol = post_break['volume'].iloc[:half].mean()
            second_half_vol = post_break['volume'].iloc[half:].mean()
            if first_half_vol > 0 and second_half_vol < first_half_vol:
                volume_shrinking = True
        close = df['close']
        if len(close) >= 30:
            ma20 = calculate_ma(close, 20)
            ma60 = calculate_ma(close, 60)
            if not pd.isna(ma20.iloc[-1]) and not pd.isna(ma60.iloc[-1]):
                current_low = df['low'].iloc[-1]
                if current_low > ma20.iloc[-1] * 0.98 or current_low > ma60.iloc[-1] * 0.98:
                    ma_support = True
        if len(post_break) >= 8:
            fractals = self._find_fractals(post_break, hg1=3)
            pens = self._build_pens(fractals)
            up_pen = next((p for p in pens if p.direction == 'up'), None)
            down_pen = next((p for p in pens if p.direction == 'down'), None)
            if up_pen is not None and down_pen is not None:
                up_range = up_pen.high - up_pen.low
                down_range = down_pen.high - down_pen.low
                if up_range > 0 and down_range < up_range * 0.8:
                    momentum_weakening = True
        return volume_shrinking, ma_support, momentum_weakening

    def _csb_trading_decision(self, result, df):
        decision = {
            'suggested_entry': 0.0, 'stop_loss': 0.0, 'targets': [],
            'position_advice': {'first_entry': 0.25, 'add_position': 0.25, 'max_total': 0.50, 'note': '\u7c7b\u4e8c\u4e70\u4e3a\u52a0\u4ed3\u4fe1\u53f7'},
        }
        latest_close = df['close'].iloc[-1]
        decision['suggested_entry'] = round(latest_close, 4)
        decision['stop_loss'] = round(result.previous_zhongshu_upper * 0.98, 4)
        if result.new_zhongshu is not None:
            zs = result.new_zhongshu
            targets = [round(zs.upper, 4)]
            if result.previous_zhongshu is not None:
                prev_range = result.previous_zhongshu.upper - result.previous_zhongshu.lower
                if prev_range > 0:
                    targets.append(round(latest_close + prev_range, 4))
                    targets.append(round(latest_close + prev_range * 1.618, 4))
            if result.df_4h is not None and len(result.df_4h) > 0:
                trend_high = result.df_4h['high'].max()
                targets.append(round(trend_high, 4))
            targets = sorted(set(targets))
            decision['targets'] = targets
        else:
            decision['targets'] = [round(latest_close * 1.03, 4), round(latest_close * 1.05, 4)]
        return decision

    def generate_similar_second_buy_report(self, result):
        lines = []
        lines.append('=' * 60)
        lines.append('  \u7f20\u8bba\u7c7b\u7b2c\u4e8c\u7c7b\u4e70\u70b9\uff08\u7c7b\u4e8c\u4e70\uff09\u5206\u6790\u62a5\u544a')
        lines.append('=' * 60)
        lines.append(f'\u5206\u6790\u65f6\u95f4\uff1a{result.timestamp}')
        lines.append('')
        lines.append('\u3010\u524d\u63d0\u68c0\u67e5\u3011\u4e0a\u5347\u8d8b\u52bf\u72b6\u6001')
        lines.append('-' * 40)
        if not result.uptrend_established:
            lines.append('\u4e00\u4e70\u672a\u786e\u8ba4\uff0c\u7ec8\u6b62\u7c7b\u4e8c\u4e70\u5206\u6790\u3002')
            return '\n'.join(lines)
        lines.append('\u4e00\u4e70\u5df2\u786e\u8ba4\uff0c\u4e0a\u5347\u8d8b\u52bf\u786e\u7acb')
        lines.append(f'\u4e0a\u6da8\u4e2d\u67a2\u6570\u91cf\uff1a{result.rising_zhongshu_count}')
        if result.rising_zhongshu_count < 2:
            lines.append(f'\u9700\u8981\u81f3\u5c112\u4e2a\u4e0a\u6da8\u4e2d\u67a2\uff0c\u5f53\u524d\u4ec5{result.rising_zhongshu_count}\u4e2a\uff0c\u7c7b\u4e8c\u4e70\u4e0d\u6210\u7acb\u3002')
            return '\n'.join(lines)
        lines.append('')
        lines.append('\u3010\u7b2c\u4e00\u6b65\u3011\u4e2d\u67a2\u5b9a\u4f4d \u2014 \u524d\u4e2d\u67a2\u88ab\u7a81\u7834+\u65b0\u4e2d\u67a2\u6784\u5efa')
        lines.append('-' * 40)
        if result.previous_zhongshu is not None:
            pzs = result.previous_zhongshu
            lines.append(f'\u524d\u4e2d\u67a2\uff1a[{pzs.lower:.4f}, {pzs.upper:.4f}] \u7d22\u5f15[{pzs.start_idx}, {pzs.end_idx}]')
        if not result.has_breakout_pullback:
            lines.append('\u672a\u51fa\u73b0\u6e05\u6670\u7684\u4e2d\u67a2\u7a81\u7834+\u56de\u8c03\u7ed3\u6784\uff0c\u7c7b\u4e8c\u4e70\u4e0d\u6210\u7acb\u3002')
            return '\n'.join(lines)
        lines.append('\u4e2d\u67a2\u7a81\u7834+\u56de\u8c03\u7ed3\u6784\u5df2\u786e\u8ba4')
        if result.new_zhongshu is not None:
            nzs = result.new_zhongshu
            lines.append(f'\u65b0\u4e2d\u67a2\uff1a[{nzs.lower:.4f}, {nzs.upper:.4f}]')
        lines.append('')
        lines.append('\u3010\u7b2c\u4e8c\u6b65\u3011\u6838\u5fc3\u51e0\u4f55\u6761\u4ef6')
        lines.append('-' * 40)
        lines.append(f'\u524d\u4e2d\u67a2\u4e0a\u6cbf\uff1a{result.previous_zhongshu_upper:.4f}')
        lines.append(f'\u56de\u8c03\u6700\u4f4e\u70b9\uff1a{result.pullback_low:.4f}')
        if result.core_condition_met:
            lines.append('\u56de\u8c03\u4f4e\u70b9 > \u524d\u4e2d\u67a2\u4e0a\u6cbf \u2014 \u7c7b\u4e8c\u4e70\u533a\u57df\u786e\u7acb')
            lines.append(f'\u5f3a\u5ea6\u5206\u7ea7\uff1a{result.strength_class}\u7c7b\u4e8c\u4e70')
        else:
            lines.append('\u56de\u8c03\u4f4e\u70b9 <= \u524d\u4e2d\u67a2\u4e0a\u6cbf \u2014 \u7c7b\u4e8c\u4e70\u4e0d\u6210\u7acb')
            return '\n'.join(lines)
        lines.append('')
        lines.append('\u3010\u7b2c\u4e09\u6b65\u3011\u5c0f\u7ea7\u522b\u9a8c\u8bc1')
        lines.append('-' * 40)
        lines.append('30\u5206\u949f\u7ea7\u522b\u4e0b\u8dcc\u80cc\u9a70\u786e\u8ba4' if result.lower_tf_divergence else '30\u5206\u949f\u7ea7\u522b\u672a\u786e\u8ba4\u4e0b\u8dcc\u80cc\u9a70')
        lines.append('')
        lines.append('\u3010\u8f85\u52a9\u9a8c\u8bc1\u3011')
        lines.append('-' * 40)
        lines.append(f'回调缩量：{"是" if result.volume_shrinking else "否"}')
        lines.append(f'均线支撑：{"是" if result.ma_support else "否"}')
        lines.append(f'力度减弱：{"是" if result.momentum_weakening else "否"}')
        lines.append('')
        lines.append('\u3010\u7efc\u5408\u5224\u5b9a\u3011')
        lines.append('-' * 40)
        for detail in result.details:
            lines.append(f'  {detail}')
        lines.append('')
        if result.similar_second_buy_confirmed:
            lines.append('\u3010\u4ea4\u6613\u6267\u884c\u3011')
            lines.append('-' * 40)
            lines.append(f'\u5efa\u8bae\u5165\u573a\u4ef7\uff1a{result.suggested_entry}')
            lines.append(f'\u6b62\u635f\uff08\u524d\u4e2d\u67a2\u4e0a\u6cbf\u4e0b\u65b9\uff09\uff1a{result.stop_loss:.4f}')
            lines.append('\u76ee\u6807\u4f4d\uff1a')
            for i, t in enumerate(result.targets):
                lines.append(f'  \u76ee\u6807{i + 1}\uff1a{t:.4f}')
            pct = result.position_advice
            note = pct.get('note', '')
            lines.append(f'\u4ed3\u4f4d\u5efa\u8bae\uff1a\u52a0\u4ed3{pct.get("first_entry", 0.25) * 100:.0f}% | \u8ffd\u52a0{pct.get("add_position", 0.25) * 100:.0f}% (\u5df2\u6709\u5e95\u4ed3)')
        lines.append('')
        lines.append('=' * 60)
        return '\n'.join(lines)


    def analyze_similar_second_sell(self, df_4h, df_30m, first_sell_result):
        result = SimilarSecondSellAnalysisResult(
            downtrend_established=False, falling_zhongshu_count=0,
            df_4h=df_4h, df_30m=df_30m, timestamp=datetime.now().isoformat(),
        )
        if not first_sell_result.divergence_confirmed:
            result.details.append('前提不满足：一卖未确认，无法进行类二卖分析')
            return result
        result.downtrend_established = True
        sell_idx, sell_high = self._ss_find_first_sell_point(df_4h, first_sell_result)
        result.details.append(f'一卖定位：索引{sell_idx}，最高价{sell_high:.4f}')
        zhongshu_list = self._css_find_falling_zhongshu(df_4h, sell_idx)
        result.falling_zhongshu_count = len(zhongshu_list)
        result.details.append(f'下跌中枢数量：{len(zhongshu_list)}')
        if len(zhongshu_list) < 2:
            result.details.append(f'结构不满足：需要至少2个下跌中枢，当前仅{len(zhongshu_list)}个')
            return result
        prev_zs = zhongshu_list[-2]
        result.previous_zhongshu = prev_zs
        result.previous_zhongshu_lower = prev_zs.lower
        result.details.append(f'前中枢：[{prev_zs.lower:.4f}, {prev_zs.upper:.4f}]')
        has_structure, new_zs, bounce_idx, bounce_high = self._css_check_breakdown_structure(df_4h, prev_zs, zhongshu_list)
        result.has_breakdown_bounce = has_structure
        result.new_zhongshu = new_zs
        result.bounce_high_idx = bounce_idx
        result.bounce_high = bounce_high
        if not has_structure:
            result.details.append('结构不满足：未出现清晰的中枢跌破+反弹结构')
            return result
        if bounce_high < prev_zs.lower:
            result.core_condition_met = True
            result.details.append(f'核心条件满足：反弹高点{bounce_high:.4f} < 前中枢下沿{prev_zs.lower:.4f}')
        else:
            result.core_condition_met = False
            result.details.append(f'核心条件不满足：反弹高点{bounce_high:.4f} >= 前中枢下沿{prev_zs.lower:.4f}，类二卖不成立')
            return result
        result.strength_class = self._css_classify_strength(bounce_high, prev_zs, new_zs)
        result.details.append(f'强度分级：{result.strength_class}类二卖')
        result.lower_tf_divergence = self._css_check_lower_tf_divergence(df_30m, prev_zs.lower)
        if result.lower_tf_divergence:
            result.details.append('30M小级别：确认上涨背驰结构')
        else:
            result.details.append('30M小级别：未确认上涨背驰')
        vol, ma_res, mom = self._css_auxiliary_verification(df_4h, prev_zs.end_idx)
        result.volume_shrinking = vol
        result.ma_resistance = ma_res
        result.momentum_weakening = mom
        aux_signals = []
        if vol: aux_signals.append('反弹缩量')
        if ma_res: aux_signals.append('均线压力')
        if mom: aux_signals.append('力度减弱')
        if aux_signals:
            result.details.append(f'辅助验证：{", ".join(aux_signals)}')
        aux_count = sum([vol, ma_res, mom])
        if result.core_condition_met and result.lower_tf_divergence and aux_count >= 2:
            result.similar_second_sell_confirmed = True
            result.details.append('>> 类二卖综合确认成立')
        elif result.core_condition_met and result.lower_tf_divergence:
            result.similar_second_sell_confirmed = True
            result.details.append('>> 类二卖综合确认成立（核心条件+小级别背驰满足）')
        else:
            result.similar_second_sell_confirmed = False
            result.details.append('>> 类二卖条件不完全满足，建议等待')
        if result.similar_second_sell_confirmed:
            decision = self._css_trading_decision(result, df_4h)
            result.suggested_entry = decision.get('suggested_entry', 0.0)
            result.stop_loss = decision.get('stop_loss', 0.0)
            result.targets = decision.get('targets', [])
            result.position_advice = decision.get('position_advice', {})
        return result

    def _css_find_falling_zhongshu(self, df, first_sell_idx):
        if first_sell_idx < 0 or first_sell_idx >= len(df) - 10:
            return []
        post_sell_df = df.iloc[first_sell_idx:].reset_index(drop=True)
        if len(post_sell_df) < 10:
            return []
        fractals = self._find_fractals(post_sell_df, hg1=3)
        pens = self._build_pens(fractals)
        if len(pens) < 3:
            return []
        zhongshu_list = self._identify_zhongshu(pens, direction='down')
        for zs in zhongshu_list:
            zs.start_idx += first_sell_idx
            zs.end_idx += first_sell_idx
        return zhongshu_list

    def _css_check_breakdown_structure(self, df, prev_zhongshu, zhongshu_list):
        prev_end = prev_zhongshu.end_idx
        if prev_end >= len(df) - 3:
            return False, None, -1, 0.0
        post_break_df = df.iloc[prev_end:]
        breakdown_found = False
        for i in range(len(post_break_df)):
            if post_break_df['low'].iloc[i] < prev_zhongshu.lower:
                breakdown_found = True
                break
        if not breakdown_found:
            return False, None, -1, 0.0
        new_zs = zhongshu_list[-1] if len(zhongshu_list) > 1 else None
        if new_zs is not None:
            new_start = new_zs.start_idx
            if new_start >= len(df):
                new_start = len(df) - 1
            bounce_segment = df.iloc[new_start:]
            if len(bounce_segment) >= 5:
                fractals = self._find_fractals(bounce_segment, hg1=3)
                pens = self._build_pens(fractals)
                up_pens = [p for p in pens if p.direction == 'up']
                bounce_high = float('-inf')
                bounce_idx = -1
                for p in up_pens:
                    if p.high > bounce_high:
                        bounce_high = p.high
                        bounce_idx = p.end_fractal.idx + new_start
                if bounce_idx > -1:
                    return True, new_zs, bounce_idx, bounce_high
                bounce_high = bounce_segment['high'].max()
                bounce_idx = int(bounce_segment['high'].values.argmax()) + new_start
                return True, new_zs, bounce_idx, bounce_high
            return True, new_zs, len(df) - 1, df['high'].iloc[-1]
        return False, None, -1, 0.0

    def _css_classify_strength(self, bounce_high, prev_zhongshu, new_zhongshu):
        lower = prev_zhongshu.lower
        if bounce_high <= lower * 0.98:
            return 'strong'
        elif bounce_high < lower:
            return 'standard'
        else:
            return 'weak'

    def _css_check_lower_tf_divergence(self, df_30m, ref_lower):
        if df_30m.empty or len(df_30m) < 30:
            return False
        extremes = find_price_extremes(df_30m, window=5)
        highs_30m = extremes.get('highs', [])
        if len(highs_30m) < 2:
            return False
        close_30m = df_30m['close']
        recent_highs = [idx for idx in highs_30m if idx > len(df_30m) * 0.5]
        if len(recent_highs) < 2:
            recent_highs = highs_30m[-4:] if len(highs_30m) >= 4 else highs_30m
        if len(recent_highs) < 2:
            return False
        last_high_idx = recent_highs[-1]
        prev_high_idx = recent_highs[-2]
        if last_high_idx >= len(close_30m) or prev_high_idx >= len(close_30m):
            return False
        last_price = df_30m['high'].iloc[last_high_idx]
        prev_price = df_30m['high'].iloc[prev_high_idx]
        if last_price <= prev_price:
            return False
        if last_price > ref_lower * 1.1:
            return False
        if prev_high_idx < last_high_idx:
            seg1 = close_30m.iloc[prev_high_idx:last_high_idx]
            if len(seg1) >= 5:
                slope = calculate_price_slope(seg1)
                if slope > 0 and slope < 2.0:
                    return True
        if 'volume' in df_30m.columns:
            last_vol = df_30m['volume'].iloc[last_high_idx]
            prev_vol = df_30m['volume'].iloc[prev_high_idx]
            if prev_vol > 0 and last_vol / prev_vol < self.volume_shrink_threshold:
                return True
        return False

    def _css_auxiliary_verification(self, df, prev_zhongshu_end_idx):
        volume_shrinking = False
        ma_resistance = False
        momentum_weakening = False
        if prev_zhongshu_end_idx < 0 or prev_zhongshu_end_idx >= len(df) - 10:
            return volume_shrinking, ma_resistance, momentum_weakening
        post_break = df.iloc[prev_zhongshu_end_idx:]
        if 'volume' in df.columns and len(post_break) >= 8:
            half = len(post_break) // 2
            first_half_vol = post_break['volume'].iloc[:half].mean()
            second_half_vol = post_break['volume'].iloc[half:].mean()
            if first_half_vol > 0 and second_half_vol < first_half_vol:
                volume_shrinking = True
        close = df['close']
        if len(close) >= 30:
            ma20 = calculate_ma(close, 20)
            ma60 = calculate_ma(close, 60)
            if not pd.isna(ma20.iloc[-1]) and not pd.isna(ma60.iloc[-1]):
                current_high = df['high'].iloc[-1]
                if current_high < ma20.iloc[-1] * 1.02 or current_high < ma60.iloc[-1] * 1.02:
                    ma_resistance = True
        if len(post_break) >= 8:
            fractals = self._find_fractals(post_break, hg1=3)
            pens = self._build_pens(fractals)
            down_pen = next((p for p in pens if p.direction == 'down'), None)
            up_pen = next((p for p in pens if p.direction == 'up'), None)
            if down_pen is not None and up_pen is not None:
                down_range = down_pen.high - down_pen.low
                up_range = up_pen.high - up_pen.low
                if down_range > 0 and up_range < down_range * 0.8:
                    momentum_weakening = True
        return volume_shrinking, ma_resistance, momentum_weakening

    def _css_trading_decision(self, result, df):
        decision = {
            'suggested_entry': 0.0, 'stop_loss': 0.0, 'targets': [],
            'position_advice': {'first_entry': 0.25, 'add_position': 0.25, 'max_total': 0.50, 'note': '类二卖为加仓信号'},
        }
        latest_close = df['close'].iloc[-1]
        decision['suggested_entry'] = round(latest_close, 4)
        decision['stop_loss'] = round(result.previous_zhongshu_lower * 1.02, 4)
        if result.new_zhongshu is not None:
            zs = result.new_zhongshu
            targets = [round(zs.lower, 4)]
            if result.previous_zhongshu is not None:
                prev_range = result.previous_zhongshu.upper - result.previous_zhongshu.lower
                if prev_range > 0:
                    targets.append(round(latest_close - prev_range, 4))
                    targets.append(round(latest_close - prev_range * 1.618, 4))
            if result.df_4h is not None and len(result.df_4h) > 0:
                trend_low = result.df_4h['low'].min()
                targets.append(round(trend_low, 4))
            targets = sorted(set(targets), reverse=True)
            decision['targets'] = targets
        else:
            decision['targets'] = [round(latest_close * 0.97, 4), round(latest_close * 0.95, 4)]
        return decision

    def generate_similar_second_sell_report(self, result):
        lines = []
        lines.append('=' * 60)
        lines.append('  缠论类第二类卖点（类二卖）分析报告')
        lines.append('=' * 60)
        lines.append(f'分析时间：{result.timestamp}')
        lines.append('')
        lines.append('【前提检查】下跌趋势状态')
        lines.append('-' * 40)
        if not result.downtrend_established:
            lines.append('一卖未确认，终止类二卖分析。')
            return '\n'.join(lines)
        lines.append('一卖已确认，下跌趋势确立')
        lines.append(f'下跌中枢数量：{result.falling_zhongshu_count}')
        if result.falling_zhongshu_count < 2:
            lines.append(f'需要至少2个下跌中枢，当前仅{result.falling_zhongshu_count}个，类二卖不成立。')
            return '\n'.join(lines)
        lines.append('')
        lines.append('【第一步】中枢定位 — 前中枢被跌破+新中枢构建')
        lines.append('-' * 40)
        if result.previous_zhongshu is not None:
            pzs = result.previous_zhongshu
            lines.append(f'前中枢：[{pzs.lower:.4f}, {pzs.upper:.4f}] 索引[{pzs.start_idx}, {pzs.end_idx}]')
        if not result.has_breakdown_bounce:
            lines.append('未出现清晰的中枢跌破+反弹结构，类二卖不成立。')
            return '\n'.join(lines)
        lines.append('中枢跌破+反弹结构已确认')
        if result.new_zhongshu is not None:
            nzs = result.new_zhongshu
            lines.append(f'新中枢：[{nzs.lower:.4f}, {nzs.upper:.4f}]')
        lines.append('')
        lines.append('【第二步】核心几何条件')
        lines.append('-' * 40)
        lines.append(f'前中枢下沿：{result.previous_zhongshu_lower:.4f}')
        lines.append(f'反弹最高点：{result.bounce_high:.4f}')
        if result.core_condition_met:
            lines.append('反弹高点 < 前中枢下沿 — 类二卖区域确立')
            lines.append(f'强度分级：{result.strength_class}类二卖')
        else:
            lines.append('反弹高点 >= 前中枢下沿 — 类二卖不成立')
            return '\n'.join(lines)
        lines.append('')
        lines.append('【第三步】小级别验证')
        lines.append('-' * 40)
        yes_str = '是'
        no_str = '否'
        lines.append('30分钟级别上涨背驰确认' if result.lower_tf_divergence else '30分钟级别未确认上涨背驰')
        lines.append('')
        lines.append('【辅助验证】')
        lines.append('-' * 40)
        lines.append(f'反弹缩量：{yes_str if result.volume_shrinking else no_str}')
        lines.append(f'均线压力：{yes_str if result.ma_resistance else no_str}')
        lines.append(f'力度减弱：{yes_str if result.momentum_weakening else no_str}')
        lines.append('')
        lines.append('【综合判定】')
        lines.append('-' * 40)
        for detail in result.details:
            lines.append(f'  {detail}')
        lines.append('')
        if result.similar_second_sell_confirmed:
            lines.append('【交易执行】')
            lines.append('-' * 40)
            lines.append(f'建议入场价：{result.suggested_entry}')
            lines.append(f'止损（前中枢下沿上方）：{result.stop_loss:.4f}')
            lines.append('目标位：')
            for i, t in enumerate(result.targets):
                lines.append(f'  目标{i + 1}：{t:.4f}')
            pct = result.position_advice
            lines.append(f'仓位建议：加仓{pct.get("first_entry", 0.25) * 100:.0f}% | 追加{pct.get("add_position", 0.25) * 100:.0f}% (已有空头仓位)')
        lines.append('')
        lines.append('=' * 60)
        return '\n'.join(lines)



class ChanFirstBuyStrategy(BaseStrategy):

    def __init__(
        self,
        symbol: str = 'ETHUSDC',
        time_frame: str = '4h',
        deviation_ratio_threshold: float = 0.8,
        volume_shrink_threshold: float = 0.7,
        slope_flatten_threshold: float = 0.3,
        min_zhongshu_for_buy: int = 2,
        min_dimensions_for_divergence: int = 2,
    ):
        super().__init__('ChanFirstBuyStrategy')
        self.symbol = symbol
        self.time_frame = time_frame

        self.analyzer = ChanTheoryFirstBuyAnalyzer(
            deviation_ratio_threshold=deviation_ratio_threshold,
            volume_shrink_threshold=volume_shrink_threshold,
            slope_flatten_threshold=slope_flatten_threshold,
            min_zhongshu_for_buy=min_zhongshu_for_buy,
            min_dimensions_for_divergence=min_dimensions_for_divergence,
        )

        self.df_4h: pd.DataFrame = pd.DataFrame()
        self.df_30m: pd.DataFrame = pd.DataFrame()
        self.latest_result: Optional[FirstBuyAnalysisResult] = None
        self.latest_sell_result: Optional[FirstSellAnalysisResult] = None
        self.use_binance_client = True

    async def initialize(self, symbol: str) -> bool:
        self.symbol = symbol
        logger.info(f'[{self.name}] 初始化完成，品种={symbol}，周期={self.time_frame}')
        return True

    async def on_bar(self, bar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None

    async def fetch_data(self):
        if self.use_binance_client:
            client = BinanceRestClient()
            try:
                logger.info(f'获取{self.time_frame} K线数据...')
                klines_4h = await client.get_continuous_klines(
                    pair=self.symbol,
                    contractType='PERPETUAL',
                    interval=self.time_frame,
                    limit=500,
                )
                if isinstance(klines_4h, list) and klines_4h:
                    self.df_4h = binance_klines_to_dataframe(klines_4h)
                    logger.info(f'获取到 {len(self.df_4h)} 条{self.time_frame}K线数据')

                logger.info('获取30分钟K线数据...')
                klines_30m = await client.get_continuous_klines(
                    pair=self.symbol,
                    contractType='PERPETUAL',
                    interval='30m',
                    limit=500,
                )
                if isinstance(klines_30m, list) and klines_30m:
                    self.df_30m = binance_klines_to_dataframe(klines_30m)
                    logger.info(f'获取到 {len(self.df_30m)} 条30M K线数据')
            finally:
                await client.close()

    def run_analysis(self) -> FirstBuyAnalysisResult:
        result = self.analyzer.analyze(self.df_4h, self.df_30m)
        self.latest_result = result
        return result

    def get_signal(self) -> Optional[Dict[str, Any]]:
        if self.latest_result is None:
            return None

        if not self.latest_result.divergence_confirmed:
            return {'action': 'HOLD', 'reason': '背驰不成立'}

        if not self.latest_result.entry_conditions_met:
            return {'action': 'HOLD', 'reason': '等待底分型确认'}

        return {
            'action': 'BUY',
            'entry_price': self.latest_result.suggested_entry_price,
            'stop_loss': self.latest_result.stop_loss_price,
            'targets': self.latest_result.targets,
            'position_advice': self.latest_result.position_advice,
        }

    async def on_order_update(self, order_data: Dict[str, Any]) -> None:
        logger.info(f'[{self.name}] 订单更新: {order_data}')

    def run_sell_analysis(self) -> FirstSellAnalysisResult:
        result = self.analyzer.analyze_sell(self.df_4h, self.df_30m)
        self.latest_sell_result = result
        return result

    def get_sell_signal(self) -> Optional[Dict[str, Any]]:
        if self.latest_sell_result is None:
            return None

        if not self.latest_sell_result.divergence_confirmed:
            return {'action': 'HOLD', 'reason': '顶背驰不成立'}

        if not self.latest_sell_result.entry_conditions_met:
            return {'action': 'HOLD', 'reason': '等待顶分型确认'}

        return {
            'action': 'SELL',
            'entry_price': self.latest_sell_result.suggested_entry_price,
            'stop_loss': self.latest_sell_result.stop_loss_price,
            'targets': self.latest_sell_result.targets,
            'position_advice': self.latest_sell_result.position_advice,
        }

    def run_second_buy_analysis(self) -> SecondBuyAnalysisResult:
        if self.latest_result is None or not self.latest_result.divergence_confirmed:
            self.run_analysis()
        result = self.analyzer.analyze_second_buy(self.df_4h, self.df_30m, self.latest_result)
        return result

    def get_second_buy_signal(self) -> Optional[Dict[str, Any]]:
        result = self.run_second_buy_analysis()
        if not result.second_buy_confirmed:
            return {'action': 'HOLD', 'reason': '二买条件不满足'}
        return {
            'action': 'BUY',
            'entry_price': result.suggested_entry,
            'stop_loss': result.stop_loss,
            'targets': result.targets,
            'position_advice': result.position_advice,
        }

    def run_second_sell_analysis(self) -> SecondSellAnalysisResult:
        if self.latest_sell_result is None or not self.latest_sell_result.divergence_confirmed:
            self.run_sell_analysis()
        result = self.analyzer.analyze_second_sell(self.df_4h, self.df_30m, self.latest_sell_result)
        return result

    def get_second_sell_signal(self) -> Optional[Dict[str, Any]]:
        result = self.run_second_sell_analysis()
        if not result.second_sell_confirmed:
            return {'action': 'HOLD', 'reason': '二卖条件不满足'}
        return {
            'action': 'SELL',
            'entry_price': result.suggested_entry,
            'stop_loss': result.stop_loss,
            'targets': result.targets,
            'position_advice': result.position_advice,
        }


    def run_similar_second_buy_analysis(self) -> SimilarSecondBuyAnalysisResult:
        if self.latest_result is None or not self.latest_result.divergence_confirmed:
            self.run_analysis()
        result = self.analyzer.analyze_similar_second_buy(
            self.df_4h, self.df_30m, self.latest_result)
        return result

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


    def run_similar_second_sell_analysis(self) -> SimilarSecondSellAnalysisResult:
        if self.latest_sell_result is None or not self.latest_sell_result.divergence_confirmed:
            self.run_sell_analysis()
        result = self.analyzer.analyze_similar_second_sell(
            self.df_4h, self.df_30m, self.latest_sell_result)
        return result

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


async def run_first_buy_analysis(symbol: str = 'ETHUSDC') -> FirstBuyAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return FirstBuyAnalysisResult(
            has_downtrend=False,
            zhongshu_count=0,
            in_final_exit_segment=False,
            trend_details=f'数据获取失败：{symbol} {strategy.time_frame}',
        )

    result = strategy.run_analysis()
    report = strategy.analyzer.generate_report(result)
    print(report)
    return result


async def run_first_sell_analysis(symbol: str = 'ETHUSDC') -> FirstSellAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return FirstSellAnalysisResult(
            has_uptrend=False,
            zhongshu_count=0,
            in_final_breakout_segment=False,
            trend_details=f'数据获取失败：{symbol} {strategy.time_frame}',
        )

    result = strategy.run_sell_analysis()
    report = strategy.analyzer.generate_sell_report(result)
    print(report)
    return result


async def run_second_buy_analysis(symbol: str = 'ETHUSDC') -> SecondBuyAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return SecondBuyAnalysisResult(
            first_buy_confirmed=False, first_buy_low=0.0, first_buy_idx=-1,
            has_rise_pullback=False,
            details=['数据获取失败'],
        )

    strategy.run_analysis()
    result = strategy.run_second_buy_analysis()
    report = strategy.analyzer.generate_second_buy_report(result)
    print(report)
    return result


async def run_second_sell_analysis(symbol: str = 'ETHUSDC') -> SecondSellAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return SecondSellAnalysisResult(
            first_sell_confirmed=False, first_sell_high=0.0, first_sell_idx=-1,
            has_fall_bounce=False,
            details=['数据获取失败'],
        )

    strategy.run_sell_analysis()
    result = strategy.run_second_sell_analysis()
    report = strategy.analyzer.generate_second_sell_report(result)
    print(report)
    return result


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


if __name__ == '__main__':
    result = asyncio.run(run_first_buy_analysis('ETHUSDC'))