# Tasks

- [ ] Task 1: 重写 `_check_15m_first_buy()` — 直接MACD底背驰检测
  - [ ] 计算15分钟 MACD(12,26,9)
  - [ ] 在最近100根K线中定位两个显著低点（间隔 >= 5根K线）
  - [ ] 检测：价格新低 < 前低 AND DIF新低 > DIF前低
  - [ ] 返回 (bool, details_dict)
  - [ ] 实现文件: `mtf_fractal_strategy.py`

- [ ] Task 2: 重写 `_check_15m_first_sell()` — 直接MACD顶背驰检测
  - [ ] 计算15分钟 MACD(12,26,9)
  - [ ] 在最近100根K线中定位两个显著高点（间隔 >= 5根K线）
  - [ ] 检测：价格新高 > 前高 AND DIF新高 < DIF前高
  - [ ] 返回 (bool, details_dict)
  - [ ] 实现文件: `mtf_fractal_strategy.py`

- [ ] Task 3: 重构 `_generate_early_entry_signal()` — 3取2条件模型
  - [ ] 移除置信度加权累加逻辑
  - [ ] 3条件独立判断：first_buy / second_buy / uptrend
  - [ ] 满足数 >= self.min_early_entry_conditions 则生成信号
  - [ ] 移除 `early_entry_min_confidence` 依赖
  - [ ] 实现文件: `mtf_fractal_strategy.py`

- [ ] Task 4: 重构 `_generate_early_short_entry_signal()` — 3取2条件模型
  - [ ] 移除置信度加权累加逻辑
  - [ ] 3条件独立判断：first_sell / second_sell / downtrend
  - [ ] 满足数 >= self.min_early_entry_conditions 则生成信号
  - [ ] 移除 `early_short_entry_min_confidence` 依赖
  - [ ] 实现文件: `mtf_fractal_strategy.py`

- [ ] Task 5: 新增 `min_early_entry_conditions` 参数
  - [ ] `MultiTFFractalStrategy.__init__` 添加参数（默认 2）
  - [ ] `MultiTFFractalStrategyExecutor.__init__` 添加参数（默认 2）
  - [ ] Executor 创建策略时透传参数
  - [ ] 实现文件: `mtf_fractal_strategy.py`

- [ ] Task 6: 更新 `run_ethusdc_mtf_backtest.py` 回测脚本
  - [ ] 添加 `--min-early-entry-conditions` CLI参数（默认 2）
  - [ ] 透传到策略创建
  - [ ] 实现文件: `run_ethusdc_mtf_backtest.py`

- [ ] Task 7: 语法检查
  - [ ] `python -m py_compile mtf_fractal_strategy.py`
  - [ ] `python -m py_compile run_ethusdc_mtf_backtest.py`

- [ ] Task 8: 运行回测并分析结果
  - [ ] 运行 `run_ethusdc_mtf_backtest.py` 覆盖最近90天
  - [ ] 分析交易数、胜率、收益率、最大回撤
  - [ ] 给出进一步优化建议

# Task Dependencies
- Task 1 和 Task 2 可并行执行（互为镜像）
- Task 3 依赖 Task 1（使用新的 _check_15m_first_buy）
- Task 4 依赖 Task 2（使用新的 _check_15m_first_sell）
- Task 3 和 Task 4 可并行执行（互为镜像）
- Task 5 与 Task 1-4 独立，可并行执行
- Task 6 依赖 Task 5（需要参数定义存在）
- Task 7 依赖 Task 1-6
- Task 8 依赖 Task 7