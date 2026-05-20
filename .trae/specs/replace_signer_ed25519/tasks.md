# Tasks

- [x] Task 1: 重写 signer.py 为多算法签名器
  - [x] 实现 `Signers` 内部类（RSA + Ed25519 密钥缓存）
  - [x] 实现 `BinanceSigner.__init__`：自动检测密钥类型（PEM → RSA/Ed25519，其他 → HMAC）
  - [x] 实现 `BinanceSigner.sign_request`：按检测到的算法签名，返回 hex 字符串
  - [x] 保留 `BinanceSigner.get_timestamp()` 静态方法
  - [x] 现有 HMAC 密钥向后兼容（新旧签名输出一致）

- [x] Task 2: 运行 client.py 测试验证
  - [x] K线获取成功（800条4h + 100条现货）
  - [x] `get_positions()` 返回 `[]`（签名 GET 请求通过 ✅）
  - [x] `place_order()` 市价单返回 `-2015`（API Key 缺少交易权限，非代码问题）
  - [x] `place_order()` 限价单返回 `-2015`（同上）

> **注意**: 下单 `-2015` 错误是因为当前 API Key 在 Binance 测试网缺少 TRADE（交易）权限，不属于代码签名问题。签名 GET 请求（`get_positions`）已成功验证签名正确性。

# Task Dependencies
- Task 2 depends on Task 1