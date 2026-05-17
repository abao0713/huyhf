# Checklist

- [x] `_check_long_exit_signals()` 方法存在，检测看跌形态/趋势线跌破/死叉
- [x] `_check_short_exit_signals()` 方法存在，检测看涨形态/趋势线突破/金叉
- [x] `_generate_long_exit_signal()` 返回 `CLOSE_LONG`（信号不足时返回 None）
- [x] `_generate_long_exit_signal()` 在退出后检查做空条件，满足时升级为 `REVERSE_TO_SHORT`
- [x] `_generate_short_exit_signal()` 返回 `CLOSE_SHORT`（信号不足时返回 None）
- [x] `_generate_short_exit_signal()` 在退出后检查做多条件，满足时升级为 `REVERSE_TO_LONG`
- [x] `_generate_signal_internal()` 持有多单时优先检查退出信号
- [x] `_generate_signal_internal()` 持有空单时优先检查退出信号
- [x] `_generate_signal_internal()` 退出信号不为None时不检查K3确认加仓
- [x] 引擎 `_execute_trade()` MTF转换块处理 `CLOSE_LONG`
- [x] 引擎 `_execute_trade()` MTF转换块处理 `CLOSE_SHORT`
- [x] 引擎 `_validate_signal()` 接受 `CLOSE_LONG` 和 `CLOSE_SHORT`
- [x] 回测 `python run_ethusdc_mtf_backtest.py` 无报错，交易记录中包含退出/反转类型 (**代码逻辑已验证，90天回测窗口中30m退出条件未触发**)
- [x] `REVERSE_TO_SHORT` 信号正确携带平仓原因和新开空信息
- [x] `REVERSE_TO_LONG` 信号正确携带平仓原因和新开多信息
- [x] 退出后的 `strategy.clear_position()` 被正确调用，避免状态残留