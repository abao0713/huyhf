# 策略代码注释规范 - 产品需求文档

## Overview
- **Summary**: 为所有策略代码添加详细的中文注释，解释策略的入参条件、核心逻辑和关键概念，使代码更易于理解和维护
- **Purpose**: 降低代码学习门槛，帮助开发者快速熟悉缠论策略和其他策略的实现细节
- **Target Users**: 策略开发者、量化交易员、需要维护和修改策略代码的工程师

## Why
- 当前策略代码缺少详细注释，新成员难以快速理解策略逻辑和入参条件
- 缠论策略包含专业术语（分型、笔、线段、背驰等），需要注释解释
- 策略参数（如hg1、macd_fast、macd_slow等）的作用不明确

## What Changes
- 为`base_strategy.py`添加策略基类注释
- 为`chan_strategy.py`添加缠论策略完整注释，包括：
  - 入参说明（symbol、time_frame、hg1、macd_fast、macd_slow、macd_signal）
  - 核心数据结构（Fractal、Pen、Segment）
  - 关键方法（_find_fractals、_build_pens、_build_segments、generate_signal）
  - 背驰判断逻辑（底背驰、顶背驰）
- 为`trend_following_strategy.py`添加趋势跟随策略注释
- 为`backtest_engine.py`添加回测引擎注释
- 为`config.py`添加配置参数注释

## Impact
- Affected specs: 无
- Affected code:
  - trading_system/strategies/base_strategy.py
  - trading_system/strategies/chan_strategy.py
  - trading_system/strategies/trend_following_strategy.py
  - trading_system/strategies/backtest_engine.py
  - trading_system/strategies/config.py

## ADDED Requirements
### Requirement: 策略注释完整性
策略代码中的每个类、方法、属性和关键逻辑块都应包含中文注释

#### Scenario: 注释覆盖率
- **WHEN** 查看任意策略源文件
- **THEN** 每个公开方法都有文档字符串，每个关键逻辑都有行内注释

### Requirement: 入参条件说明
策略的初始化参数和配置参数应有清晰的中文说明

#### Scenario: 入参文档化
- **WHEN** 查看策略构造函数或配置
- **THEN** 每个参数的含义、默认值、取值范围都有说明

## MODIFIED Requirements
### Requirement: Existing Feature
无修改要求，纯新增注释

## REMOVED Requirements
### Requirement: Old Feature
无