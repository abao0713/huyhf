# 量化交易策略 - 产品需求文档

## Overview
- **Summary**: 开发一个基于OKX API的量化交易策略，根据一分钟行情数据的连续涨跌情况，在第五分钟进行交易并在分钟结束时平仓。
- **Purpose**: 实现一个简单的趋势跟随策略，利用短期价格走势进行交易，目标是在价格趋势明确时获取收益。
- **Target Users**: 量化交易员、投资者

## Goals
- 实现基于一分钟行情数据的趋势检测
- 根据连续4分钟的涨跌情况在第五分钟进行交易
- 在第五分钟结束时平仓
- 支持实盘和模拟盘交易
- 提供详细的交易日志和结果分析

## Non-Goals (Out of Scope)
- 不实现复杂的风险控制策略
- 不支持多市场、多品种同时交易
- 不实现自动化的参数优化
- 不提供复杂的回测功能

## Background & Context
- 该策略基于OKX交易所的API，使用WebSocket获取实时行情数据
- 策略逻辑简单明确：连续4分钟上涨则做多，连续4分钟下跌则做空，第五分钟结束平仓
- 每个交易周期为5分钟，使用1分钟K线数据进行分析

## Functional Requirements
- **FR-1**: 实时获取OKX交易所的1分钟K线数据
- **FR-2**: 分析连续4分钟的价格走势
- **FR-3**: 根据连续4分钟的涨跌情况在第五分钟开始时下单
- **FR-4**: 在第五分钟结束时平仓
- **FR-5**: 记录交易日志和结果
- **FR-6**: 支持实盘和模拟盘切换

## Non-Functional Requirements
- **NFR-1**: 策略执行延迟低，确保在分钟开始和结束时及时下单
- **NFR-2**: 系统稳定可靠，能够处理网络波动和API错误
- **NFR-3**: 日志记录详细，便于分析策略表现
- **NFR-4**: 代码结构清晰，易于维护和扩展

## Constraints
- **Technical**: 使用Python 3.7+，依赖OKX API、WebSocket、asyncio等库
- **Business**: 遵守OKX的API限速规则，避免过度请求
- **Dependencies**: 依赖OKX API的WebSocket和REST接口

## Assumptions
- 假设OKX API能够稳定提供1分钟K线数据
- 假设网络连接稳定，能够及时获取行情数据和执行交易
- 假设交易品种的流动性足够，能够快速成交

## Acceptance Criteria

### AC-1: 行情数据获取
- **Given**: 策略启动并连接到OKX WebSocket
- **When**: 订阅1分钟K线数据
- **Then**: 能够实时接收并处理1分钟K线数据
- **Verification**: `programmatic`

### AC-2: 趋势分析
- **Given**: 接收到连续的1分钟K线数据
- **When**: 分析连续4分钟的价格走势
- **Then**: 能够正确识别连续上涨或下跌的情况
- **Verification**: `programmatic`

### AC-3: 交易执行
- **Given**: 检测到连续4分钟上涨
- **When**: 第五分钟开始时
- **Then**: 执行做多交易
- **Verification**: `programmatic`

### AC-4: 平仓执行
- **Given**: 执行了做多或做空交易
- **When**: 第五分钟结束时
- **Then**: 执行平仓交易
- **Verification**: `programmatic`

### AC-5: 日志记录
- **Given**: 策略运行过程中
- **When**: 发生行情数据接收、交易执行等事件
- **Then**: 记录详细的日志信息
- **Verification**: `human-judgment`

### AC-6: 实盘和模拟盘切换
- **Given**: 配置不同的交易环境
- **When**: 启动策略
- **Then**: 能够在实盘或模拟盘环境下运行
- **Verification**: `programmatic`

## Open Questions
- [ ] 交易品种选择：默认使用BTC-USDT，是否支持其他品种？
- [ ] 交易金额：默认使用固定金额，是否支持动态计算？
- [ ] 手续费考虑：是否需要在策略中考虑手续费成本？
- [ ] 滑点考虑：是否需要在策略中考虑滑点影响？