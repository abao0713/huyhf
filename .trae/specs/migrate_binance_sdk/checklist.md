# Checklist

## 迁移验证清单

- [x] 所有旧 SDK 导入已移除
- [x] 新 SDK 导入已正确添加
- [x] 客户端初始化使用 `ConfigurationRestAPI` 和 `DerivativesTradingUsdsFutures`
- [x] 根据 `is_simulated` 正确选择 PROD/TESTNET URL
- [x] 手动时间同步代码已移除
- [x] `place_order` 方法已更新并正常工作
- [x] `get_order` 方法已更新并正常工作
- [x] `cancel_order` 方法已更新并正常工作
- [x] `get_account` 方法已更新并正常工作
- [x] `get_positions` 方法已更新并正常工作
- [x] `get_exchange_info` 方法已更新并正常工作
- [x] `get_continuous_klines` 方法已更新并正常工作
- [x] `get_spot_klines` 方法已更新并正常工作
- [x] 所有方法正确提取 `ApiResponse.data()` 并返回 dict/list
- [x] 时间戳 -1021 错误不再出现
- [x] 现有调用代码（run_crypto_chan_live.py 等）无需修改即可正常工作
