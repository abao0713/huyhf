# 配置文件重构 - 实现计划

## [ ] Task 1: 分析现有配置结构
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 分析现有的配置文件结构
  - 确认API配置和数据库连接配置的位置
  - 评估修改的影响
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - `human-judgment` TR-1.1: 详细分析报告
- **Notes**: 重点关注配置加载机制

## [ ] Task 2: 将API配置移到.env文件
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 修改.env文件，添加API配置（api_key、secret_key、passphrase）
  - 确保OKX配置类能从.env文件加载这些配置
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-2.1: API配置从.env文件加载
  - `programmatic` TR-2.2: 配置加载正常
- **Notes**: 确保.env文件中的配置格式正确

## [ ] Task 3: 将数据库连接配置移到代码中
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 修改数据库配置文件，将数据库连接配置移到代码中
  - 移除.env文件中的数据库连接配置
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-3.1: 数据库连接配置从代码中加载
  - `programmatic` TR-3.2: 数据库连接正常
- **Notes**: 确保数据库连接配置的默认值合理

## [x] Task 4: 测试和验证
- **Priority**: P1
- **Depends On**: Task 2, Task 3
- **Description**:
  - 测试修改后的配置加载
  - 验证系统能正常工作
  - 确保API配置和数据库连接配置都能正确加载
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-4.1: 代码正常工作测试
  - `programmatic` TR-4.2: 配置加载测试
- **Notes**: 确保所有测试场景覆盖完整

**实现结果**:
- 测试脚本运行成功
- 数据库连接配置已成功移到代码中
- .env文件中的OKX配置已添加
- OKX配置类已支持从.env文件加载配置
- 系统能正常工作
