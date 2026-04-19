# REST API接口优化 - 产品需求文档

## Overview
- **Summary**: 优化REST API接口，移除对clOrdId字段的支持，只使用ordId字段作为订单标识符，因为ordId是下单时返回的订单ID。
- **Purpose**: 简化API接口，避免字段混淆，确保只使用下单时返回的ordId作为订单标识符。
- **Target Users**: 系统开发者和交易策略开发者。

## Goals
- 移除REST API接口中对clOrdId字段的支持
- 确保所有订单查询接口只使用ordId字段
- 保持API接口的一致性和简洁性
- 确保修改后的代码能正常工作

## Non-Goals (Out of Scope)
- 不修改现有的WebSocket接口
- 不修改数据库结构
- 不修改其他功能模块

## Background & Context
- 现有系统同时支持ordId和clOrdId字段作为订单标识符
- ordId是OKX系统返回的订单ID，是下单时的唯一标识符
- clOrdId是客户端自定义的订单ID，使用较少且容易造成混淆
- 为了简化API接口，避免字段混淆，需要移除对clOrdId的支持

## Functional Requirements
- **FR-1**: 移除REST API接口中对clOrdId字段的支持
- **FR-2**: 确保所有订单查询接口只使用ordId字段
- **FR-3**: 保持API接口的一致性和简洁性

## Non-Functional Requirements
- **NFR-1**: 确保修改后的代码能正常工作
- **NFR-2**: 确保API接口的向后兼容性
- **NFR-3**: 确保代码的可读性和可维护性

## Constraints
- **Technical**: 只修改REST API相关的代码，不影响其他模块
- **Business**: 确保修改不会影响现有功能
- **Dependencies**: 依赖现有的OKX API实现

## Assumptions
- ordId是下单时返回的唯一订单标识符
- 所有订单操作都应该使用ordId作为标识符
- 移除clOrdId不会影响现有功能

## Acceptance Criteria

### AC-1: 移除clOrdId字段支持
- **Given**: REST API接口代码
- **When**: 修改代码后
- **Then**: 所有REST API接口不再支持clOrdId字段
- **Verification**: `programmatic`

### AC-2: 只使用ordId字段
- **Given**: 订单查询接口
- **When**: 调用接口时
- **Then**: 接口只接受ordId字段作为订单标识符
- **Verification**: `programmatic`

### AC-3: 代码正常工作
- **Given**: 修改后的代码
- **When**: 运行系统时
- **Then**: 系统能正常工作，订单查询功能不受影响
- **Verification**: `programmatic`

## Open Questions
- [ ] 现有代码中哪些地方使用了clOrdId字段
- [ ] 移除clOrdId是否会影响现有功能
- [ ] 是否需要更新文档和示例代码
