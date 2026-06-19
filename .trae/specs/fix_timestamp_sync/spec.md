# Fix Binance Timestamp Sync Spec

## Why
当前 `client.py` 中的时间同步机制存在代码截断和方法缺失问题，导致请求仍然出现 `-1021 Timestamp for this request is outside of the recvWindow` 错误。需要修复 patch 函数并实现服务器时间同步逻辑。

## What Changes
- 修复 `_patch_binance_timestamp()` 函数中的截断错误（L53）
- 实现 `_sync_server_time()` 方法，通过 API 获取服务器时间并计算偏移量
- 确保时间偏移在 SDK 签名请求时正确应用

## Impact
- Affected specs: migrate_binance_sdk, fix_auth_signing
- Affected code: `e:\Auto_test\huyhf\trading_system\binance\client.py`

## ADDED Requirements

### Requirement: Server Time Synchronization
系统 SHALL 在初始化时自动同步 Binance 服务器时间，计算本地时间与服务器时间的偏移量，并在所有签名请求中应用该偏移量。

#### Scenario: Client Initialization
- **WHEN** `BinanceRestClient` 实例化时
- **THEN** 调用 `/fapi/v1/time` 获取服务器时间
- **THEN** 计算时间偏移量 `offset = server_time - local_time`
- **THEN** 将偏移量存储到全局变量 `_time_offset_ms`

#### Scenario: Signed Request with Time Offset
- **WHEN** 发送需要签名的 API 请求（如 `place_order`）
- **THEN** SDK 调用 `get_timestamp()` 时返回 `local_time + offset`
- **THEN** 请求时间戳与服务器时间偏差 < 1 秒
- **THEN** 不再出现 `-1021` 时间戳错误

## MODIFIED Requirements

### Requirement: Patch Binance Timestamp Function
修复 `_patch_binance_timestamp()` 函数，正确替换 `binance_common.utils.get_timestamp` 为带偏移量的版本。

**Current Issue**:
```python
# L53 代码被截断
binance_utils.get_timestamp = _get_timestamp_with_of  # 错误：函数名不完整
```

**Corrected Implementation**:
```python
def _patch_binance_timestamp():
    """Patch binance_common.utils.get_timestamp 函数"""
    import binance_common.utils as binance_utils
    binance_utils.get_timestamp = _get_timestamp_with_offset
    logger.info("已 patch binance_common.utils.get_timestamp")
```

### Requirement: Implement _sync_server_time Method
在 `BinanceRestClient` 类中实现 `_sync_server_time()` 方法。

**Implementation**:
```python
def _sync_server_time(self):
    """同步服务器时间，计算本地时间与服务器时间的偏移量"""
    try:
        import requests
        local_time_before = int(time.time() * 1000)
        
        # 调用 Binance 时间 API
        base_url = DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL if self.is_simulated else DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
        response = requests.get(f"{base_url}/fapi/v1/time", timeout=5000)
        response.raise_for_status()
        
        server_time = response.json().get("serverTime")
        local_time_after = int(time.time() * 1000)
        
        if server_time:
            # 计算本地时间（取请求前后的平均值）
            local_time_avg = (local_time_before + local_time_after) // 2
            offset = server_time - local_time_avg
            
            _set_time_offset(offset)
            logger.info(f"时间同步成功: 服务器时间={server_time}, 本地时间={local_time_avg}, 偏移量={offset}ms")
        else:
            logger.warning("服务器时间获取失败，使用时间偏移 0")
            
    except Exception as e:
        logger.error(f"时间同步失败: {e}，使用时间偏移 0")
```

## REMOVED Requirements
无
