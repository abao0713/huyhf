# Tasks

- [x] Task 1: 重构 send_order_result 方法为标准交易通知格式
  - [x] SubTask 1.1: 添加状态引用块和状态图标映射逻辑
  - [x] SubTask 1.2: 实现交易参数分区（交易对/方向/类型/数量/价格）
  - [x] SubTask 1.3: 实现返回详情分区（错误码/错误信息/订单ID）
  - [x] SubTask 1.4: 添加错误信息截断逻辑（50字符+"..."）
  - [x] SubTask 1.5: 添加页脚（环境信息 + 时间）

- [x] Task 2: 新增错误码知识库方法 _get_error_suggestions
  - [x] SubTask 2.1: 实现错误码映射字典（-1021/-1109/-2015/-2019/-2022）
  - [x] SubTask 2.2: 实现智能建议生成逻辑
  - [x] SubTask 2.3: 添加通用建议兜底

- [x] Task 3: 重构 send_trade_signal 方法
  - [x] SubTask 3.1: 统一使用引用块 + 分区格式
  - [x] SubTask 3.2: 添加策略信号专用字段（信号类型/仓位比例/入场价/止损价/原因）
  - [x] SubTask 3.3: 添加页脚

- [x] Task 4: 重构 send_error 方法
  - [x] SubTask 4.1: 统一消息格式
  - [x] SubTask 4.2: 添加排查建议分区

- [x] Task 5: 重构 send_status 方法
  - [x] SubTask 5.1: 统一策略启动/停止/风控通知格式
  - [x] SubTask 5.2: 添加页脚

- [x] Task 6: 添加环境信息支持
  - [x] SubTask 6.1: 在 __init__ 中添加 env_info 参数
  - [x] SubTask 6.2: 存储 env_info 为实例属性

- [x] Task 7: 验证所有通知方法格式正确性
  - [x] SubTask 7.1: 测试 send_order_result 成功场景
  - [x] SubTask 7.2: 测试 send_order_result 失败场景（带错误码）
  - [x] SubTask 7.3: 测试其他通知方法格式一致性
