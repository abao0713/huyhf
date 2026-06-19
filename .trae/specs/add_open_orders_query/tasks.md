# Tasks

## Task 1: 在 BinanceRestClient 中新增 get_open_orders() 方法
- [x] 1.1 在 `trading_system/binance/client.py` 中添加 `get_open_orders(symbol: str = None)` 方法
- [x] 1.2 调用 SDK 的 `current_all_open_orders()` API
- [x] 1.3 支持可选的 symbol 参数过滤
- [x] 1.4 返回订单列表或错误字典
- [x] 1.5 添加完整的日志记录

## Task 2: 添加订单状态判断辅助方法
- [x] 2.1 在 `BinanceRestClient` 中添加 `is_order_filled(order: Dict) -> bool` 方法
- [x] 2.2 添加 `is_order_partially_filled(order: Dict) -> bool` 方法
- [x] 2.3 添加 `is_order_cancelled(order: Dict) -> bool` 方法

## Task 3: 更新策略类使用新接口查询订单状态
- [x] 3.1 修改 `mtf_fractal_strategy.py` 中的 `_process_pending_limit_orders()` 方法
- [x] 3.2 通过执行器客户端调用 `get_open_orders()` 查询实际订单状态
- [x] 3.3 根据查询结果调用 `mark_order_filled()` 或 `mark_order_cancelled()`
- [x] 3.4 添加日志记录订单状态变更

## Task 4: 验证接口功能
- [x] 4.1 运行 `run_crypto_chan_live.py` 验证无报错
- [x] 4.2 检查日志中 `get_open_orders` 调用正常
- [x] 4.3 验证订单状态判断逻辑正确

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1, Task 2
- Task 4 depends on Task 3
