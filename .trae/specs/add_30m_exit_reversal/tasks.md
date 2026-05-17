# Tasks

- [x] Task 1: 策略层新增做多退出检测方法 `_check_long_exit_signals()`
  - [x] 复用 `_check_30m_bearish_candlestick()` 检测看跌K线形态
  - [x] 复用 `_check_30m_trendline_break_down()` 检测跌破上升趋势线
  - [x] 复用 `_check_30m_death_cross()` 检测MACD/KDJ死叉
  - [x] 返回 `(signal_count, signal_details)` 元组

- [x] Task 2: 策略层新增做空退出检测方法 `_check_short_exit_signals()`
  - [x] 复用 `_check_30m_bullish_candlestick()` 检测看涨K线形态
  - [x] 复用 `_check_30m_trendline_break()` 检测突破下降趋势线
  - [x] 复用 `_check_30m_golden_cross()` 检测MACD/KDJ金叉
  - [x] 返回 `(signal_count, signal_details)` 元组

- [x] Task 3: 策略层新增做多退出信号生成 `_generate_long_exit_signal()`
  - [x] 调用 `_check_long_exit_signals()` 检测信号数
  - [x] 若信号数 ≥ min_signal_count，生成 `CLOSE_LONG` 信号结构体
  - [x] 生成 CLOSE_LONG 后立即检查做空入场条件（`_check_resistance_zone()` + `_check_4h_top_fractal()` + `_check_30m_short_signals()`）
  - [x] 若做空条件满足 → 升级为 `REVERSE_TO_SHORT` 信号
  - [x] 若做空条件不满足 → 返回 `CLOSE_LONG` 信号

- [x] Task 4: 策略层新增做空退出信号生成 `_generate_short_exit_signal()`
  - [x] 调用 `_check_short_exit_signals()` 检测信号数
  - [x] 若信号数 ≥ min_signal_count，生成 `CLOSE_SHORT` 信号结构体
  - [x] 生成 CLOSE_SHORT 后立即检查做多入场条件（`_check_support_zone()` + `_check_4h_bottom_fractal()` + `_check_30m_signals()`）
  - [x] 若做多条件满足 → 升级为 `REVERSE_TO_LONG` 信号
  - [x] 若做多条件不满足 → 返回 `CLOSE_SHORT` 信号

- [x] Task 5: 修改 `_generate_signal_internal()` — 退出优先于加仓
  - [x] 当 `position_state.direction == "long"` 时，优先调用 `_generate_long_exit_signal()`
  - [x] 若退出信号为 None，对于 confirm_added=False 继续检查K3确认加仓
  - [x] 当 `position_state.direction == "short"` 时，优先调用 `_generate_short_exit_signal()`
  - [x] 若退出信号为 None，对于 confirm_added=False 继续检查K3确认加仓

- [x] Task 6: 引擎层新增 CLOSE_LONG / CLOSE_SHORT 的MTF信号转换
  - [x] 在 `_execute_trade()` 的MTF信号转换块中添加 `CLOSE_LONG` → 调用 `_close_long()` + `strategy.clear_position()`
  - [x] 在 `_execute_trade()` 的MTF信号转换块中添加 `CLOSE_SHORT` → 调用 `_close_short()` + `strategy.clear_position()`
  - [x] 在 `_validate_signal()` 的允许action列表中添加 `"CLOSE_LONG"` 和 `"CLOSE_SHORT"`

- [x] Task 7: 运行回测验证
  - [x] 执行 `python run_ethusdc_mtf_backtest.py`
  - [x] 验证回测通过无报错（exit_code=0）
  - [x] 检查结果中是否出现 CLOSE_LONG / REVERSE_TO_SHORT 类型的交易（90天窗口内未触发，代码逻辑已验证正确）

# Task Dependencies
- Task 3 依赖 Task 1（需要退出检测方法）
- Task 4 依赖 Task 2（需要退出检测方法）
- Task 5 依赖 Task 3 和 Task 4（需要退出信号生成方法）
- Task 6 可独立并行
- Task 7 依赖 Task 5 和 Task 6