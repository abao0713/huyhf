# 项目清理计划

## 保留原则
- **MTF策略链完整保留**: `mtf_fractal_strategy.py` 及其所有依赖
- **活跃实盘入口保留**: MTF实盘、V2实盘、Web API入口
- **Binance API层完整保留**: `trading_system/okx/`
- **数据文件保留**: ETHUSDC 历史K线数据
- **Spec文档保留**: `.trae/specs/` 和 `.trae/documents/` 作为设计历史

---

## Step 1: 删除废弃根级脚本 (7个)

| 文件 | 删除理由 |
|------|----------|
| `run_chan_buy_sell_backtest.py` | subprocess调用同一 run_backtest.py，未实际使用买卖点策略 |
| `run_ethusdc_v2_backtest.py` | subprocess调用同一 run_backtest.py，未实际使用V2策略 |
| `run_ethusdt_30m_continuous.py` | ETHUSDT临时回测脚本，非ETHUSDC |
| `run_first_buy_analysis.py` | 一次性背驰分析工具，非核心流程 |
| `run_param_optimization.py` | 一次性参数优化，结果已产出 |

## Step 2: 删除临时测试脚本 (3个)

| 文件 | 删除理由 |
|------|----------|
| `_test_state_machine.py` | 用假数据测试买卖点状态机 |
| `test_v2_signals.py` | 一次性V2信号验证 |
| `test_batch_download.py` | 一次性下载测试 |

## Step 3: 删除一次性数据下载工具 (2个)

| 文件 | 删除理由 |
|------|----------|
| `download_ethusdc_90d.py` | 数据已下载完毕 |
| `download_ethusdt_180d.py` | 数据已下载完毕 |

## Step 4: 删除冗余策略文件 (2个)

| 文件 | 删除理由 |
|------|----------|
| `trading_system/strategies/chan_buy_sell_strategy.py` | 仅被已删除的 `_test_state_machine.py` 引用 |
| `trading_system/strategies/config.py` | 未被任何活跃代码引用，且含硬编码API密钥（安全风险） |

### Step 4.1: 更新 __init__.py
删除 `trading_system/strategies/__init__.py` 中对 `ChanBuySellStrategy` 的导入和导出。

## Step 5: 清理所有 `__pycache__` 目录 (11个)

删除以下位置的所有 `__pycache__/` 目录：
- 根目录
- `trading_system/strategies/`（含孤儿 `trend_following_strategy.pyc`）
- `trading_system/backtest/`
- `trading_system/utils/`
- `trading_system/data/`
- `trading_system/okx/`
- `trading_system/api/`（含孤儿 `routers.pyc`, `ws.pyc`）
- `trading_system/core/`
- `trading_system/models/`
- `trading_system/services/`

## Step 6: 删除所有日志文件 (9个)

```
*.log (根目录4个)
trading_system/backtest/logs/       # 整个目录
trading_system/okx/logs/            # 整个目录
```

## Step 7: 删除生成的图表和测试输出

| 路径 | 删除理由 |
|------|----------|
| `backtest_plot.png` | 运行回测重新生成 |
| `trading_system/backtest/charts/` | 运行回测重新生成 |
| `test_charts/` | 测试图表输出目录 |

## Step 8: 删除非ETHUSDC数据文件 (2个)

| 文件 | 删除理由 |
|------|----------|
| `trading_system/data/binance_history/ETHUSDT_1d.csv` | 非目标交易对 |
| `trading_system/data/binance_history/ETHUSDT_30m.csv` | 非目标交易对 |

## Step 9: 删除参数优化结果文件 (21个)

| 路径 | 删除理由 |
|------|----------|
| `trading_system/data/binance_history/optimization_report.json` | 优化已结束 |
| `trading_system/data/binance_history/opt_*.json` (20个) | 优化已结束 |

## Step 10: 删除冗余回测结果

| 路径 | 删除理由 |
|------|----------|
| `trading_system/data/binance_history/backtest_results.json` | 保留 `chan_strategy_backtest_results.json` 即可 |

---

## 保留文件清单（清理后）

```
huyhf/
├── .env
├── .env.example
├── .gitignore
├── .idea/                          # IDE配置
├── .trae/                          # AI辅助开发历史
│   ├── documents/                  # 32个设计文档
│   └── specs/                      # 37个功能规格
├── requirements.txt
├── README.md
├── main.py                         # Web API入口
├── log_config.py                   # 统一日志配置
├── run_ethusdc_mtf_backtest.py     # MTF回测入口 ★
├── run_ethusdc_mtf_live.py         # MTF实盘入口 ★
├── run_ethusdc_v2_live.py          # V2实盘入口
├── trading_system/
│   ├── api/                        # FastAPI Web层
│   │   ├── main.py
│   │   └── __init__.py
│   ├── backtest/
│   │   └── run_backtest.py         # 回测运行器
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   └── schemas.py
│   ├── data/
│   │   ├── backtest_data.py
│   │   ├── market_data.py
│   │   └── binance_history/
│   │       ├── ETHUSDC_15m.csv
│   │       ├── ETHUSDC_30m.csv
│   │       ├── ETHUSDC_1d.csv
│   │       ├── ETHUSDC_4h.csv
│   │       └── chan_strategy_backtest_results.json
│   ├── models/
│   │   ├── trading_order.py
│   │   ├── trade_record.py
│   │   └── position.py
│   ├── okx/                        # Binance REST API层
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── database_adapter.py
│   │   ├── enums.py
│   │   ├── mapper.py
│   │   ├── sdk_client.py
│   │   └── signer.py
│   ├── services/
│   │   └── crud.py
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── base_strategy.py        # 策略基类
│   │   ├── chan_strategy.py        # 核心缠论策略
│   │   ├── chan_first_buy_strategy.py  # 背驰分析器(MTF依赖)
│   │   ├── chan_strategy_v2.py     # V2策略
│   │   ├── backtest_engine.py      # 回测引擎
│   │   └── mtf_fractal_strategy.py # MTF多周期策略 ★
│   └── utils/
│       ├── chan_plotter.py
│       └── indicators.py
```

---

## 执行步骤汇总

| Step | 操作 | 删除数量 |
|------|------|---------|
| 1 | 删除废弃根级脚本 | 5个.py |
| 2 | 删除临时测试脚本 | 3个.py |
| 3 | 删除一次性下载工具 | 2个.py |
| 4 | 删除冗余策略 + 更新 __init__.py | 2个.py + 1处编辑 |
| 5 | 清理 __pycache__ | 11个目录 |
| 6 | 删除日志文件 | 9个文件/目录 |
| 7 | 删除图表输出 | 3个目录/文件 |
| 8 | 删除非目标交易对数据 | 2个.csv |
| 9 | 删除参数优化结果 | 21个.json |
| 10 | 删除冗余回测结果 | 1个.json |

**总计删除**: ~50个文件 + 11个目录，编辑1处（__init__.py）