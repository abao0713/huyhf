# Checklist

- [x] `run_ethusdc_mtf_backtest.py` 的 `RESISTANCE_LEVELS` 中包含 ≤2100 的阻力位（如2050）
- [x] `run_backtest.py` 的 `--resistance-levels` 默认值中包含 ≤2100 的阻力位
- [x] `run_ethusdc_mtf_backtest.py` 的 `SUPPORT_LEVELS` 覆盖价格区间下沿（如1950-1850）
- [x] `run_backtest.py` 的 `--support-levels` 默认值覆盖价格区间下沿
- [x] 回测日志中同时出现 `[MTF] 15m做空信号检测` 和 `[MTF] 15m信号检测`
- [x] 回测运行无Python异常
- [x] 回测报告输出完整（收益率、胜率、最大回撤）