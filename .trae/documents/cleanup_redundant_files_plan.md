# 项目冗余文件清理计划

## 概述

清理项目中未被主交易系统（`run_crypto_chan_live.py` / `run_crypto_chan_backtest.py`）引用的冗余文件，包括测试脚本、调试脚本、过时的输出文件、未使用的模块、`__pycache__` 目录等。

## 当前状态分析

### 活跃入口文件（保留）
- `run_crypto_chan_live.py` — 实盘交易入口
- `run_crypto_chan_backtest.py` — 回测入口
- `run_ethusdc_mtf_backtest.py` — 另一个回测变体
- `download_backtest_data.py` — 数据下载工具

### 核心依赖链（保留）
```
run_crypto_chan_live.py
  └── trading_system.binance.client → trading_system.binance.config
  └── trading_system.strategies.mtf_fractal_strategy
        └── trading_system.strategies.chan_strategy
        └── trading_system.strategies.chan_first_buy_strategy
        └── trading_system.strategies.base_strategy
        └── trading_system.utils.indicators
        └── trading_system.data.market_data
  └── trading_system.notify.dingtalk
```

### 仅被Web服务器使用的模块（可删除）
- `main.py` — FastAPI Web服务器，不和交易系统交互
- `log_config.py` — 仅被 `main.py`、`database.py`、`crud.py` 引用
- `trading_system/api/` — 仅被 `main.py` 导入
- `trading_system/services/` — 仅被 `main.py` 导入
- `trading_system/binance/database_adapter.py` — 仅被 `__init__.py` 导出
- `trading_system/binance/mapper.py` — 仅被 `database_adapter.py` 和 `__init__.py` 使用
- `trading_system/binance/enums.py` — 仅被 `__init__.py` 导出
- `trading_system/binance/__init__.py` — 仅导出 database_adapter/mapper/enums
- `trading_system/models/` — 仅被数据库相关模块使用
- `trading_system/core/database.py` — 仅被 database_adapter 使用
- `trading_system/core/schemas.py` — 仅被 services/crud.py 使用

## 清理清单

### 第1组：根目录测试/调试脚本（13个文件）
- `test_client.py` — 测试脚本
- `test_sdk_migration.py` — SDK迁移测试
- `test_signal_fix.py` — 信号修复测试
- `test_signal_fix2.py` — 信号修复测试2
- `diagnose_backtest.py` — 回测诊断脚本
- `diagnose_signals.py` — 信号诊断脚本
- `signal_diag.py` — 信号诊断脚本
- `quick_signal_test.py` — 快速信号测试
- `verify_1h_data.py` — 1H数据验证脚本
- `verify_signals.py` — 信号验证脚本
- `timing_test.py` — 计时测试脚本
- `vrfy.py` — 验证脚本
- `run_vrfy.bat` — 批处理文件

### 第2组：根目录过期输出文件（5个文件）
- `backtest_output.txt` — 回测输出
- `backtest_plot.png` — 回测图表
- `backtest_plot_guide.md` — 图表指南
- `run_crypto_chan_live.pid` — PID文件
- `trading_system.log` — 根目录过期日志

### 第3组：根目录过时包文件（4个文件）
- `binance_connector-3.3.1.whl` — 旧版wheel
- `binance_futures_connector-3.3.1-py3-none-any.whl` — 旧版wheel
- `binance_futures_connector-4.2.0-py3-none-any.whl` — 旧版wheel
- `pypi.json` — 无用配置

### 第4组：未使用的Web服务器代码（4个文件/目录）
- `main.py` — FastAPI入口
- `log_config.py` — Web服务器日志配置
- `trading_system/api/` — API路由模块
- `trading_system/services/` — CRUD服务模块

### 第5组：未使用的交易所模块（1个目录）
- `trading_system/okx/` — OKX交易所（未被任何代码引用）

### 第6组：所有 `__pycache__` 目录
- 根目录 `__pycache__/`
- `trading_system/__pycache__/`
- `trading_system/api/__pycache__/`
- `trading_system/backtest/__pycache__/`
- `trading_system/binance/__pycache__/`
- `trading_system/core/__pycache__/`
- `trading_system/data/__pycache__/`
- `trading_system/models/__pycache__/`
- `trading_system/notify/__pycache__/`
- `trading_system/okx/__pycache__/`
- `trading_system/services/__pycache__/`
- `trading_system/strategies/__pycache__/`
- `trading_system/utils/__pycache__/`

### 第7组：过期编译文件（2个文件）
- `trading_system/strategies/chan_first_buy_strategy.pyc`
- `trading_system/strategies/chan_strategy.pyc`

### 第8组：过期日志文件（4个文件）
- `trading_system/binance/logs/api_log`
- `trading_system/binance/logs/api_log.2026-04-24.log`
- `trading_system/binance/trading_system.log`
- `trading_system/backtest/logs/api_log`

### 第9组：过期图表输出（8个文件）
- `test_charts/drawdown.png`
- `test_charts/equity_curve.png`
- `test_charts/returns.png`
- `trading_system/backtest/charts/drawdown.png`
- `trading_system/backtest/charts/equity_curve.png`
- `trading_system/backtest/charts/returns.png`
- `trading_system/backtest/ETHUSDC_backtest_20260613_152238.png`
- `trading_system/backtest/ETHUSDC_backtest_20260613_181717.png`
- `trading_system/backtest/ETHUSDC_backtest_20260613_185218.png`
- `trading_system/backtest/ETHUSDC_backtest_20260613_185321.png`
- `trading_system/backtest/ETHUSDC_backtest_20260613_185600.png`

### 第10组：过期回测结果（4个文件）
- `trading_system/data/binance_history/backtest_results.json`
- `trading_system/data/binance_history/chan_strategy_backtest_results.json`
- `trading_system/data/binance_history/crypto_chan_backtest_results.json`
- `trading_system/data/binance_history/paper_results.json`

### 第11组：数据库相关模块（未使用，7个文件）
- `trading_system/binance/database_adapter.py`
- `trading_system/binance/mapper.py`
- `trading_system/binance/enums.py`
- `trading_system/binance/__init__.py`
- `trading_system/models/__init__.py`
- `trading_system/models/trading_order.py`
- `trading_system/models/trade_record.py`
- `trading_system/models/position.py`
- `trading_system/core/database.py`
- `trading_system/core/schemas.py`

## 保留的项目

以下文件虽然可能暂时未使用，但予以保留：

| 文件/目录 | 原因 |
|-----------|------|
| `.env` / `.env.example` | 运行必需配置 |
| `requirements.txt` | 依赖管理 |
| `README.md` | 项目文档 |
| `frontend/` | 前端Dashboard，可能后续使用 |
| `.trae/specs/` | 历史规范文档（开发记录） |
| `.trae/documents/` | 历史计划文档（开发记录） |
| `.idea/` | IDE配置 |
| `.qoder/` | 文档wiki |
| `trading_system/data/binance_history/*.csv` | 回测数据 |
| `trading_system/core/config.py` | 核心配置 |
| `trading_system/core/__init__.py` | 包标识 |
| `download_backtest_data.py` | 数据下载工具 |
| `run_ethusdc_mtf_backtest.py` | 回测变体 |

## 验证步骤

1. 删除所有冗余文件后，运行 `python run_crypto_chan_live.py --foreground --interval 10` 确认实盘交易正常
2. 运行 `python run_crypto_chan_backtest.py` 确认回测正常
3. 检查无 import 错误