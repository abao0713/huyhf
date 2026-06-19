# 新增待成交订单查询接口 Spec

## Why
策略执行器需要查询当前所有未成交的限价单，以便在 `_process_pending_limit_orders` 方法中检查订单状态并决定是否取消或调整。现有 `get_order` 方法只能查询单个订单，缺少批量查询所有未成交订单的接口。

## What Changes
- 在 `BinanceRestClient` 类中新增 `get_open_orders()` 方法
- 调用 SDK 的 `current_all_open_orders()` API
- 支持可选的 `symbol` 参数过滤特定交易对
- 返回所有未成交订单列表

## Impact
- Affected specs: fix_live_mode_errors, order_status_query
- Affected code: 
  - `trading_system/binance/client.py` - 新增接口方法
  - `trading_system/strategies/mtf_fractal_strategy.py` - 策略可调用此接口查询待成交订单

## ADDED Requirements

### Requirement: 查询所有未成交订单接口
The system SHALL provide a method to query all open orders (unfilled or partially filled orders) from Binance Futures API.

#### Scenario: 查询所有交易对的未成交订单
- **WHEN** 调用 `get_open_orders()` 不传参数
- **THEN** 返回所有交易对的未成交订单列表
- **AND** 每个订单包含 orderId, symbol, side, price, qty, status 等字段

#### Scenario: 查询特定交易对的未成交订单
- **WHEN** 调用 `get_open_orders(symbol="BTCUSDT")`
- **THEN** 仅返回 BTCUSDT 交易对的未成交订单列表

#### Scenario: API 调用失败
- **WHEN** API 调用发生异常
- **THEN** 返回包含 error 和 msg 字段的字典
- **AND** 记录错误日志

### Requirement: 订单状态判断辅助方法
The system SHALL provide helper methods to check order fill status.

#### Scenario: 判断订单是否完全成交
- **WHEN** 调用 `is_order_filled(order)` 且订单 status 为 "FILLED"
- **THEN** 返回 True

#### Scenario: 判断订单是否部分成交
- **WHEN** 调用 `is_order_partially_filled(order)` 且订单 status 为 "PARTIALLY_FILLED"
- **THEN** 返回 True

## MODIFIED Requirements

### Requirement: 策略待成交订单处理逻辑
策略类 `CryptoChan4HMasterStrategy` 的 `_process_pending_limit_orders` 方法应使用新接口查询实际订单状态，而非仅维护内部状态。

#### Scenario: 查询并更新待成交订单状态
- **WHEN** 执行器调用 `strategy._process_pending_limit_orders()`
- **THEN** 策略通过客户端调用 `get_open_orders()` 查询实际订单状态
- **AND** 根据查询结果更新内部 `_pending_limit_orders` 列表
- **AND** 已成交订单调用 `mark_order_filled()`
- **AND** 已取消订单调用 `mark_order_cancelled()`
