# Checklist

- [x] `_generate_signal_internal` 中提前入场检测在标准入场之前执行
- [x] 提前做多 / 提前做空 先于 标准做多 / 标准做空
- [x] 提前入场命中后直接 return，不再检测标准入场
- [x] 双向提前入场冲突时按 satisfied_count 选择更大者
- [x] `early_entry_ratio` 默认值 = 0.40
- [x] `early_short_entry_ratio` 默认值 = 0.40
- [x] Executor 参数同步更新
- [x] 提前入场持仓的 K3 确认加仓比例 = `investment_ratio - early_entry_ratio`
- [x] `run_ethusdc_mtf_backtest.py` 显示更新正确
- [x] Python语法检查通过
- [x] 回测有 EARLY_ENTRY 信号触发（4次提前入场！）