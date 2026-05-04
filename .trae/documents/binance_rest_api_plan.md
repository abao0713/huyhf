# Binance REST API SPI 实现计划

## 任务概述
参考Binance官方文档，实现REST API SPI功能，封装成方法，适配MySQL数据库入库和日志系统。

## 参考文档
- Binance Derivatives Trading USDⓈ-Margined Futures REST APIs
- 文档链接：https://github.com/binance/binance-connector-python/tree/master/clients/derivatives_trading_usds_futures#rest-apis

## 项目结构
```
trading_system/
├── okx/                          # Binance模块（重命名）
│   ├── __init__.py
│   ├── config.py                 # Binance配置
│   ├── signer.py                 # 签名生成器
│   └── client.py                 # REST API客户端
├── models/                       # 数据模型
│   ├── trading_order.py          # 交易订单表
│   ├── trade_record.py           # 成交记录表
│   └── position.py               # 持仓表
├── services/
│   └── crud.py                   # 数据库CRUD操作
├── api/
│   └── main.py                   # FastAPI应用
└── strategies/
    └── trend_following_strategy.py  # 交易策略
```

## 实现步骤

### 步骤 1: 创建Binance配置模块
**文件**: `trading_system/okx/config.py`
- 从环境变量加载API凭证
- 配置REST API基础URL
- 支持模拟盘/实盘切换

### 步骤 2: 实现签名器
**文件**: `trading_system/okx/signer.py`
- HMAC SHA256签名算法
- 签名请求参数处理
- 时间戳生成

### 步骤 3: 实现REST API客户端
**文件**: `trading_system/okx/client.py`
- 异步HTTP请求处理
- 身份验证头生成
- 主要API方法封装:
  - `place_order()` - 下单
  - `get_order()` - 查询订单
  - `cancel_order()` - 取消订单
  - `get_account()` - 获取账户信息
  - `get_positions()` - 获取持仓信息

### 步骤 4: 实现数据映射层
**文件**: `trading_system/okx/mapper.py` (新建)
- Binance订单数据 -> TradingOrder模型映射
- Binance成交数据 -> TradeRecord模型映射
- Binance持仓数据 -> Position模型映射
- 数据类型转换（字符串 -> 枚举等）

### 步骤 5: 实现数据库适配层
**文件**: `trading_system/okx/database_adapter.py` (新建)
- 订单数据入库
- 成交记录入库
- 持仓更新
- 事务管理
- 错误处理和回滚

### 步骤 6: 实现统一日志集成
**文件**: `trading_system/okx/logger.py` (新建)
- 统一使用log_config.py的logger
- 请求/响应日志记录
- 错误日志标记
- 性能日志

### 步骤 7: 创建测试脚本
**文件**: `test_binance_order.py` (新建)
- 测试下单功能
- 测试订单查询
- 测试数据库记录

## API方法详细设计

### 1. place_order() - 下单方法
```python
async def place_order(
    symbol: str,           # 交易对，如 "BTCUSDT"
    side: str,            # 买入或卖出 "BUY" / "SELL"
    position_side: str,    # 持仓方向 "LONG" / "SHORT"
    order_type: str,       # 订单类型 "LIMIT" / "MARKET"
    quantity: float,       # 数量
    price: float = None,   # 价格（限价单必需）
    time_in_force: str = "GTC"  # 有效期限
) -> Dict[str, Any]
```

### 2. get_order() - 查询订单方法
```python
async def get_order(
    symbol: str,
    order_id: int = None,
    orig_client_order_id: str = None
) -> Dict[str, Any]
```

### 3. cancel_order() - 取消订单方法
```python
async def cancel_order(
    symbol: str,
    order_id: int = None,
    orig_client_order_id: str = None
) -> Dict[str, Any]
```

### 4. get_account() - 获取账户信息
```python
async def get_account() -> Dict[str, Any]
```

### 5. get_positions() - 获取持仓信息
```python
async def get_positions() -> List[Dict[str, Any]]
```

## 数据库映射规则

### TradingOrder表字段映射
| Binance字段 | TradingOrder字段 | 说明 |
|------------|----------------|------|
| orderId | order_id | 订单ID |
| symbol | symbol | 交易对 |
| side | side | 买卖方向 |
| positionSide | position_side | 持仓方向 |
| type | order_type | 订单类型 |
| price | price | 订单价格 |
| origQty | quantity | 原始数量 |
| executedQty | filled_quantity | 已成交数量 |
| status | status | 订单状态 |
| updateTime | update_time | 更新时间 |

### TradeRecord表字段映射
| Binance字段 | TradeRecord字段 | 说明 |
|------------|----------------|------|
| tradeId | trade_id | 成交ID |
| orderId | order_id | 订单ID |
| symbol | symbol | 交易对 |
| price | price | 成交价格 |
| qty | quantity | 成交数量 |
| commission | fee | 手续费 |
| time | trade_time | 成交时间 |

## 日志输出格式
```
2026-04-19 10:30:00 - binance_client - INFO - [place_order] Request: {"symbol": "BTCUSDT", "side": "BUY", ...}
2026-04-19 10:30:00 - binance_client - INFO - [place_order] Response: {"orderId": 123456, "status": "NEW", ...}
2026-04-19 10:30:00 - binance_client - ERROR - [place_order] Error: Insufficient balance
```

## 依赖项
- aiohttp: 异步HTTP客户端（已在requirements.txt）
- cryptography: 加密库（用于HMAC签名）
- sqlalchemy: 数据库ORM
- pymysql: MySQL驱动

## 风险评估
1. API版本兼容性 - Binance API可能更新，需版本控制
2. 网络异常处理 - 需要重试机制
3. 限流处理 - 遵守API调用频率限制
4. 数据一致性 - 订单状态同步

## 验证步骤
1. 运行测试脚本验证API调用
2. 检查数据库记录是否正确
3. 验证日志输出格式
4. 测试异常处理和错误回滚