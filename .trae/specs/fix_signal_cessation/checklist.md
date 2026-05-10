# Checklist: 修复V2策略K线索引100后信号停止

- [x] `generate_signal(bar_idx)` 接受bar_idx参数且无参数调用向后兼容
- [x] 传入bar_idx=5时能匹配到idx=5的分型并生成正确信号
- [x] 传入bar_idx=6（无分型位置）时返回 `{"action": "HOLD"}`
- [x] 传入bar_idx=20时分型类型正确映射到信号方向
- [x] 回测引擎主循环正确传递 `i` 给 `generate_signal(bar_idx=i)`
- [x] 完整回测运行后，信号覆盖全部K线范围（不仅仅前100根）
- [x] 重新运行参数优化实验全部19个实验成功完成
- [x] 优化实验结果各参数组之间有明显区分度（非全部相同）
- [x] 优化报告 `optimization_report.json` 包含全部实验结果