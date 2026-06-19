# 实现实时监控模式 Spec

## Why
用户期望程序能够持续运行，实时监控市场数据并执行交易策略。当前程序在处理完历史CSV数据后就退出，无法实现真正的实盘监控。

## What Changes
- 修改 `run_loop` 方法，在历史数据处理完成后进入实时监控循环
- 实现新K线检测机制（通过API轮询最新K线数据）
- 添加持续运行的控制逻辑（只有用户主动停止才退出）
- 优化日志输出，区分历史回放和实时监控阶段

## Impact
- Affected specs: fix_abnormal_restart, run_v2_live_monitor
- Affected code: 
  - `run_crypto_chan_live.py` - 主循环逻辑
  - 可能涉及K线数据获取模块

## MODIFIED Requirements

### Requirement: 实时监控模式
程序应支持两种运行模式：
1. **历史回放模式**：处理CSV中的历史数据（当前行为）
2. **实时监控模式**：处理完历史数据后，继续监控实时K线数据

#### Scenario: 进入实时监控
- **WHEN** 历史数据处理完成（到达最后一根K线）
- **THEN** 程序不退出，而是进入实时监控循环
- **AND** 定期（如每60秒）检查是否有新的4H K线形成
- **AND** 检测到新K线时，更新数据并执行策略

#### Scenario: 持续运行控制
- **WHEN** 程序处于实时监控模式
- **THEN** 只有以下情况才会退出：
  - 用户按下 Ctrl+C（KeyboardInterrupt）
  - 收到系统信号（SIGTERM/SIGINT）
  - 发生致命错误（API连接失败等）
- **AND** 不应该因为"处理完数据"而自动退出

#### Scenario: 日志输出区分
- **WHEN** 程序从历史回放切换到实时监控
- **THEN** 输出明确的日志提示："历史数据处理完成，进入实时监控模式"
- **AND** 实时监控阶段的日志格式应包含"实时"标识

### Requirement: 新K线检测机制
系统应能够检测新的4H K线是否形成。

#### Scenario: 检测新K线
- **WHEN** 程序处于实时监控模式
- **THEN** 定期调用API获取最新的K线数据
- **AND** 比较新K线的open_time与最后已处理K线的open_time
- **AND** 如果open_time更大，说明有新K线形成

#### Scenario: 更新数据
- **WHEN** 检测到新的4H K线
- **THEN** 将新K线追加到数据集中
- **AND** 调用策略的 `inject_data_incremental` 方法更新数据
- **AND** 执行策略逻辑，生成交易信号

## REMOVED Requirements

### Requirement: 处理完数据自动退出
**Reason**: 用户期望程序持续运行，而不是处理完历史数据后退出
**Migration**: 修改 `run_loop` 的返回逻辑，历史数据处理完成后进入实时监控循环
