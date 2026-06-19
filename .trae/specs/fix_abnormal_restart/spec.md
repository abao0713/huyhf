# 修复异常退出误判 & 初始资金使用实时余额 Spec

## Why
1. `run_crypto_chan_live.py` 主循环在 `duration=0` 模式下，`run_loop` 正常处理完所有数据后返回，但被误判为"异常退出"触发重启。原因是主循环只区分了 `duration>0` 的正常退出和 `_daemon_running=False` 的退出，没有处理"数据跑完正常结束"的情况。
2. 初始资金应使用钱包实时余额（已通过 `get_account_balance()` 获取），而非硬编码的 `args.capital` 默认值。

## What Changes
- 修改 `run_loop` 返回值增加 `completed` 标志，标识是否正常处理完所有数据
- 修改主循环逻辑，根据 `completed` 标志区分正常完成和异常退出
- 初始化阶段使用 `get_account_balance()` 返回的 `availableBalance` 作为初始资金

## Impact
- Affected specs: fix_live_mode_errors
- Affected code:
  - `run_crypto_chan_live.py` — 主循环退出逻辑、初始化资金逻辑

## MODIFIED Requirements

### Requirement: 主循环退出判断
主循环应能区分以下三种退出情况：
1. **数据跑完正常结束**：`run_loop` 返回 `completed=True`，直接 break 退出
2. **运行时长达到**：`duration>0` 且时长到达，直接 break 退出
3. **异常退出**：其他情况才触发重启

#### Scenario: 数据跑完正常退出
- **WHEN** `run_loop` 处理完所有K线数据并返回 `completed=True`
- **THEN** 主循环打印正常结束日志并 break 退出
- **AND** 不触发重启逻辑

### Requirement: 初始资金使用实时余额
- **WHEN** 执行器初始化时
- **THEN** 使用 `get_account_balance()` 返回的 `availableBalance` 作为 `initial_capital`
- **AND** 不再使用 `args.capital` 的默认值覆盖实时余额
