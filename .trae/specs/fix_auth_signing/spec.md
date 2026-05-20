# Binance API 鉴权规范符合性审查 Spec

## Why
用户提供 Binance 官方 REST API 鉴权规范，要求审查当前 [client.py](file:///e:/Auto_test/huyhf/trading_system/okx/client.py) 和 [signer.py](file:///e:/Auto_test/huyhf/trading_system/okx/signer.py) 的实现是否符合要求。

## 审查结论

### 已满足项 ✅

| 检查项 | 要求 | 当前实现 | 状态 |
|--------|------|----------|------|
| 签名算法 | HMAC SHA256 | `hmac.new(key, msg, hashlib.sha256).hexdigest()` | ✅ |
| 签名密钥 | API-Secret 作为 HMAC 密钥 | `BinanceSigner(secret_key)` | ✅ |
| 签名对象 | 所有参数（不含signature） | `sorted(params.items())` 生成 query_string | ✅ |
| 参数排序 | 字母顺序 | `sorted(params.items())` | ✅ |
| 签名位置 | 位于 query string 最后 | `params["signature"] = ...` 最后添加 | ✅ |
| timestamp | 毫秒 Unix 时间戳 | `int(datetime.now().timestamp() * 1000)` | ✅ |
| API 路径前缀 | `/fapi/v1` | `config.rest_api_path = "/fapi/v1"` | ✅ |
| POST 请求 | 参数走 query string | `session.post(url, json=body, params=params)` | ✅ |
| 签名格式 | 十六进制小写（大小写不敏感） | `.hexdigest()` 返回小写 | ✅ |
| X-MBX-APIKEY | HTTP 请求头 | `headers = {"X-MBX-APIKEY": self.api_key}` | ✅ |
| GET 签名 | GET 也需 timestamp+signature | `_request` 统一处理 | ✅ |
| DELETE 签名 | DELETE 也需 | `_request` 统一处理 | ✅ |

### 需修复项 ❌

| 检查项 | 要求 | 当前实现 | 问题 |
|--------|------|----------|------|
| recvWindow | 建议设置 5000，防止时钟偏差导致请求被拒 | 未传递 recvWindow | 本地时钟偏差可能触发 "Timestamp for this request was 5000ms ahead of the server's time" 错误 |
| 冗余签名 | 无冗余 | `get_account()` 和 `get_positions()` 手动添加 timestamp+signature 后 `_request()` 再次覆盖 | 每请求多计算一次签名，冗余且可能引起困惑 |

### 接口基准 URL 验证

| 环境 | 官方地址 | 当前配置 | 状态 |
|------|----------|----------|------|
| 实盘 REST | `https://fapi.binance.com/fapi/v1` | `https://fapi.binance.com/fapi/v1` | ✅ |
| 模拟盘 REST | `https://testnet.binancefuture.com/fapi/v1` | `https://demo-fapi.binance.com/fapi/v1` | ⚠️ 待确认 |

> 注：Binance 测试网存在多个域名，`demo-fapi.binance.com` 需要实际测试验证是否可用。

## What Changes
- `_request()` 签名时自动追加 `recvWindow=5000`
- 移除 `get_account()` 和 `get_positions()` 中的冗余手动签名逻辑

## Impact
- Affected specs: none
- Affected code: `trading_system/okx/client.py`

## MODIFIED Requirements
### Requirement: 签名请求自动携带 recvWindow
`_request()` 方法在 `signed=True` 时 SHALL 自动追加 `recvWindow=5000` 参数后再计算签名。

#### Scenario: 签名请求自动加 recvWindow
- **WHEN** `_request(method, path, params, signed=True)` 被调用
- **THEN** 在添加 `timestamp` 之后、`signature` 之前，自动 `params["recvWindow"] = recvWindow`（默认 5000）
- **AND** 签名计算包含 recvWindow 参数

### Requirement: 移除冗余签名逻辑
`get_account()` 和 `get_positions()` 方法 SHALL 不再手动添加 timestamp 和 signature，交由 `_request()` 统一处理。

#### Scenario: 签名由 _request 统一处理
- **WHEN** `get_account()` 被调用
- **THEN** 仅设置业务参数，调用 `_request("GET", path, signed=True)`
- **AND** timestamp、recvWindow、signature 均由 `_request()` 添加