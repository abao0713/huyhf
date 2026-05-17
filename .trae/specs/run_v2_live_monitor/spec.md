# 运行并监控 V2 实时交易脚本 规范

## Why
验证缠论V2策略的模拟盘实时交易脚本 `run_ethusdc_v2_live.py` 能否正常运行，并监控其输出中是否有报错或异常。

## What Changes
- 执行 `run_ethusdc_v2_live.py --dry-run` 进行 Dry-Run 模式测试
- 监控脚本启动过程中的日志输出
- 检查是否有异常、报错或崩溃
- 验证 Binance API 数据获取是否正常
- 验证分型识别和信号生成逻辑是否工作正常

## Impact
- Affected specs: 无（独立验证任务）
- Affected code: `e:\Auto_test\huyhf\run_ethusdc_v2_live.py`（只读，不修改）

## ADDED Requirements
### Requirement: Dry-Run 脚本执行验证
系统 SHALL 在 dry-run 模式下成功执行 `run_ethusdc_v2_live.py` 脚本，无崩溃或未捕获异常。

#### Scenario: 脚本正常启动
- **WHEN** 执行 `python run_ethusdc_v2_live.py --dry-run`
- **THEN** 脚本打印配置参数信息并开始运行
- **AND** 无 import 错误、语法错误或初始化错误

#### Scenario: Binance API 数据获取成功
- **WHEN** 脚本调用 Binance API 获取K线数据
- **THEN** 成功获取 30m K线数据和日线K线数据
- **AND** 日志显示获取到的K线数量

#### Scenario: 分型识别正常
- **WHEN** K线数据被处理
- **THEN** 日志显示分型数量 > 0
- **AND** 策略状态正确输出

#### Scenario: 信号生成正常
- **WHEN** 策略检查最新K线
- **THEN** 根据当前分型状态生成 HOLD 或交易信号
- **AND** 无 KeyError、IndexError 等运行时异常

### Requirement: 监控输出
用户 SHALL 能够在控制台和日志文件中看到脚本的完整运行输出。

#### Scenario: 日志输出
- **WHEN** 脚本运行
- **THEN** 控制台显示 INFO 级别日志
- **AND** 日志文件 `v2_live_trading.log` 记录完整日志