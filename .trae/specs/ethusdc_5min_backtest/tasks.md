# ETHUSDC 5分钟级别K线回测 - 实现计划

## [ ] Task 1: 扩展数据获取功能，支持5分钟级别
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 修改backtest_data.py，添加对5分钟（5m）时间级别的支持
  - 确保能够获取ETHUSDC交易对的5分钟K线数据
  - 实现今日数据的获取逻辑
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-1.1: 成功获取ETHUSDC的5分钟K线数据
  - `programmatic` TR-1.2: 数据格式正确，包含所有必要字段
- **Notes**: 确保数据获取脚本能够正确处理5分钟级别的数据请求

## [ ] Task 2: 调整缠论策略参数，适应5分钟级别
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 修改ChanStrategy类，添加对5分钟级别的参数支持
  - 调整hg1参数以适应5分钟级别的分型识别
  - 确保策略能够正确处理5分钟K线数据
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-2.1: 策略能够正确加载5分钟K线数据
  - `programmatic` TR-2.2: 策略能够识别5分钟级别的分型和笔
- **Notes**: 5分钟级别的hg1参数可能需要设置为3或4以获得更好的信号生成

## [ ] Task 3: 执行ETHUSDC 5分钟级别回测
- **Priority**: P1
- **Depends On**: Task 2
- **Description**:
  - 修改回测脚本，支持ETHUSDC交易对
  - 配置回测参数，使用5分钟级别数据
  - 执行回测并收集结果
- **Acceptance Criteria Addressed**: AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 回测执行完成，无错误
  - `programmatic` TR-3.2: 收益率计算准确
- **Notes**: 确保回测引擎能够正确处理5分钟级别的数据

## [ ] Task 4: 生成回测报告和可视化结果
- **Priority**: P1
- **Depends On**: Task 3
- **Description**:
  - 生成包含收益率的回测报告
  - 创建权益曲线、收益率曲线和回撤曲线
  - 计算并展示关键绩效指标
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `human-judgment` TR-4.1: 报告包含所有必要的绩效指标
  - `human-judgment` TR-4.2: 图表清晰，易于理解
- **Notes**: 确保报告格式与现有的BTCUSDT回测报告一致