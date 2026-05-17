# Paper Trading 查询真实余额 Spec

## Why
当前 `PaperTradingClient` 使用硬编码 `--initial-balance` 参数（默认 $10,000）作为起始资金。用户的 Binance 模拟盘（testnet）账户中已有真实资金，纸交易应通过 API 查询该余额作为起始资金，无需手动指定。

## What Changes
- **PaperTradingClient** 初始化时通过 `BinanceRestClient` 查询真实账户余额作为 `_balance`
- 移除 `--initial-balance` CLI 参数
- `_balance` 初始值改为异步查询结果，不存在时回退到默认值

## Impact
- Affected specs: none
- Affected code: `trading_system/okx/paper_client.py`, `run_ethusdc_mtf_live.py`

## ADDED Requirements
### Requirement: PaperTradingClient 查询真实余额初始化
PaperTradingClient SHALL 在初始化完成后、首次交易前，通过 BinanceRestClient 查询模拟盘账户的真实余额，并将其作为本地模拟的起始资金。

#### Scenario: 成功查询余额
- **WHEN** PaperTradingClient 启动
- **THEN** 调用 `BinanceRestClient.get_account()` 获取 `availableBalance`（或 `totalMarginBalance`）
- **AND** 将 `_balance` 设置为查询到的余额值
- **AND** 将 `_initial_balance` 设置为相同值

#### Scenario: 查询失败回退
- **WHEN** API 查询余额失败（网络错误、无 API Key 等）
- **THEN** 回退到默认初始资金 $10,000
- **AND** 日志记录警告信息

## REMOVED Requirements
### Requirement: --initial-balance CLI 参数
**Reason**: 余额由 API 查询获取，无需手动指定
**Migration**: 移除 `run_ethusdc_mtf_live.py` 中 `--initial-balance` 参数定义及传参