# ETHUSDC 5分钟级别回测 - 产品需求文档

## Overview
- **Summary**: 针对ETHUSDC交易对进行今日5分钟级别的K线数据回测，验证策略收益率
- **Purpose**: 评估策略在ETHUSDC交易对上的表现，特别是今日5分钟级别的短期交易机会
- **Target Users**: 交易策略开发者和量化交易员

## Goals
- 下载ETHUSDC交易对今日的5分钟K线数据
- 使用现有策略引擎对数据进行回测
- 计算并验证回测收益率和其他关键指标
- 生成详细的回测报告

## Non-Goals (Out of Scope)
- 不修改现有策略逻辑
- 不进行多周期或多交易对的回测
- 不优化策略参数
- 不考虑其他时间周期的回测

## Background & Context
- 现有回测系统已经支持BTCUSDT等交易对的回测
- 系统使用OKX API获取K线数据
- 回测引擎支持5分钟级别的数据处理
- 今日日期为2026-04-25

## Functional Requirements
- **FR-1**: 下载ETHUSDC交易对今日（2026-04-25）的5分钟K线数据
- **FR-2**: 下载ETHUSDC交易对今日（2026-04-25）的日线K线数据（用于策略计算）
- **FR-3**: 使用现有策略引擎对ETHUSDC 5分钟K线数据进行回测
- **FR-4**: 计算并输出回测收益率和其他关键指标
- **FR-5**: 保存回测结果到JSON文件

## Non-Functional Requirements
- **NFR-1**: 数据下载过程应在10秒内完成
- **NFR-2**: 回测过程应在5秒内完成
- **NFR-3**: 回测结果应包含完整的交易记录和绩效指标

## Constraints
- **Technical**: 使用现有回测系统架构，不修改核心代码
- **Business**: 仅针对今日数据进行回测，不涉及历史数据
- **Dependencies**: 依赖OKX API获取K线数据

## Assumptions
- OKX API可以正常访问并返回ETHUSDC的K线数据
- 现有策略引擎可以正确处理ETHUSDC的K线数据
- 今日（2026-04-25）的K线数据已经可用

## Acceptance Criteria

### AC-1: 数据下载完成
- **Given**: 系统配置正确，网络连接正常
- **When**: 执行数据下载操作
- **Then**: 成功下载ETHUSDC今日的5分钟和日线K线数据
- **Verification**: `programmatic`
- **Notes**: 数据应保存为CSV文件

### AC-2: 回测执行成功
- **Given**: 数据下载完成，策略配置正确
- **When**: 执行回测操作
- **Then**: 回测引擎成功运行并生成结果
- **Verification**: `programmatic`

### AC-3: 收益率计算准确
- **Given**: 回测执行成功
- **When**: 查看回测结果
- **Then**: 结果中包含总收益率、净利润等关键指标
- **Verification**: `programmatic`

### AC-4: 回测报告完整
- **Given**: 回测执行成功
- **When**: 查看回测结果文件
- **Then**: JSON文件包含完整的回测数据，包括交易记录、权益曲线等
- **Verification**: `human-judgment`

## Open Questions
- [ ] OKX API是否需要特殊配置才能获取ETHUSDC的K线数据？
- [ ] 现有策略是否针对ETHUSDC交易对进行过优化？
- [ ] 今日数据的具体时间范围是什么（从00:00到当前时间）？