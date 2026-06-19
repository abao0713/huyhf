# 钉钉通知消息格式优化 Spec

## Why
当前钉钉通知消息格式简陋，缺少交易参数详情、错误码诊断和排查建议，不利于快速定位交易问题。需要按照"标准交易通知型"格式重构所有通知方法。

## What Changes
- 重构 `send_order_result` 方法，采用标准交易通知格式（状态引用块 + 交易参数 + 返回详情 + 排查建议 + 页脚）
- 重构 `send_trade_signal` 方法，统一消息格式风格
- 重构 `send_error` 方法，增加排查建议
- 重构 `send_status` 方法，统一消息格式风格
- 新增错误码知识库 `_get_error_suggestions`，根据错误码智能推荐解决方案
- 新增环境信息支持，`__init__` 接受 `env_info` 参数
- 新增状态图标映射逻辑

## Impact
- Affected specs: 无
- Affected code:
  - `e:\Auto_test\huyhf\trading_system\notify\dingtalk.py`（主要修改文件）
  - `e:\Auto_test\huyhf\run_crypto_chan_live.py`（调用方，需传入 env_info）

## MODIFIED Requirements

### Requirement: send_order_result 标准交易通知格式
系统 SHALL 按照以下格式生成订单结果通知：

```
### 📈 币安合约交易信号

> **状态**: [状态图标] **[状态文本]**

**🔹 交易参数**
- 交易对: `[symbol]`
- 方向: `[side]`
- 类型: `[type]`
- 数量: `[quantity]`
- 价格: `[price]`（市价单显示"市价"）

**🔸 返回详情**
- 错误码: `[error_code]`（成功时"N/A"）
- 错误信息: `[error_msg]`（成功时"N/A"，超过50字符截断+"..."）
- 订单ID: `[order_id]`（失败时"None"）

**💡 排查建议**
[根据错误码智能推荐]

---
*节点: [env_info] | 时间: [YYYY-MM-DD HH:MM:SS]*
```

#### Scenario: 下单成功
- **WHEN** 订单执行成功（无 error 字段）
- **THEN** 状态显示 "✅ 下单成功"，错误码/错误信息显示 "N/A"，无排查建议

#### Scenario: 下单失败带错误码
- **WHEN** 订单执行失败，result 包含 error_code
- **THEN** 状态显示 "❌ 下单失败"，展示错误码和截断的错误信息，显示对应排查建议

### Requirement: 错误码知识库
系统 SHALL 内置以下错误码映射：
- **-1021**: 时间漂移 → 校准系统时间/NTP服务
- **-1109**: API Key与环境不匹配 → 检查 base_path 配置
- **-2015**: 权限不足 → 检查 API Key 权限
- **-2019**: 保证金不足 → 检查余额/降低杠杆
- **-2022**: 价格超出范围 → 检查价格合理性
- **其他**: 通用建议（网络/参数/API文档）

### Requirement: send_trade_signal 统一格式
系统 SHALL 使用统一的引用块 + 分区格式发送策略信号通知。

### Requirement: send_error 增加排查建议
系统 SHALL 在运行异常通知中包含排查建议。

### Requirement: send_status 统一格式
系统 SHALL 在策略启动/停止/风控通知中使用统一格式风格。

### Requirement: 环境信息支持
系统 SHALL 支持在 `__init__` 中传入 `env_info` 参数，用于消息页脚显示运行环境。
