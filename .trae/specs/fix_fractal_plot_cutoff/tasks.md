# Tasks

- [x] Task 1: 在MTF策略中传播 `df_processed` 属性
  - [x] 在 `inject_data()` 末尾添加 `self.df_processed = self._chan.df_processed.copy()`
  - [x] 在 `_process_data()` 中通过 `inject_data()` 自动传播 `df_processed`
  - [x] 确保MTF策略对象在回测引擎 `hasattr(strategy, 'df_processed')` 检测时返回True

- [x] Task 2: 运行回测验证图表
  - [x] 执行 `run_ethusdc_mtf_backtest.py`
  - [x] 验证无Python异常（exit code 0）
  - [x] 验证生成的 `backtest_plot.png` K线数据与分型数据索引一致

# Task Dependencies
- Task 2 依赖 Task 1