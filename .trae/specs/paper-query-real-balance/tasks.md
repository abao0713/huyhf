# Tasks

- [x] Task 1: PaperTradingClient 增加异步余额查询初始化
  - [x] 新增 `async def initialize()` 方法，通过 `BinanceRestClient` 查询真实余额
  - [x] 查询成功则将 `_balance` 和 `_initial_balance` 设置为查询值
  - [x] 查询失败则回退到默认 $10,000 并记录警告
  - [x] 在 `run_ethusdc_mtf_live.py` 中 `Executor.start()` 之前调用 `await client.initialize()`

- [x] Task 2: 移除 --initial-balance CLI 参数
  - [x] 删除 `run_ethusdc_mtf_live.py` 中 `--initial-balance` 参数定义
  - [x] 删除 `PaperTradingClient(...)` 构造时传入 `initial_balance` 参数

- [x] Task 3: 语法检查验证
  - [x] `python -m py_compile` 两个文件通过

# Task Dependencies
- Task 2 depends on Task 1