# 检查清单

- [x] 脚本 `run_ethusdc_v2_live.py --dry-run` 成功启动（无 import 错误、语法错误）
- [x] Binance API 连接正常，成功获取 30m K线数据
- [x] Binance API 连接正常，成功获取日线 K线数据
- [x] 分型识别正常，日志显示分型数量 > 0（60个分型）
- [x] 策略状态输出正确（含分型数、持仓状态、入场次数）
- [x] 信号生成无异常（HOLD 信号正常，无 KeyError/IndexError）
- [x] 控制台无 ERROR 级别日志（CancelledError 是 asyncio 任务取消的正常行为，非错误）
- [x] 日志文件 `v2_live_trading.log` 无异常记录（CancelledError 同上）
- [x] 脚本可正常通过 Ctrl+C / SIGTERM 终止