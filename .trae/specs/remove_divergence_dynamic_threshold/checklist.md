# Checklist: 移除背离信号 + 动态支撑阻力阈值

## 30m做多信号（底背离移除）
- [x] `_check_30m_signals()` 中 divergence 固定为 False，不再调用 `_check_30m_divergence()`
- [x] `_check_30m_divergence()` 方法体保留在文件中
- [x] 日志输出的 signal_details 中 divergence 为 False

## 30m做空信号（顶背离移除）
- [x] `_check_30m_short_signals()` 中 top_divergence 固定为 False，不再调用 `_check_30m_top_divergence()`
- [x] `_check_30m_top_divergence()` 方法体保留在文件中
- [x] 日志输出的 signal_details 中 top_divergence 为 False

## 动态支撑阈值
- [x] `_check_support_zone()` 使用 `min(current_atr * 0.5, current_price * 0.01)` 替代固定 `self.support_threshold`
- [x] `current_atr = 0` 时回退到 `current_price * 0.01`

## 动态阻力阈值
- [x] `_check_resistance_zone()` 使用 `min(current_atr * 0.5, current_price * 0.01)` 替代固定 `self.resistance_threshold`
- [x] `current_atr = 0` 时回退到 `current_price * 0.01`

## 投入金额
- [x] `run_ethusdc_mtf_backtest.py` 中 `INVESTMENT_RATIO = 0.50`
- [x] `MultiTFFractalStrategy.__init__` 中 `investment_ratio` 默认值为 `0.50`

## 回测验证
- [x] 回测交易数 > 0 (实际: 3笔)
- [x] 30m信号日志显示3种信号类型（无 divergence/top_divergence）
- [x] 阈值日志值在合理范围内（≤ 当前价格*1%）
- [x] 仓位使用50%投入比例 (净利润从$85→$1,106，约13倍提升)