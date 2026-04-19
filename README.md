# 交易系统项目

## 项目结构

```
├── trading_system/       # FastAPI交易系统
│   ├── api/             # API层
│   │   ├── __init__.py
│   │   ├── main.py      # FastAPI应用入口
│   │   └── routers.py   # API路由
│   ├── core/            # 核心配置
│   │   ├── __init__.py
│   │   ├── config.py    # 配置管理
│   │   ├── database.py  # 数据库连接
│   │   └── schemas.py   # Pydantic模型
│   ├── models/          # 数据库模型
│   │   ├── __init__.py
│   │   ├── trading_order.py
│   │   ├── trade_record.py
│   │   └── position.py
│   ├── services/        # 业务逻辑
│   │   ├── __init__.py
│   │   └── crud.py      # CRUD操作
├── okx/                 # OKX WebSocket接口
│   ├── models/          # 数据模型
│   ├── tests/           # 测试文件
│   ├── utils/           # 工具类
│   │   ├── signer.py    # 签名生成
│   │   └── rate_limiter.py # 限速管理
│   ├── websocket/       # WebSocket客户端
│   │   └── client.py    # WebSocket客户端实现
│   ├── api.py           # OKX API封装
│   ├── config.py        # OKX配置
│   └── examples.py      # 使用示例
├── .env                 # 环境变量配置
├── .env.example         # 环境变量示例
├── main.py              # 项目主入口
├── log_config.py        # 日志配置
└── requirements.txt     # 依赖文件
```

## 功能特性

1. **FastAPI交易系统**
   - 交易订单管理
   - 成交记录管理
   - 持仓管理
   - 自动计算利润和手续费

2. **OKX WebSocket接口**
   - 支持实盘和模拟盘
   - 登录认证
   - 频道订阅
   - 下单功能
   - 限速控制

## 环境配置

1. **创建环境变量文件**
   ```bash
   cp .env.example .env
   ```

2. **编辑.env文件**
   ```
   # 数据库配置
   DATABASE_URL=mysql+pymysql://root:password@localhost:3306/trading_db
   
   # OKX API配置
   OKX_API_KEY=your_api_key
   OKX_SECRET_KEY=your_secret_key
   OKX_PASSPHRASE=your_passphrase
   ```

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行项目

### 启动FastAPI应用

```bash
python main.py
```

或

```bash
uvicorn main:app --reload
```

### 访问API文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## OKX WebSocket使用示例

```python
from okx.api import OKXSyncAPI

# 初始化API (使用模拟盘)
api = OKXSyncAPI(
    api_key="your_api_key",
    secret_key="your_secret_key",
    passphrase="your_passphrase",
    is_simulated=True
)

# 连接并登录
api.connect()
api.login()

# 订阅tickers频道
def callback(data):
    print(f"Price: {data['data'][0]['last']}")
api.subscribe("tickers", "BTC-USDT", callback)

# 下单
api.place_order(
    side="buy",
    instId="BTC-USDT",
    tdMode="cash",
    ordType="market",
    sz="0.001"
)

# 关闭连接
api.close()
```

## 技术栈

- Python 3.7+
- FastAPI
- SQLAlchemy
- MySQL
- WebSockets
- Pydantic

## 注意事项

1. 确保MySQL数据库已创建
2. OKX API密钥需要在OKX官网申请
3. 模拟盘和实盘使用不同的WebSocket地址
4. 遵守OKX的限速规则
