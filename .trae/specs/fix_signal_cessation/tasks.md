# Tasks: 修复V2策略K线索引100后信号停止

- [x] Task 1: 修改 `chan_strategy_v2.py` 的 `generate_signal()` 支持bar_idx参数
  - 添加 `bar_idx: int = None` 参数
  - 当 `bar_idx is None` 时保持原有顺序处理（向后兼容）
  - 当 `bar_idx` 传入时，查找 `fractals` 列表中 `idx == bar_idx` 的分型
  - 找到匹配分型后生成信号，未找到返回HOLD
  - 移除 `_current_fractal_idx += 1` 的顺序推进逻辑（改为按idx定位）

- [x] Task 2: 修改 `chan_strategy_v2.py` 的 `on_bar()` 传递bar_idx
  - `on_bar(bar_data, bar_idx=None)` 新增参数
  - 调用 `self.generate_signal(bar_idx=bar_idx)`

- [x] Task 3: 修改 `backtest_engine.py` 主循环传递bar索引
  - 在 `_run_backtest_loop()` 中，将 `strategy.generate_signal()` 改为 `strategy.generate_signal(bar_idx=i)`

- [x] Task 4: 重新运行完整5组参数优化实验
  - 执行 `python run_param_optimization.py --clean`
  - 验证所有19个实验全部完成
  - 确认各参数组之间结果有明显区分度
  - 确认回测覆盖全部K线范围

# Task Dependencies
- Task 1 无依赖
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1, 2, 3