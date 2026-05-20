# 迁移计划：从手动 REST API → Binance 官方 Python SDK

## 现状分析

### 当前架构
```
BinanceRestClient (client.py)          PaperTradingClient (paper_client.py)
├── _request() 手工构造 HTTP 请求       ├── 本地模拟交易
├── place_order() POST /order          ├── _get_kline_client() → BinanceRestClient
├── get_order() GET /order             ├── get_continuous_klines()
├── cancel_order() DELETE /order      └── get_spot_klines()
├── get_account() GET /account         └── close() [关闭内部 _kline_client]
├── get_positions() GET /positionRisk
├── get_exchange_info() GET /exchangeInfo
├── get_continuous_klines() GET /continuousKlines
├── get_spot_klines() GET /klines
└── close()
依赖: aiohttp + BinanceSigner (HMAC/Ed25519/RSA)
```

### 目标架构
```
BinanceRestClient (client.py)          PaperTradingClient (paper_client.py)
├── UMFutures SDK 封装                  ├── 本地模拟交易（不变）
├── place_order() → new_order()        ├── _get_kline_client() → BinanceRestClient
├── get_order() → query_order()       ├── get_continuous_klines()
├── cancel_order() → cancel_order()   └── get_spot_klines()
├── get_account() → account()          └── close() [SDK 无 session，pass 即可]
├── get_positions() → get_position_risk()
├── get_exchange_info() → exchange_info()
├── get_continuous_klines() → continuous_klines()
└── close() → pass（SDK 无 session 需要管理）
删除: signer.py, aiohttp 依赖
```

### 依赖文件（不可修改接口）
| 文件 | 使用的接口 |
|------|-----------|
| `paper_client.py:15` | import BinanceRestClient → 内部创建 kline client |
| `run_ethusdc_mtf_live.py:23-24` | import BinanceRestClient, PaperTradingClient |
| `run_ethusdc_v2_live.py:23` | import BinanceRestClient |
| `strategies/mtf_fractal_strategy.py:2320` | import BinanceRestClient（延迟导入） |
| `strategies/chan_strategy.py:10` | import BinanceRestClient |
| `strategies/chan_strategy_v2.py:21` | import BinanceRestClient |
| `strategies/chan_first_buy_strategy.py:13` | import BinanceRestClient |
| `data/backtest_data.py:67` | import BinanceRestClient |
| `__init__.py:2-4` | import BinanceSigner, BinanceRestClient + 损坏的 sdk_client 引用 |

### SDK 方法映射

| 当前方法 | SDK 方法 | 签名 |
|----------|----------|------|
| `place_order()` | `new_order(symbol,side,type,quantity,price,timeInForce,positionSide)` | signed |
| `get_order()` | `query_order(symbol,orderId,origClientOrderId,recvWindow)` | signed |
| `cancel_order()` | `cancel_order(symbol,orderId,origClientOrderId,recvWindow)` | signed |
| `get_account()` | `account(recvWindow=6000)` | signed |
| `get_positions(symbol)` | `get_position_risk(symbol,recvWindow)` | signed |
| `get_exchange_info()` | `exchange_info()` | 无签名 |
| `get_continuous_klines()` | `continuous_klines(pair,contractType,interval,**kwargs)` | 无签名 |
| `get_spot_klines()` | `klines(symbol,interval,**kwargs)` | 无签名 |

### 异步适配
SDK 方法是**同步**的，当前项目使用**全异步** (asyncio)。使用 `asyncio.get_event_loop().run_in_executor(None, func)` 包装同步 SDK 调用。

### SDK 安装
```
pip install binance-futures-connector
```
包名：`binance-futures-connector`，导入路径：`from binance.um_futures import UMFutures`

---

## 实施步骤

### Step 1: 安装 SDK
- **操作**: `pip install binance-futures-connector`
- **验证**: `python -c "from binance.um_futures import UMFutures; print('OK')"`
- **备选**: `pip install --no-proxy binance-futures-connector` 或配置镜像源

### Step 2: 重写 `client.py` — 使用 UMFutures SDK

**2.1** 构造函数改用 `UMFutures(key, secret, base_url)`
  - 移除 `aiohttp.ClientSession`、`_get_session()`
  - 移除 `BinanceSigner`（SDK 内置签名）
  - `is_simulated` → testnet base_url 或生产 base_url

**2.2** 新增 `_run_sync` 异步包装器
  ```python
  def _run_sync(self, func, *args, **kwargs):
      loop = asyncio.get_event_loop()
      return loop.run_in_executor(None, lambda: func(*args, **kwargs))
  ```

**2.3** 重写 8 个公开方法（接口签名完全不变）：

  | 方法 | SDK 调用 |
  |------|----------|
  | `place_order()` | `sdk.new_order(symbol=symbol, side=side, type=order_type, quantity=quantity, price=price, timeInForce=time_in_force, positionSide=position_side)` |
  | `get_order()` | `sdk.query_order(symbol=symbol, orderId=order_id, origClientOrderId=orig_client_order_id, recvWindow=5000)` |
  | `cancel_order()` | `sdk.cancel_order(symbol=symbol, orderId=order_id, origClientOrderId=orig_client_order_id, recvWindow=5000)` |
  | `get_account()` | `sdk.account(recvWindow=6000)` |
  | `get_positions(symbol)` | `sdk.get_position_risk(symbol=symbol, recvWindow=5000)` |
  | `get_exchange_info()` | `sdk.exchange_info()` |
  | `get_continuous_klines()` | `sdk.continuous_klines(pair=pair, contractType=contractType, interval=interval, startTime=startTime, endTime=endTime, limit=limit)` |
  | `get_spot_klines()` | `sdk.klines(symbol=symbol, interval=interval, startTime=startTime, endTime=endTime, limit=limit)` |

**2.4** `close()` 方法改为 `pass`（SDK 无 session 需要管理）

**2.5** 移除 `_request()`、`_get_session()` 方法

**2.6** 移除 `import aiohttp` 和 `from trading_system.binance.signer import BinanceSigner`

**2.7** main 测试代码中的 `close()` 调用保留（无实际作用）

### Step 3: 删除 `signer.py` 并清理 `__init__.py`

**3.1** 删除文件 `e:\Auto_test\huyhf\trading_system\binance\signer.py`

**3.2** 更新 `__init__.py`：
  - 移除 `from .signer import BinanceSigner`
  - 移除 `from .sdk_client import BinanceSDKClient, BinanceAPIError, APIResponse`（文件不存在）
  - 保留 `from .config import ...`
  - 保留 `from .client import BinanceRestClient`
  - 保留 `from .mapper import BinanceMapper, PositionSideEnum`
  - 保留 `from .database_adapter import BinanceDatabaseAdapter`
  - 保留 `from .enums import ...`
  - 更新 `__all__` 列表，移除 `BinanceSigner`、`BinanceSDKClient`、`BinanceAPIError`、`APIResponse`

### Step 4: PaperTradingClient 适配

**4.1** `close()` 方法中的 `await self._kline_client.close()` 改为无操作（SDK 无 session），可以移除该调用或改为 pass

**4.2** 确认 `PaperTradingClient._get_kline_client()` 创建 `BinanceRestClient` 方式不变

### Step 5: 语法编译验证

**5.1** `python -m py_compile e:\Auto_test\huyhf\trading_system\binance\client.py`

**5.2** `python -m py_compile e:\Auto_test\huyhf\trading_system\binance\__init__.py`

**5.3** `python -m py_compile e:\Auto_test\huyhf\trading_system\binance\paper_client.py`

**5.4** 运行 `python -m trading_system.binance.client --simulated` 验证接口可用

### Step 6: 全面验证

**6.1** 对 8 个引用 `BinanceRestClient` 的文件做 `python -m py_compile` 全量检查

**6.2** Grep 确认无残留 `trading_system.binance.signer` 引用

**6.3** Grep 确认 `signer.py` 已删除

---

## 风险点

1. **SDK 安装失败**：代理环境可能阻塞 pip — 备选：源码下载安装
2. **同步→异步适配**：`run_in_executor` 可能有性能影响 — 接受，交易请求频率低
3. **testnet base_url**：需验证 `https://testnet.binancefuture.com` 是否为正确格式
4. **`PaperTradingClient.close()`**：SDK 无 session，`close()` 改为 pass 或空操作
5. **`__init__.py` 损坏引用**：`sdk_client.py` 等文件不存在，清理时需注意
