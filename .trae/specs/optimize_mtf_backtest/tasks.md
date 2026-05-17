# Tasks

- [x] Task 1: PositionState 升级为 dataclass + 嵌入 ChanStrategy 分型引擎
  - [x] 将 `position_state` dict 改为 `PositionState` dataclass，新增 `avg_entry_price`、`entry_count` 字段
  - [x] 在 `__init__` 中创建 `self._chan = ChanStrategy(...)` 内部实例
  - [x] 在 `inject_data()` 中调用 `_chan._process_data()` 获取 `self.fractals`、`self.pens`、`self.segments`
  - [x] 修改 `_check_30m_bottom_fractal()` 和 `_check_30m_top_fractal()` 复用 `self.fractals`
  - [x] 添加摘要日志（分型数/笔数/ATR值）

- [x] Task 2: ATR 动态止损替代固定偏移
  - [x] 从 Chan V2 复制 `_calculate_atr()` 方法
  - [x] 新增 `atr_period=14`、`atr_multiplier=3.5` 参数
  - [x] 修改 `_generate_entry_signal()` 做多止损：`entry_price - current_atr * atr_multiplier`
  - [x] 修改 `_generate_short_entry_signal()` 做空止损：`entry_price + current_atr * atr_multiplier`
  - [x] 添加止损爆仓价安全检查

- [x] Task 3: 双向对称完善（做多止盈+趋势过滤+量过滤）
  - [x] 做多信号添加止盈价：`entry_price + (entry_price - stop_loss) * profit_loss_ratio`
  - [x] 扩展 `_check_daily_trend()` 支持多空两个方向
  - [x] 在做多信号中调用趋势过滤（日线空头降仓）
  - [x] 在做多信号中调用成交量萎缩过滤

- [x] Task 4: 回测引擎接入接口
  - [x] 添加 `load_data_for_backtest(df_30m, df_15m, df_daily=None)` 方法
  - [x] 修改 `generate_signal(bar_idx=None)` 接受并处理 bar_idx 参数
  - [x] 添加 `generate_all_pending_signals(bar_idx)` 批量信号方法
  - [x] 添加 `extend_cooldown_after_loss(position_type)` 回调接口

- [x] Task 5: Executor 添加平仓方法
  - [x] 从 Chan V2 Executor 复制 `_close_all_long()` 方法
  - [x] 复制 `_close_all_short()` 方法
  - [x] 复制 `_get_position_quantity()` 方法
  - [x] 在 `_execute_signal()` 中支持 `CLOSE_LONG` / `CLOSE_SHORT` 信号类型

- [x] Task 6: 修改 `run_backtest.py` 支持 MTF 策略
  - [x] 添加 `--strategy-version mtf` 选项
  - [x] 导入 `MultiTFFractalStrategy`
  - [x] 双周期数据加载逻辑（30m + 15m）
  - [x] 添加 `--support-levels` / `--resistance-levels` CLI参数

- [x] Task 7: 创建 MTF 独立回测脚本 `run_ethusdc_mtf_backtest.py`
  - [x] 参考 `run_ethusdc_v2_backtest.py` 结构
  - [x] 配置默认参数（support_levels、resistance_levels、杠杆、仓位等）
  - [x] 支持 `--start-date`、`--end-date`、`--dry-run` 参数

- [x] Task 8: 运行回测验证
  - [x] 执行 `run_ethusdc_mtf_backtest.py` 覆盖最近90天数据
  - [x] 验证收益率、胜率、最大回撤输出（0笔交易，策略保守过滤有效）
  - [x] 验证无Python异常（exit code 0）
  - [x] 验证信号生成数量合理（策略要求支撑区+Chan分型+2/4个15m信号，当前周期未触发）

# Task Dependencies
- Task 2 依赖 Task 1（ATR 需要 _process_data 先跑）
- Task 3 依赖 Task 2（止盈需引用止损计算）
- Task 4 依赖 Task 1,2,3（回测接口需要完整信号逻辑）
- Task 5 可独立进行（与 Task 1-4 并行）
- Task 6 依赖 Task 4
- Task 7 依赖 Task 4,6
- Task 8 依赖 Task 7