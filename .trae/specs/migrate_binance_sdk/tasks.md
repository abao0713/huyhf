# Tasks

## 迁移 Binance SDK

- [x] Task 1: 更新导入语句
  - [x] 1.1 移除 `from binance.um_futures import UMFutures`
  - [x] 1.2 添加新 SDK 导入：`DerivativesTradingUsdsFutures`, `ConfigurationRestAPI`, URL 常量
  - [x] 1.3 添加响应模型导入（可选，用于类型提示）

- [x] Task 2: 更新客户端初始化逻辑
  - [x] 2.1 修改 `__init__` 方法，使用 `ConfigurationRestAPI` 创建配置
  - [x] 2.2 根据 `is_simulated` 参数选择正确的 base_url（PROD 或 TESTNET）
  - [x] 2.3 初始化 `DerivativesTradingUsdsFutures` 客户端
  - [x] 2.4 移除手动时间同步代码（`_sync_server_time`, `_apply_time_offset`）

- [x] Task 3: 更新 API 方法调用
  - [x] 3.1 更新 `place_order` 方法：调用 `rest_api.new_order()`
  - [x] 3.2 更新 `get_order` 方法：调用 `rest_api.query_order()`
  - [x] 3.3 更新 `cancel_order` 方法：调用 `rest_api.cancel_order()`
  - [x] 3.4 更新 `get_account` 方法：调用 `rest_api.account_information_v2()`
  - [x] 3.5 更新 `get_positions` 方法：调用 `rest_api.position_information_v2()`
  - [x] 3.6 更新 `get_exchange_info` 方法：调用 `rest_api.exchange_information()`
  - [x] 3.7 更新 `get_continuous_klines` 方法：调用 `rest_api.continuous_contract_kline_candlestick_data()`
  - [x] 3.8 更新 `get_spot_klines` 方法：调用 `rest_api.kline_candlestick_data()`

- [x] Task 4: 适配响应格式
  - [x] 4.1 所有方法返回值改为从 `ApiResponse.data()` 提取实际数据
  - [x] 4.2 确保返回值类型与原有接口一致（dict/list）

- [x] Task 5: 测试验证
  - [x] 5.1 运行现有测试脚本验证基本功能
  - [x] 5.2 验证时间戳问题已解决（不再出现 -1021 错误）
  - [x] 5.3 验证所有 API 方法正常工作
