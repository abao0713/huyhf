# 订单状态查询REST API - 产品需求文档

## Overview
- **Summary**: 实现REST API接口用于查询WebSocket下单和批量下单的订单状态，特别关注订单完全成交的状态标识（state=fill）。
- **Purpose**: 提供一种可靠的方式来查询订单的实时状态，确保订单操作的完整性和可追踪性。
- **Target Users**: 系统开发者和交易策略开发者。

## Goals
- 提供订单状态查询接口，支持单个订单和批量订单的状态查询
- 确保订单状态查询的实时性和准确性
- 特别标识订单完全成交的状态（state=fill）
- 与现有的WebSocket下单和批量下单功能无缝集成

## Non-Goals (Out of Scope)
- 不修改现有的WebSocket下单和批量下单功能
- 不实现订单历史查询功能
- 不提供订单状态的实时推送

## Background & Context
- 现有系统已经实现了基于WebSocket的下单和批量下单功能
- 为了确保订单操作的完整性，需要一种可靠的方式来查询订单的状态
- 特别是需要明确标识订单完全成交的状态，以便交易策略能够及时响应

## Functional Requirements
- **FR-1**: 提供单个订单状态查询接口，支持通过订单ID和交易对查询订单状态
- **FR-2**: 提供批量订单状态查询接口，支持通过多个订单ID和交易对查询订单状态
- **FR-3**: 确保订单状态查询的响应包含完整的订单信息，包括成交价格、成交量、手续费等
- **FR-4**: 特别标识订单完全成交的状态（state=fill）

## Non-Functional Requirements
- **NFR-1**: 订单状态查询接口的响应时间不超过500ms
- **NFR-2**: 接口的可用性不低于99.9%
- **NFR-3**: 接口的错误处理机制完善，提供清晰的错误信息
- **NFR-4**: 接口的日志记录完整，便于问题排查

## Constraints
- **Technical**: 基于OKX官方REST API实现，遵循OKX API的规范和限制
- **Business**: 接口调用需要遵循OKX的API限速规则
- **Dependencies**: 依赖OKX官方REST API和现有的认证机制

## Assumptions
- OKX REST API的订单状态查询接口是可用的
- 系统已经正确配置了OKX API的凭证
- 订单ID和交易对参数是正确的

## Acceptance Criteria

### AC-1: 单个订单状态查询
- **Given**: 系统已初始化并登录OKX
- **When**: 调用单个订单状态查询接口
- **Then**: 接口返回订单的详细状态信息，包括state字段
- **Verification**: `programmatic`
- **Notes**: 订单状态为"filled"表示完全成交

### AC-2: 批量订单状态查询
- **Given**: 系统已初始化并登录OKX
- **When**: 调用批量订单状态查询接口
- **Then**: 接口返回多个订单的详细状态信息，每个订单都包含state字段
- **Verification**: `programmatic`

### AC-3: 订单完全成交状态标识
- **Given**: 订单已完全成交
- **When**: 查询订单状态
- **Then**: 接口返回的state字段值为"filled"
- **Verification**: `programmatic`

### AC-4: 接口响应时间
- **Given**: 网络环境正常
- **When**: 调用订单状态查询接口
- **Then**: 接口响应时间不超过500ms
- **Verification**: `programmatic`

### AC-5: 错误处理
- **Given**: 提供无效的订单ID或交易对
- **When**: 调用订单状态查询接口
- **Then**: 接口返回清晰的错误信息
- **Verification**: `programmatic`

## Open Questions
- [ ] OKX API的订单状态字段是否有其他可能的值，需要完整支持
- [ ] 是否需要对订单状态进行本地化处理，以便更方便地使用
- [ ] 批量订单查询的最大订单数量限制是多少
