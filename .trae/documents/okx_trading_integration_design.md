# OKX与Trading System整合设计方案

## 1. 数据映射关系

### OKX下单参数到TradingOrder的映射

| OKX参数 | TradingOrder字段 | 映射规则 |
|---------|----------------|----------|
| instId | symbol | 直接映射，如"BTC-USDT" |
| side | side | 直接映射，"buy"→"buy"，"sell"→"sell" |
| ordType | order_type | market→1，limit→2，stop→3 |
| sz | quantity | 直接映射 |
| price | price | 限价单时映射，市价单为null |
| clOrdId | remark | 存储为备注 |
| tdMode | remark | 存储为备注 |
| 其他参数 | remark | 存储为JSON字符串 |

### OKX订单响应到TradeRecord的映射

| OKX响应字段 | TradeRecord字段 | 映射规则 |
|------------|----------------|----------|
| ordId | - | 存储在TradingOrder的remark中 |
| ts | trade_time | 转换为datetime |
| sCode | - | 存储在TradingOrder的remark中 |
| sMsg | - | 存储在TradingOrder的remark中 |

## 2. 日志系统整合

### 统一日志配置
- 修改OKX模块，使用主项目的log_config.py
- 移除OKX内部的logging配置
- 确保所有组件使用相同的日志级别和格式

### 日志输出格式
- 保持现有格式：`%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- 确保所有模块使用相同的日期格式

## 3. 代码结构调整

### 推荐结构
```
├── trading_system/       # 主项目
│   ├── api/             # API层
│   ├── core/            # 核心配置
│   ├── models/          # 数据库模型
│   ├── services/        # 业务逻辑
│   └── okx/             # OKX模块（整合到主项目）
│       ├── websocket/    # WebSocket客户端
│       ├── utils/        # 工具类
│       ├── api.py        # OKX API封装
│       └── config.py     # OKX配置
├── main.py              # 项目主入口
├── log_config.py        # 统一日志配置
└── requirements.txt     # 依赖文件
```

### 导入路径调整
- OKX模块内的导入使用相对导入
- 主项目导入OKX使用 `from trading_system.okx import ...`

## 4. 实现方案

### 数据记录流程
1. OKX API下单成功后，获取订单响应
2. 转换OKX下单数据为TradingOrder模型
3. 保存到数据库
4. 监听OKX订单状态更新
5. 当订单成交时，创建TradeRecord记录

### 事务处理
- 使用数据库事务确保数据一致性
- 处理异步操作和数据库操作的协调

### 错误处理
- 确保数据库操作失败时的回滚机制
- 记录详细的错误日志

## 5. 测试计划

### 单元测试
- 测试数据映射逻辑
- 测试日志系统整合
- 测试代码结构调整

### 集成测试
- 测试完整的下单流程
- 测试数据记录到数据库
- 测试日志输出

### 性能测试
- 测试并发下单时的数据记录性能
- 测试日志系统的性能影响
