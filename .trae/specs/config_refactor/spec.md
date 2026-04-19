# 配置文件重构 - 产品需求文档

## Overview
- **Summary**: 重构配置文件，将API配置（api_key、secret_key、passphrase）移到.env文件，将数据库连接配置移到代码中。
- **Purpose**: 提高配置的安全性和可维护性，将敏感的API凭证放在环境变量中，将数据库连接配置集中管理。
- **Target Users**: 系统开发者和维护人员。

## Goals
- 将API配置（api_key、secret_key、passphrase）移到.env文件
- 将数据库连接配置移到代码中
- 保持配置的一致性和安全性
- 确保修改后的代码能正常工作

## Non-Goals (Out of Scope)
- 不修改其他功能模块
- 不改变配置的使用方式
- 不修改现有的API调用逻辑

## Background & Context
- 现有的API配置（api_key、secret_key、passphrase）硬编码在配置文件中，存在安全风险
- 数据库连接配置放在.env文件中，而其他配置放在代码中，导致配置分散
- 为了提高配置的安全性和可维护性，需要进行配置文件重构

## Functional Requirements
- **FR-1**: 将API配置（api_key、secret_key、passphrase）移到.env文件
- **FR-2**: 将数据库连接配置移到代码中
- **FR-3**: 确保配置的加载和使用方式保持不变

## Non-Functional Requirements
- **NFR-1**: 确保API凭证的安全性
- **NFR-2**: 确保配置的一致性和可维护性
- **NFR-3**: 确保修改后的代码能正常工作

## Constraints
- **Technical**: 只修改配置相关的代码，不影响其他模块
- **Business**: 确保修改不会影响现有功能
- **Dependencies**: 依赖现有的配置加载机制

## Assumptions
- .env文件已经存在且可读写
- 代码中的配置加载机制支持从.env文件读取配置
- 数据库连接配置的默认值是合理的

## Acceptance Criteria

### AC-1: API配置移到.env文件
- **Given**: 系统配置
- **When**: 修改配置文件后
- **Then**: API配置（api_key、secret_key、passphrase）从.env文件加载
- **Verification**: `programmatic`

### AC-2: 数据库连接配置移到代码中
- **Given**: 系统配置
- **When**: 修改配置文件后
- **Then**: 数据库连接配置从代码中加载，不再依赖.env文件
- **Verification**: `programmatic`

### AC-3: 代码正常工作
- **Given**: 修改后的代码
- **When**: 运行系统时
- **Then**: 系统能正常工作，配置加载和使用不受影响
- **Verification**: `programmatic`

## Open Questions
- [ ] 数据库连接配置的默认值是否需要调整
- [ ] 是否需要更新示例配置文件
- [ ] 是否需要添加配置验证机制
