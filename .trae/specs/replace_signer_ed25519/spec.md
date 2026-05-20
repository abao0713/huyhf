# 签名器改造为 RSA/Ed25519/HMAC 多算法支持 Spec

## Why
当前 [signer.py](file:///e:/Auto_test/huyhf/trading_system/okx/signer.py) 仅支持 HMAC SHA256 签名。用户要求基于提供的 `Signers` 类模式完全重写签名器，支持 RSA、Ed25519 两种非对称签名算法，同时保持对现有 HMAC 密钥的向后兼容。

## What Changes
- **BREAKING**: `signer.py` 完全重写，从单一 HMAC SHA256 → 多算法自动检测签名器
- `client.py` 中 `BinanceSigner` 的调用方式不变（接口兼容）
- 安装依赖 `pycryptodome`（已安装 v3.23.0 ✅）

## Impact
- Affected specs: `fix_auth_signing`（鉴权签名逻辑被替换）
- Affected code: `trading_system/okx/signer.py`（重写）、`trading_system/okx/client.py`（无需改，接口兼容）

## MODIFIED Requirements
### Requirement: 多算法自动检测签名器
系统 SHALL 在初始化 `BinanceSigner` 时自动检测密钥类型，选择对应签名算法：

| 密钥格式 | 签名算法 | 签名输出 |
|----------|----------|----------|
| 64 位十六进制字符串 | HMAC SHA256 | hex 字符串 |
| PEM 格式 Ed25519 私钥 | Ed25519 (rfc8032) | hex 字符串 |
| PEM 格式 RSA 私钥 | RSA PKCS1_v1_5 | hex 字符串 |
| 文件路径 | 加载后同上述规则 | hex 字符串 |

#### Scenario: 现有 HMAC 密钥向后兼容
- **WHEN** `BinanceSigner("xZ2PH7kdI8AAYwtw2IdTyfXIpgBIrkQECsOPQ7qRowOiqNGNvQUlpVUiUvxTeRHA")` 被构造
- **THEN** 内部使用 HMAC SHA256 签名
- **AND** `sign_request(params)` 返回与当前实现一致的 hex 签名字符串

#### Scenario: Ed25519 密钥签名
- **WHEN** `BinanceSigner(ed25519_pem_key)` 被构造
- **THEN** 内部使用 Ed25519 + rfc8032 签名
- **AND** `sign_request(params)` 返回 hex 编码的签名

### Requirement: 保持公有接口不变
`BinanceSigner` 的公有接口 SHALL 保持不变，确保 `client.py` 无需修改：

```python
class BinanceSigner:
    def __init__(self, secret_key: str)
    def sign_request(self, params: dict) -> str   # 返回 hex 签名
    @staticmethod
    def get_timestamp() -> int                     # 毫秒时间戳
```

## 验证方法
运行 [client.py](file:///e:/Auto_test/huyhf/trading_system/okx/client.py) 的测试代码（L322-374），市价单和限价单均返回成功。