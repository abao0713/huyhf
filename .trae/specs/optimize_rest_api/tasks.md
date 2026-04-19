# REST API接口优化 - 实现计划

## [ ] Task 1: 分析现有代码
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 分析现有REST API代码，找出使用clOrdId字段的地方
  - 确认需要修改的文件和代码位置
  - 评估移除clOrdId的影响
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - `human-judgment` TR-1.1: 详细分析报告
- **Notes**: 重点关注订单查询相关的代码

## [ ] Task 2: 移除REST API接口中对clOrdId的支持
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 修改REST API客户端，移除对clOrdId字段的支持
  - 确保所有订单查询接口只使用ordId字段
  - 更新相关的方法参数和文档
- **Acceptance Criteria Addressed**: AC-1, AC-2
- **Test Requirements**:
  - `programmatic` TR-2.1: 移除clOrdId字段支持
  - `programmatic` TR-2.2: 只使用ordId字段
- **Notes**: 确保修改后的代码能正常工作

## [x] Task 3: 测试和验证
- **Priority**: P1
- **Depends On**: Task 2
- **Description**:
  - 测试修改后的REST API接口
  - 验证订单查询功能是否正常
  - 确保移除clOrdId不会影响现有功能
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 代码正常工作测试
  - `programmatic` TR-3.2: 订单查询功能测试
- **Notes**: 确保所有测试场景覆盖完整

**实现结果**:
- 现有的REST API客户端已经只使用ordId字段，没有使用clOrdId字段
- 订单查询功能正常工作
- 移除clOrdId不会影响现有功能
