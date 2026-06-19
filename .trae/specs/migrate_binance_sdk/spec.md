# 迁移至 binance-sdk-derivatives-trading-usds-futures SDK Spec

## Why
当前 `client.py` 使用旧的 `binance-futures-connector` 包（`from binance.um_futures import UMFutures`），该包存在时间戳偏移问题且已不再维护。需要迁移至官方新的模块化 SDK `binance-sdk-derivatives-trading-usds-futures`（v11.0.0），该 SDK 内置时间同步、更好的错误处理，且由 Binance 官方维护。

## What Changes
- **BREAKING**: 替换底层 SDK 依赖，从 `binance.um_futures.UMFutures` 迁移至 `binance_sdk_derivatives_trading_usds_futures`
- 更新所有 import 路径
- 更新客户端初始化方式（使用 `ConfigurationRestAPI` + `DerivativesTradingUsdsFutures`）
- 更新所有 API 方法调用映射到新 SDK 的方法名
- 适配新 SDK 的响应格式（`ApiResponse` 包装对象，通过 `.data()` 获取数据）
- 移除手动时间同步逻辑（新 SDK 内置时间戳处理）
- 保持 `BinanceRestClient` 对外接口不变（`place_order`, `get_order`, `cancel_order`, `get_account`, `get_positions`, `get_exchange_info`, `get_continuous_klines`, `get_spot_klines`）

## Impact
- Affected specs: 无直接依赖
- Affected code:
  - `trading_system/binance/client.py` — 主要修改文件
  - `run_crypto_chan_live.py` — 间接使用（通过 BinanceRestClient）
  - `run_crypto_chan_paper.py` — 间接使用（通过 BinanceRestClient）
  - `trading_system/data/market_data.py` — 可能间接使用

## API 方法映射表

| 旧方法 (UMFutures) | 新方法 (新SDK rest_api) | 说明 |
|---|---|---|
| `client.new_order(**params)` | `client.rest_api.new_order(...)` | 下单 |
| `client.query_order(**params)` | `client.rest_api.query_order(...)` | 查询订单 |
| `client.cancel_order(**params)` | `client.rest_api.cancel_order(...)` | 取消订单 |
| `client.account(recvWindow=6000)` | `client.rest_api.account_information_v2(recv_window=6000)` | 账户信息 |
| `client.get_position_risk(**params)` | `client.rest_api.position_information_v2(symbol=...)` | 持仓信息 |
| `client.exchange_info()` | `client.rest_api.exchange_information()` | 交易所信息 |
| `client.continuous_klines(**params)` | `client.rest_api.continuous_contract_kline_candlestick_data(...)` | 永续合约K线 |
| `client.klines(**params)` | `client.rest_api.kline_candlestick_data(...)` | 现货K线 |

## 响应格式变化

旧 SDK 返回原始 dict/list，新 SDK 返回 `ApiResponse` 包装对象：
- 旧：`result = client.account()` → `result` 是 dict
- 新：`response = client.rest_api.account_information_v2()` → `response.data()` 获取实际数据

## REMOVED Requirements
### Requirement: 手动时间同步 (_sync_server_time)
**Reason**: 新 SDK 内置时间戳处理机制，不再需要手动 patch `get_timestamp`
**Migration**: 移除 `_sync_server_time` 方法和 `_time_offset` 相关代码
