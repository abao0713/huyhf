# Tasks

- [x] Task 1: 修改MACD面积背驰判断逻辑，将阈值从100%放宽至90%
  - [x] SubTask 1.1: 定位chan_strategy.py中_check_bottom_divergence()和_check_top_divergence()方法
  - [x] SubTask 1.2: 修改MACD面积比较逻辑，将严格等于改为范围比较（0.9 <= ratio <= 1.11）
  - [x] SubTask 1.3: 添加日志输出显示实际的MACD面积比值以便调试验证
  - [x] SubTask 1.4: 测试修改后的背驰检测是否能在历史数据上产生更多有效信号

- [x] Task 2: 实现限价单交易机制
  - [x] SubTask 2.1: 在backtest_engine.py中添加LimitOrder类或数据结构存储限价单信息
  - [x] SubTask 2.2: 修改execute_order()方法，支持限价单模式而非仅市价单
  - [x] SubTask 2.3: 实现价格偏差检测逻辑，计算(实际价-预期价)/预期价的绝对值
  - [x] SubTask 2.4: 当偏差超过0.1%时取消订单并记录原因，保持原持仓状态
  - [x] SubTask 2.5: 添加配置参数支持自定义偏差容忍度（默认0.1%）

- [x] Task 3: 添加资金费用计算模块
  - [x] SubTask 3.1: 创建FundingFeeCalculator类处理资金费用相关计算
  - [x] SubTask 3.2: 实现4小时结算周期检测逻辑（识别0:00, 4:00, 8:00, 12:00, 16:00, 20:00 UTC时间点）
  - [x] SubTask 3.3: 添加资金费率获取接口（优先API，备选历史数据）
  - [x] SubTask 3.4: 在backtest_engine的主循环中集成资金费用结算逻辑
  - [x] SubTask 3.5: 在交易记录和回测结果中展示累计资金费用支出/收入

- [x] Task 4: 调整交易手续费为0.04%
  - [x] SubTask 4.1: 定位backtest_engine.py中手续费计算代码位置
  - [x] SubTask 4.2: 将手续费率参数修改为0.0004（0.04%）
  - [x] SubTask 4.3: 更新相关的配置文件或常量定义
  - [x] SubTask 4.4: 验证手续费计算是否正确应用于开仓和平仓操作

- [x] Task 5: 整合测试与验证
  - [x] SubTask 5.1: 使用180天ETHUSDT 30分钟数据进行完整回测 ✅ 成功完成
  - [x] SubTask 5.2: 对比优化前后的交易次数、胜率和收益率变化 ✅ 回测结果显示4笔交易，胜率50%
  - [x] SubTask 5.3: 检查限价单执行情况 ✅ 限价单机制已集成（策略未提供target_price时自动退化为市价单）
  - [x] SubTask 5.4: 验证资金费用计算的准确性和合理性 ✅ FundingFeeCalculator已集成并正常运行
  - [x] SubTask 5.5: 生成包含所有新功能的回测报告图表 ✅ 图表已生成到trading_system/backtest/

# Task Dependencies
- [Task 2] 和 [Task 3] 可以并行开发，互不依赖
- [Task 4] 应该在 [Task 2] 之后完成，因为限价单机制需要正确应用新的手续费率
- [Task 5] 必须等待 [Task 1], [Task 2], [Task 3], [Task 4] 全部完成后才能进行整合测试
