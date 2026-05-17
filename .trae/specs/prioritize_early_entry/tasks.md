# Tasks

- [x] Task 1: 反转 `_generate_signal_internal` 优先级 — 提前入场在前
  - [x] 将提前入场检测块移到标准入场检测块之前
  - [x] 添加双向提前入场冲突处理（按 satisfied_count 比较）
  - [x] 实现文件: `mtf_fractal_strategy.py`

- [x] Task 2: 调整仓位比例默认值
  - [x] `MultiTFFractalStrategy.__init__`: `early_entry_ratio` 默认 0.25 → 0.40
  - [x] `MultiTFFractalStrategy.__init__`: `early_short_entry_ratio` 默认 0.25 → 0.40
  - [x] `MultiTFFractalStrategyExecutor.__init__`: 同步修改
  - [x] 实现文件: `mtf_fractal_strategy.py`

- [x] Task 3: 提前入场后的标准加仓使用剩余仓位
  - [x] 新增 `MTFPositionState.is_early_entry` 标记
  - [x] 在 `update_position_from_signal` 中设置 early_entry/early_short_entry 标记
  - [x] `_generate_confirm_signal` 检测 is_early_entry → 加仓比例 = investment_ratio - early_entry_ratio
  - [x] `_generate_short_confirm_signal` 镜像处理
  - [x] 实现文件: `mtf_fractal_strategy.py`

- [x] Task 4: 更新回测脚本显示
  - [x] `run_ethusdc_mtf_backtest.py` 中 early_entry_ratio 显示更新为 40%
  - [x] 实现文件: `run_ethusdc_mtf_backtest.py`

- [x] Task 5: 语法检查
  - [x] `python -m py_compile mtf_fractal_strategy.py` ✅
  - [x] `python -m py_compile run_ethusdc_mtf_backtest.py` ✅

- [x] Task 6: 运行回测并分析结果
  - [x] 运行 `run_ethusdc_mtf_backtest.py`
  - [x] 验证 EARLY_ENTRY 信号已触发（4次提前入场！）
  - [x] 分析胜率、收益率变化
  - [x] 修复2个关键bug：_process_data参数位置错误 + MACD index越界

# Task Dependencies
- Task 1 是核心修改，无依赖
- Task 2 与 Task 1 可并行
- Task 3 依赖 Task 1（需要先有提前入场优先逻辑）
- Task 4 依赖 Task 2
- Task 5 依赖 Task 1-4
- Task 6 依赖 Task 5

# Bug修复记录
- **Bug 1**: `_process_data()` 调用 `inject_data(df_4h, df_30m_sliced, df_daily)` 将 self.df_daily 错误传入 df_15m 参数，导致15m数据被日线数据覆盖
- **Bug 2**: MACD背驰检测中 `reset_index(drop=True)` 缺失，导致 `idxmin()` 返回原始DataFrame索引在切片后越界