# Checklist: 修复分型索引与K线索引坐标系不匹配

- [x] ChanStrategy `__init__` 接受 `use_inclusion_merge` 参数且默认值为True（向后兼容）
- [x] `_process_data()` 在 `use_inclusion_merge=False` 时跳过包含关系合并
- [x] V2策略在 `load_data_for_backtest` 中禁用包含关系处理
- [x] `df_processed` 行数与 `df_30m` 一致（不缩编）
- [x] 分型的 `idx` 范围与原始K线索引一致（0~999）
- [x] `generate_signal(bar_idx)` 的 `bar_idx` 与 `fractal.idx` 在同一坐标系
- [x] 完整回测运行后，信号覆盖全部K线范围（不仅前500根）
- [x] 重新运行参数优化实验全部19个实验成功完成
- [x] 优化实验结果各参数组之间有明显区分度