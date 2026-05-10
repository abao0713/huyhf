# Tasks: 修复分型索引与K线索引坐标系不匹配

- [x] Task 1: 修改 `chan_strategy.py` 的 `_process_data()` 支持跳过包含关系处理
  - 在 `__init__` 中添加 `use_inclusion_merge: bool = True` 参数
  - 修改 `_process_data()` 中的 `_merge_inclusion` 调用，添加条件判断
  - 当 `use_inclusion_merge=False` 时跳过包含关系合并

- [x] Task 2: 修改 `chan_strategy_v2.py` 的 `load_data_for_backtest()` 禁用包含关系处理
  - 在创建内部策略时设置 `use_inclusion_merge=False`
  - 确保 `df_processed` 行数与 `df_30m` 一致

- [x] Task 3: 重新运行完整5组参数优化实验
  - 执行 `python run_param_optimization.py --clean`
  - 验证信号覆盖全部K线范围
  - 比较修复前后的交易数和收益率变化

# Task Dependencies
- Task 1 无依赖
- Task 2 depends on Task 1
- Task 3 depends on Task 1, 2