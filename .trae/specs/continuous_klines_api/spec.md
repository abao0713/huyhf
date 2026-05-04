# 永续合约K线接口 - 产品需求文档

## Overview
- **Summary**: 新增 `/fapi/v1/continuousKlines` REST API接口，用于获取永续合约的K线数据
- **Purpose**: 提供永续合约的K线数据查询功能，支持不同合约类型和时间间隔
- **Target Users**: 量化交易策略、数据分析工具、前端图表展示

## Goals
- 实现永续合约K线数据查询接口
- 支持多种时间间隔和合约类型
- 提供完整的参数验证和错误处理
- 与现有API架构保持一致

## Non-Goals (Out of Scope)
- 实时WebSocket推送
- 历史数据导出
- 自定义时间间隔
- 数据缓存

## Background & Context
- 基于Binance Futures API设计
- 集成到现有的FastAPI框架中
- 与现有的市场数据获取模块集成

## Functional Requirements
- **FR-1**: 实现 GET /fapi/v1/continuousKlines 接口
- **FR-2**: 支持必需参数：pair, contractType, interval
- **FR-3**: 支持可选参数：startTime, endTime, limit
- **FR-4**: 实现参数验证和错误处理
- **FR-5**: 与市场数据获取模块集成，返回格式化的K线数据

## Non-Functional Requirements
- **NFR-1**: 响应时间 < 1000ms
- **NFR-2**: 错误率 < 1%
- **NFR-3**: 支持CORS跨域请求
- **NFR-4**: 符合REST API设计规范

## Constraints
- **Technical**: FastAPI框架，Python 3.7+
- **Dependencies**: Binance API, pandas
- **Rate Limit**: 遵循Binance API rate limit

## Assumptions
- 市场数据获取模块已实现并可用
- Binance API访问权限已配置
- 网络连接稳定

## Acceptance Criteria

### AC-1: 接口基本功能
- **Given**: 系统正常运行
- **When**: 发送GET请求到 /fapi/v1/continuousKlines 并提供必需参数
- **Then**: 返回200状态码和K线数据
- **Verification**: `programmatic`

### AC-2: 参数验证
- **Given**: 缺少必需参数
- **When**: 发送GET请求到 /fapi/v1/continuousKlines 缺少pair参数
- **Then**: 返回400状态码和错误信息
- **Verification**: `programmatic`

### AC-3: 数据格式
- **Given**: 接口正常响应
- **When**: 接收响应数据
- **Then**: 数据格式符合Binance API规范，包含open_time, open, high, low, close, volume等字段
- **Verification**: `programmatic`

### AC-4: 时间范围
- **Given**: 提供startTime和endTime参数
- **When**: 发送GET请求
- **Then**: 返回指定时间范围内的K线数据
- **Verification**: `programmatic`

### AC-5: 错误处理
- **Given**: 无效的参数值
- **When**: 发送GET请求使用无效的contractType
- **Then**: 返回400状态码和错误信息
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要支持分页？
- [ ] 是否需要添加缓存机制？
- [ ] 错误信息的具体格式？