# 项目清理：仅保留 mtf_fractal_strategy 及其依赖 Spec

## Why
项目经过多次迭代积累了多个无关策略的残留文件、无源文件的 `.pyc` 缓存、以及不再被引用的废弃模块（OKX交易所、旧回测引擎等）。需要精简项目，仅保留 `mtf_fractal_strategy.py` 策略及其回测、图表、入库、模拟盘、基础类支撑模块，删除其余冗余代码。

## What Changes

### 删除项（无关策略残留）
- 删除 `trading_system/strategies/__pycache__/` 中无对应 `.py` 源文件的以下 `.pyc`：
  - `chan_buy_sell_strategy.cpython-37.pyc`
  - `chan_strategy_v2.cpython-37.pyc`
  - `multi_indicator_strategy.cpython-37.pyc`
  - `trend_following_strategy.cpython-37.pyc`
  - `config.cpython-37.pyc`
  - `backtest_engine.cpython-37.pyc`
- 删除整个 `trading_system/backtest/` 目录（仅含 `run_backtest.cpython-37.pyc`，无源文件，不被引用）
- 删除整个 `trading_system/okx/` 目录（OKX交易所模块，仅含 `.pyc` 无源文件，与当前 CCXT/Binance 策略无关）
- 删除 `trading_system/data/__pycache__/backtest_data.cpython-37.pyc`（无源文件，不被引用）

### 删除项（废弃数据与日志）
- 删除旧策略回测结果 JSON：
  - `trading_system/data/binance_history/backtest_results.json`
  - `trading_system/data/binance_history/chan_strategy_backtest_results.json`
  - `trading_system/data/binance_history/backtest_c2640bb9.json`
  - `trading_system/data/binance_history/backtest_ce7c87db.json`
  - `trading_system/data/binance_history/backtest_ee39d72c.json`
- 删除 `backtest_engine.log`（临时回测日志）
- 删除 `trading_system/binance/logs/api_log.2026-04-24.log`（过期 API 日志）
- 删除 `binance_connector-3.3.1.whl`（旧版 wheel 文件，已在 requirements.txt 之外）

### 保留项（mtf_fractal_strategy 依赖链）
- 策略核心：`mtf_fractal_strategy.py`、`base_strategy.py`、`chan_strategy.py`(.pyc)、`chan_first_buy_strategy.py`(.pyc)
- 回测入口：`run_crypto_chan_backtest.py`、`download_backtest_data.py`、`diagnose_backtest.py`、`timing_test.py`
- 图表：`visualization.py`、`chan_plotter.py`
- 入库（数据库）：`trading_system/models/`、`trading_system/services/crud.py`、`trading_system/core/database.py`、`trading_system/core/schemas.py`
- 模拟盘：`trading_system/binance/`（含 `paper_client.py`）
- 基础类：`trading_system/strategies/__init__.py`、`trading_system/core/config.py`、`trading_system/data/market_data.py`
- 工具类：`trading_system/utils/indicators.py`
- 配置：`.env`、`.env.example`、`requirements.txt`、`log_config.py`
- 数据：`trading_system/data/binance_history/*.csv`、`crypto_chan_backtest_results.json`
- 前端：`frontend/`
- 通知：`trading_system/notify/`（钉钉通知，策略依赖链的一部分）
- 入口：`main.py`（FastAPI，虽 `trading_system.api.main` 不存在但保留框架）
- 图表输出：`test_charts/`

### 修复项
- 清理 `trading_system/strategies/__init__.py`，移除对已删除 `.pyc` 的导入（`chan_buy_sell_strategy`、`chan_strategy_v2` 等实际无源文件可导入的模块无需修改；当前 `__init__.py` 的导入链 `chan_strategy` + `chan_first_buy_strategy` + `mtf_fractal_strategy` + `visualization` 已经匹配实际情况）

## Impact
- Affected specs: 无（全新清理操作）
- Affected code:
  - `trading_system/strategies/__pycache__/` — 删除 6 个孤立 .pyc
  - `trading_system/backtest/` — 整体删除
  - `trading_system/okx/` — 整体删除
  - `trading_system/data/__pycache__/` — 删除 1 个孤立 .pyc
  - `trading_system/data/binance_history/` — 删除 5 个旧 JSON
  - 根目录 — 删除 2 个废弃文件

## REMOVED Requirements
### Requirement: 旧策略模块（chan_buy_sell_strategy, chan_strategy_v2, multi_indicator_strategy, trend_following_strategy）
**Reason**: 这四个文件仅存在于 `__pycache__` 中，对应的 `.py` 源文件已被删除。`mtf_fractal_strategy.py` 不导入其中任何一个，全项目代码搜索无引用。
**Migration**: 无需迁移。

### Requirement: 旧回测引擎（backtest/run_backtest.py）
**Reason**: 仅存在于 `__pycache__/run_backtest.cpython-37.pyc`，无 `.py` 源文件，全项目无引用。当前回测入口是 `run_crypto_chan_backtest.py`。
**Migration**: 无需迁移。

### Requirement: OKX 交易所模块
**Reason**: `trading_system/okx/` 目录仅含 `.pyc` 文件无源文件，是为 OKX 交易所设计的模块。当前策略使用 CCXT 连接 Binance，与 OKX 完全无关。全项目代码搜索无引用。
**Migration**: 无需迁移。

### Requirement: 旧策略回测结果 JSON
**Reason**: `backtest_results.json`、`chan_strategy_backtest_results.json` 和 3 个 `backtest_*.json` 是已删除策略的回测输出，不属于当前 `mtf_fractal_strategy`。
**Migration**: 当前策略结果保存在 `crypto_chan_backtest_results.json`，保留。

### Requirement: backtest_engine.log 和过期 API 日志
**Reason**: 临时日志文件，不包含持久化信息。`api_log.2026-04-24.log` 是 4 月份的过期日志。
**Migration**: 无需迁移。

### Requirement: binance_connector-3.3.1.whl
**Reason**: 旧版 Binance Connector wheel 文件（v3.3.1），当前项目通过 `requirements.txt` 管理依赖，使用 `binance-futures-connector>=4.0.0`。
**Migration**: 通过 `pip install -r requirements.txt` 安装正确版本。