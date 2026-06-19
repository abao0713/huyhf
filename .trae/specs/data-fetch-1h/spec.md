# 1H数据获取规范 - 与4H数据获取逻辑保持一致

## Overview
- **Summary**: 确保1H K线数据的获取方式与4H数据完全一致，支持从本地CSV文件加载和通过CCXT从Binance API获取两种方式
- **Purpose**: 解决回测时1H数据缺失的问题，确保多周期策略能够正常运行
- **Target Users**: 回测系统和实盘交易系统

## Goals
- 确保1H数据与4H数据使用相同的获取逻辑
- 支持本地CSV加载和CCXT API获取两种方式
- 保证数据格式一致（时间戳、列名、数据类型）

## Non-Goals (Out of Scope)
- 不修改核心策略逻辑
- 不改变数据处理流程

## Background & Context
- 回测系统需要4H/1H/15M/1D多周期数据
- 现有代码已经支持通过CCXT获取1H数据
- 本地CSV文件 `ETHUSDC_1h.csv` 之前缺失，现已生成

## Functional Requirements
- **FR-1**: 1H数据获取逻辑与4H数据完全一致
- **FR-2**: 支持从本地CSV文件加载1H数据
- **FR-3**: 支持通过CCXT从Binance获取1H数据
- **FR-4**: 1H数据格式与4H数据一致

## Non-Functional Requirements
- **NFR-1**: 数据加载失败时记录警告日志但不中断程序
- **NFR-2**: 数据格式验证确保一致性

## Constraints
- **Technical**: 依赖 `CCXTDataProvider` 和 `MarketDataClient`
- **Dependencies**: 需要网络连接（CCXT模式）或本地CSV文件（文件模式）

## Assumptions
- `ETHUSDC_1h.csv` 文件存在于 `trading_system/data/binance_history/`
- CCXT库已安装且配置正确

## Acceptance Criteria

### AC-1: 1H数据CSV加载成功
- **Given**: `ETHUSDC_1h.csv` 文件存在于数据目录
- **When**: 调用 `load_csv_data` 函数
- **Then**: 成功加载1H数据，无警告日志
- **Verification**: `programmatic`

### AC-2: 1H数据CCXT获取成功
- **Given**: 网络连接正常，CCXT配置正确
- **When**: 调用 `load_ccxt_data` 函数
- **Then**: 成功从Binance获取1H数据
- **Verification**: `programmatic`

### AC-3: 数据格式一致性
- **Given**: 已加载4H和1H数据
- **When**: 检查DataFrame结构
- **Then**: 1H数据与4H数据具有相同的列名和数据类型
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要添加数据格式验证功能？