# 去除冗余代码和目录 - 产品需求文档

## Overview
- **Summary**: 清理项目中的冗余代码和目录，包括旧的OKX模块、根目录下的旧Python文件、编译缓存目录和临时测试文件，以保持项目结构的整洁和可维护性。
- **Purpose**: 减少项目中的冗余文件，提高代码的可维护性，避免代码重复和混淆。
- **Target Users**: 系统开发者和维护人员。

## Goals
- 移除根目录下的旧Python文件，这些文件已被trading_system目录中的对应文件替代
- 移除根目录下的okx/目录，因为它已被整合到trading_system/okx/目录
- 移除编译缓存目录(__pycache__/)，减少项目体积
- 移除临时测试文件，保持项目的整洁

## Non-Goals (Out of Scope)
- 修改任何功能代码
- 重命名或移动必要的文件
- 修改配置文件和依赖文件

## Background & Context
- 项目已经整合了OKX模块到trading_system/okx/目录
- 根目录下的Python文件已经被trading_system目录中的对应文件替代
- 编译缓存目录和临时测试文件占用了不必要的空间

## Functional Requirements
- **FR-1**: 移除根目录下的旧Python文件
- **FR-2**: 移除根目录下的okx/目录
- **FR-3**: 移除所有__pycache__目录
- **FR-4**: 移除临时测试文件

## Non-Functional Requirements
- **NFR-1**: 保持项目的功能完整性
- **NFR-2**: 保持项目的配置文件和依赖文件不变
- **NFR-3**: 确保移除操作不会影响项目的正常运行

## Constraints
- **Technical**: 只删除明确冗余的文件和目录，不修改任何功能代码
- **Business**: 确保项目在清理后仍能正常运行

## Assumptions
- trading_system目录中的文件已经完全替代了根目录下的旧文件
- trading_system/okx/目录已经完全替代了根目录下的okx/目录
- 编译缓存目录和临时测试文件可以安全删除

## Acceptance Criteria

### AC-1: 根目录旧文件已移除
- **Given**: 项目根目录
- **When**: 执行清理操作后
- **Then**: 根目录下的旧Python文件（config.py, crud.py, database.py, models.py, routers.py, schemas.py）已被移除
- **Verification**: `programmatic`

### AC-2: 旧okx目录已移除
- **Given**: 项目根目录
- **When**: 执行清理操作后
- **Then**: 根目录下的okx/目录已被移除
- **Verification**: `programmatic`

### AC-3: 编译缓存目录已移除
- **Given**: 项目目录
- **When**: 执行清理操作后
- **Then**: 所有__pycache__目录已被移除
- **Verification**: `programmatic`

### AC-4: 临时测试文件已移除
- **Given**: 项目根目录
- **When**: 执行清理操作后
- **Then**: 临时测试文件（test_log_config.py, test_logging.py）已被移除
- **Verification**: `programmatic`

### AC-5: 项目功能完整性保持
- **Given**: 清理后的项目
- **When**: 运行项目时
- **Then**: 项目功能正常，没有因清理操作而出现错误
- **Verification**: `human-judgment`

## Open Questions
- [ ] 确认根目录下的所有旧Python文件确实已被trading_system目录中的对应文件完全替代
- [ ] 确认根目录下的okx/目录确实已被trading_system/okx/目录完全替代
