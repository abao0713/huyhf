# 修复 Live 模式运行错误 Spec

## Why
运行 `run_crypto_chan_live.py` 时出现两个错误：
1. `'CryptoChan4HMasterStrategy' object has no attribute '_process_pending_limit_orders'` - 策略类缺少限价单处理方法
2. `无法获取账户余额，使用默认值: $10,000.00` - `get_account` 方法返回的数据结构不包含 `availableBalance` 字段，需要使用 `futures_account_balance_v3` API 获取余额

## What Changes
- 在 `client.py` 中新增 `get_account_balance()` 方法，调用 `futures_account_balance_v3` API 获取账户余额
- 在 `run_crypto_chan_live.py` 中修改余额获取逻辑，使用新的 `get_account_balance()` 方法
- 在 `mtf_fractal_strategy.py` 中添加 `_process_pending_limit_orders()` 方法（空实现或注释掉调用）

## Impact
- Affected specs: fix_timestamp_sync, optimize_dingtalk_notify_v2
- Affected code:
  - `e:\Auto_test\huyhf\trading_system\binance\client.py`（新增方法）
  - `e:\Auto_test\huyhf\run_crypto_chan_live.py`（修改余额获取逻辑）
  - `e:\Auto_test\huyhf\trading_system\strategies\mtf_fractal_strategy.py`（添加缺失方法）

## ADDED Requirements

### Requirement: 账户余额查询方法
系统 SHALL 提供 `get_account_balance()` 方法，通过 `futures_account_balance_v3` API 获取账户可用余额。

**API 参考**:
```python
response = client.rest_api.futures_account_balance_v3()
```

**返回值**:
- 成功时返回包含余额信息的字典，包含 `availableBalance` 字段
- 失败时返回包含 `error` 字段的字典

#### Scenario: 成功获取余额
- **WHEN** 调用 `get_account_balance()` 且 API 正常
- **THEN** 返回包含 `availableBalance` 字段的字典
- **THEN** `availableBalance` 值为字符串类型的余额

#### Scenario: API 调用失败
- **WHEN** API 调用失败（网络错误、认证失败等）
- **THEN** 返回包含 `error` 字段的字典
- **THEN** 不影响程序继续运行

### Requirement: Live 模式余额获取逻辑
系统 SHALL 在 Live 模式初始化时使用 `get_account_balance()` 获取账户余额。

#### Scenario: 成功获取余额
- **WHEN** Live 模式启动并调用 `get_account_balance()`
- **THEN** 使用返回的 `availableBalance` 作为初始资金
- **THEN** 日志显示实际账户余额

#### Scenario: 获取余额失败
- **WHEN** `get_account_balance()` 返回错误
- **THEN** 使用默认初始资金 $10,000.00
- **THEN** 日志显示警告信息

### Requirement: 限价单处理方法
系统 SHALL 在 `CryptoChan4HMasterStrategy` 类中提供 `_process_pending_limit_orders()` 方法。

#### Scenario: 方法存在
- **WHEN** 调用 `strategy._process_pending_limit_orders()`
- **THEN** 不抛出 `AttributeError`
- **THEN** 方法可以正常执行（即使为空实现）

## MODIFIED Requirements

### Requirement: get_account 方法返回值处理
当前 `get_account()` 方法调用 `account_information_v2`，返回的数据结构可能不包含 `availableBalance` 字段。需要：
1. 保留 `get_account()` 方法用于获取账户详细信息
2. 新增 `get_account_balance()` 方法专门用于获取余额

## REMOVED Requirements
无

## Verification Requirements

### 验证场景1: 余额查询
- **输入**: 调用 `await client.get_account_balance()`
- **预期输出**: 返回包含 `availableBalance` 字段的字典

### 验证场景2: Live 模式启动
- **输入**: 运行 `run_crypto_chan_live.py`
- **预期输出**: 
  - 不出现 `_process_pending_limit_orders` 错误
  - 日志显示实际账户余额（非默认值）

### 验证场景3: 限价单处理
- **输入**: 在 Live 模式运行过程中调用 `strategy._process_pending_limit_orders()`
- **预期输出**: 不抛出异常
