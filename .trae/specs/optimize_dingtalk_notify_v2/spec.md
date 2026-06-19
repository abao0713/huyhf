# 钉钉通知消息格式优化 Spec

## Why
当前钉钉通知实现已基本符合标准格式，但需要进一步优化以确保完全符合用户提供的模板要求，特别是在成功场景下也需要显示排查建议区域。

## What Changes
- 优化 `send_order_result` 方法，确保成功和失败场景都显示排查建议区域
- 统一所有通知方法的格式结构
- 确保错误信息截断逻辑正确（50字符+"..."）
- 优化状态图标映射和状态文本显示

## Impact
- Affected specs: optimize_dingtalk_notify（已完成的spec）
- Affected code:
  - `e:\Auto_test\huyhf\trading_system\notify\dingtalk.py`（主要修改文件）

## MODIFIED Requirements

### Requirement: send_order_result 完全符合标准格式
系统 SHALL 严格按照用户提供的模板生成订单结果通知，格式如下：

```
### 📈 币安合约交易信号

> **状态**: [状态图标] **[状态文本]**

**🔹 交易参数**
- 交易对: `[symbol]`
- 方向: `[side]`
- 类型: `[type]`
- 数量: `[quantity]`
- 价格: `[price]` (市价单显示"市价")

**🔸 返回详情**
- 错误码: `[error_code]` (成功时"N/A")
- 错误信息: `[error_msg]` (成功时"N/A"，超过50字符截断+"...")
- 订单ID: `[order_id]` (失败时"None")

**💡 排查建议**
[根据错误码智能推荐，成功时显示"无"]

---
*节点: [环境信息] | 时间: [YYYY-MM-DD HH:MM:SS]*
```

#### Scenario: 下单成功
- **WHEN** 订单执行成功（无 error 字段）
- **THEN** 状态显示 "✅ 已挂单" 或 "✅ 已成交" 或 "✅ 下单成功"
- **THEN** 错误码显示 "N/A"
- **THEN** 错误信息显示 "N/A"
- **THEN** 订单ID显示实际订单号
- **THEN** 排查建议显示 "无"

#### Scenario: 下单失败带错误码
- **WHEN** 订单执行失败，result 包含 error 字段
- **THEN** 状态显示 "❌ 下单失败"
- **THEN** 错误码显示实际错误码（从错误信息中提取）
- **THEN** 错误信息显示截断后的错误信息（最多50字符+"..."）
- **THEN** 订单ID显示 "None"
- **THEN** 排查建议根据错误码智能推荐

#### Scenario: 部分成交
- **WHEN** 订单部分成交（status == "PARTIALLY_FILLED"）
- **THEN** 状态显示 "⚠️ 部分成交"
- **THEN** 其他字段正常显示

### Requirement: 状态图标映射
系统 SHALL 使用以下状态图标映射：
- 成功（NEW/FILLED）: ✅
- 失败（有error）: ❌
- 部分成交（PARTIALLY_FILLED）: ⚠️

### Requirement: 错误码知识库完整性
系统 SHALL 内置以下错误码映射：
- **-1021**: 时间戳超出接收窗口 → 校准系统时间/NTP服务/服务器时间动态校准
- **-1109**: API Key与环境不匹配 → 检查base_path配置/确认Key环境
- **-2015**: 权限不足 → 检查API Key权限/重新配置/确认未禁用
- **-2019**: 保证金不足 → 检查余额/降低杠杆/调整资金管理
- **-2022**: 价格超出范围 → 检查价格合理性/参考市场价格/检查PRICE_FILTER
- **其他**: 通用建议 → 检查网络/核对参数/查阅API文档

### Requirement: 环境信息和时间戳格式
系统 SHALL 在消息页脚显示：
- 节点: [环境信息]（从 `env_info` 参数获取）
- 时间: [YYYY-MM-DD HH:MM:SS]（当前系统时间）

## Verification Requirements

### 验证场景1: 成功下单
- **输入**: 
  ```python
  result = {
      "status": "NEW",
      "side": "BUY",
      "type": "LIMIT",
      "origQty": "0.001",
      "price": "60000",
      "orderId": 123456
  }
  symbol = "BTCUSDT"
  ```
- **预期输出**: 
  ```
  ### 📈 币安合约交易信号

  > **状态**: ✅ **已挂单**

  **🔹 交易参数**
  - 交易对: `BTCUSDT`
  - 方向: `BUY`
  - 类型: `LIMIT`
  - 数量: `0.001`
  - 价格: `60000`

  **🔸 返回详情**
  - 错误码: `N/A`
  - 错误信息: `N/A`
  - 订单ID: `123456`

  **💡 排查建议**
  无

  ---
  *节点: 生产环境 | 时间: 2026-06-14 11:30:45*
  ```

### 验证场景2: 失败下单（时间戳错误）
- **输入**: 
  ```python
  result = {
      "error": "(-1021, 'Timestamp for this request is outside of the recvWindow.')",
      "side": "BUY",
      "type": "LIMIT",
      "origQty": "0.001",
      "price": "60000"
  }
  symbol = "BTCUSDT"
  ```
- **预期输出**:
  ```
  ### 📈 币安合约交易信号

  > **状态**: ❌ **下单失败**

  **🔹 交易参数**
  - 交易对: `BTCUSDT`
  - 方向: `BUY`
  - 类型: `LIMIT`
  - 数量: `0.001`
  - 价格: `60000`

  **🔸 返回详情**
  - 错误码: `-1021`
  - 错误信息: `Timestamp for this request is outside of the rec...`
  - 订单ID: `None`

  **💡 排查建议**
  1. 离线环境时间漂移，请手动校准系统时间至北京时间
  2. 在代码中引入服务器时间动态校准逻辑
  3. 检查系统NTP服务是否正常运行

  ---
  *节点: 生产环境 | 时间: 2026-06-14 11:30:45*
  ```
