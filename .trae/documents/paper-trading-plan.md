# MTF策略模拟盘(Paper Trading) 实施计划

## 现状分析

当前系统有两种"模拟"模式，但都不是真正的本地 Paper Trading：

| 现有模式 | 实现方式 | 问题 |
|----------|----------|------|
| Binance Testnet (`--real` 不传) | 连接 testnet.binancefuture.com，真实下单 | 需要Testnet API Key，依赖外部交易所 |
| DRY-RUN (`--dry-run`) | 只生成信号不下单 | 不模拟余额/盈亏/手续费，无法评估策略表现 |

**目标**：新增 `--paper` 模式，本地模拟所有交易操作（余额、持仓、订单、手续费、盈亏），K线数据从真实API获取，零外部依赖。

---

## Step 1: 创建 `PaperTradingClient` 类

**文件**: `trading_system/okx/paper_client.py`（新建）

### 接口设计（与 `BinanceRestClient` 保持相同接口）

```python
class PaperTradingClient:
    """
    本地纸交易客户端
    - 模拟账户余额、持仓、订单
    - K线数据委托给真实 BinanceRestClient 获取
    - 不发送任何真实订单到交易所
    """

    def __init__(self, initial_balance=10000.0, commission_rate=0.0004,
                 leverage=10, api_key=None, secret_key=None, is_simulated=True):
        # K线数据仍从真实API获取（或testnet）
        self._kline_client = BinanceRestClient(
            api_key=api_key, secret_key=secret_key, is_simulated=is_simulated
        )
        # 模拟账户状态
        self._initial_balance = initial_balance
        self._balance = initial_balance
        self._positions: Dict[str, List[Dict]] = {}  # 按symbol分组
        self._orders: List[Dict] = []
        self._trades: List[Dict] = []
        self._commission_rate = commission_rate
        self._leverage = leverage
        self._current_price: Dict[str, float] = {}
```

### 模拟的方法

| 方法 | 模拟行为 |
|------|----------|
| `get_account()` | 返回本地虚拟余额（`availableBalance`, `totalMarginBalance`） |
| `place_order(symbol, side, position_side, order_type, quantity, price)` | 以当前市价立即成交，更新余额/持仓/交易记录 |
| `get_positions(symbol)` | 返回本地虚拟持仓列表 |
| `get_order(order_id)` | 返回本地订单记录 |

### 委托的方法（真实API）

| 方法 | 行为 |
|------|------|
| `get_continuous_klines(symbol, interval, limit, end_time)` | 委托给 `_kline_client` |
| `get_spot_klines(...)` | 委托给 `_kline_client` |
| `get_exchange_info()` | 委托给 `_kline_client` |
| `close()` | 关闭 `_kline_client` 会话 |

### `place_order` 模拟逻辑

```
1. 获取当前市价（从最近K线收盘价，或通过 get_continuous_klines 取最新价格）
2. 计算成交金额 = quantity * current_price
3. 计算手续费 = 成交金额 * commission_rate
4. 根据 position_side 和 side 判断是开仓还是平仓:
   - 开仓: 扣除手续费，创建虚拟持仓
   - 平仓: 计算盈亏 = (平仓价 - 开仓价) * 平仓数量，更新余额
5. 更新 _balance, _positions, _trades, _orders
6. 返回模拟的订单结果 dict
```

### 模拟盈亏计算

```python
# 多头平仓盈亏
pnl = (exit_price - entry_price) * qty_closed
# 空头平仓盈亏
pnl = (entry_price - exit_price) * qty_closed
# 手续费扣除
commission = notional * self._commission_rate  # taker 0.04%
```

---

## Step 2: 修改 `run_ethusdc_mtf_live.py`

### 2.1 新增命令行参数

```python
parser.add_argument("--paper", action="store_true", 
                    help="本地纸交易模式（不依赖交易所，本地模拟成交）")
parser.add_argument("--initial-balance", type=float, default=10000.0,
                    help="纸交易初始资金 (默认: $10,000)")
parser.add_argument("--commission-rate", type=float, default=0.0004,
                    help="纸交易手续费率 (默认: 0.04%%)")
```

### 2.2 启动逻辑

```
if args.paper:
    client = PaperTradingClient(
        initial_balance=args.initial_balance,
        commission_rate=args.commission_rate,
    )
    executor = MultiTFFractalStrategyExecutor(client, **params)
elif args.dry_run:
    executor = DryRunExecutor(client, **params)
else:
    client = BinanceRestClient(is_simulated=is_simulated)
    executor = MultiTFFractalStrategyExecutor(client, **params)
```

### 2.3 信号处理增强（纸交易专用）

纸交易模式下，定期输出账户状态报告：
- 当前余额、总权益（余额+未实现盈亏）
- 当前持仓列表
- 已实现盈亏汇总
- 今日/累计盈亏

---

## Step 3: 确保 Executor 兼容纸交易客户端

### 检查点

`MultiTFFractalStrategyExecutor._execute_signal()` 中所有调用 `self.client.xxx()` 的地方：

| 调用 | 是否兼容 PaperTradingClient |
|------|---------------------------|
| `self.client.get_account()` | ✅ 已在接口中定义 |
| `self.client.place_order(...)` | ✅ 已在接口中定义 |
| `self.client.get_positions()` | ✅ 已在接口中定义 |
| `self.client.get_continuous_klines(...)` | ✅ 已在接口中定义 |

**无需修改 Executor 代码**，因为 `PaperTradingClient` 实现了与 `BinanceRestClient` 完全相同的接口。

---

## Step 4: 新增纸交易性能报告

### 4.1 运行时实时输出

每隔 N 次循环或每隔 M 分钟输出：
```
========= 纸交易状态报告 =========
账户余额:      $9,856.32
未实现盈亏:    +$123.45
总权益:        $9,979.77
持仓:          
  LONG  ETHUSDC  0.45 @ $2,150.00  当前: $2,235.00  (+$38.25)
已实现盈亏:    -$143.68
手续费合计:    $18.42
交易次数:      12 (胜: 5 / 负: 7)
胜率:          41.67%
===================================
```

### 4.2 退出时生成完整报告

与回测报告格式保持一致：
- 收益表现（初始资金、最终权益、净利润、总收益率）
- 风险指标（最大回撤）
- 交易统计（总交易次数、胜率、盈利因子、平均每笔盈亏）

---

## Step 5: 数据持久化（可选，后续实现）

纸交易订单和交易记录保存到本地 JSON 文件：
- `paper_trades.json` — 交易历史
- `paper_orders.json` — 订单历史
- `paper_equity_curve.json` — 权益曲线

---

## 修改文件清单

| 操作 | 文件 | 说明 |
|------|------|------|
| **新建** | `trading_system/okx/paper_client.py` | PaperTradingClient 类 |
| **修改** | `run_ethusdc_mtf_live.py` | 新增 --paper 参数和启动逻辑 |
| **不改** | `trading_system/strategies/mtf_fractal_strategy.py` | Executor 不需要任何改动 |

## 依赖关系

```
PaperTradingClient
  ├── 依赖 BinanceRestClient (仅用于K线查询)
  ├── 实现与 BinanceRestClient 相同接口
  └── 被 MultiTFFractalStrategyExecutor 使用（无需修改Executor）
```

## 使用方式

```bash
# 纸交易模式（默认$10,000初始资金）
python run_ethusdc_mtf_live.py --paper

# 自定义初始资金和杠杆
python run_ethusdc_mtf_live.py --paper --initial-balance 50000

# 纸交易 + 手动支撑阻力位
python run_ethusdc_mtf_live.py --paper --support-levels 2200,2150 --resistance-levels 2400,2500
```