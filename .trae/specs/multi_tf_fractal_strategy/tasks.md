# Tasks

- [x] Task 1: 创建策略核心类 `MultiTFFractalStrategy`
  - [x] 继承 `BaseStrategy`，定义策略名称和数据容器
  - [x] 实现支撑位管理（注入关键支撑位列表，计算价格是否进入支撑区域+阈值）
  - [x] 实现30分钟底分型预判（K1/K2 K线形态检测：K2.low < K1.low AND K2.close > K2.open * 0.5）
  - [x] 实现15分钟多信号检测：
    - [x] 底背离检测（价格新低 + MACD未新低）
    - [x] 看涨K线形态检测（早晨之星/看涨吞没/锤子线）
    - [x] 下降趋势线突破检测（收盘价突破最近N根K线的下降趋势线）
    - [x] 指标金叉检测（MACD金叉 + KDJ低位金叉 K<20）
  - [x] 实现两阶段仓位管理（40%试探入场 + K3确认后60%加仓）
  - [x] 实现多层风控：
    - [x] 单笔亏损 <= 总资金2%（自动调整仓位大小）
    - [x] 连续3次止损暂停交易（跟踪止损计数）
    - [x] 日亏损5%停止当日交易（跟踪当日累计亏损）

- [x] Task 2: 创建执行器 `MultiTFFractalStrategyExecutor`
  - [x] 结构参考 `ChanStrategyV2Executor`
  - [x] 支持同时获取30分钟和15分钟双周期K线
  - [x] `_run_once()` 主循环：获取数据 → 调用策略检测 → 执行入场/加仓信号
  - [x] 支持K3确认监控（试探入场后持续监控30分钟K线）
  - [x] 实现交易执行：`_open_long_probe()`(40%), `_add_long_confirm()`(60%), `_execute_stop_loss()`
  - [x] 日志输出：数据时间戳、支撑位检测结果、15分钟信号详情、风控状态

- [x] Task 3: 创建运行脚本 `run_ethusdc_mtf_live.py`
  - [x] 参考 `run_ethusdc_v2_live.py` 的脚本结构
  - [x] 配置关键支撑位列表（可命令行指定或从配置文件读取）
  - [x] 支持 `--dry-run`（仅信号不下单）和 `--real`（实盘）
  - [x] 支持 `--support-levels` 参数传入支撑位列表

- [x] Task 4: 注册到 `__init__.py`
  - [x] 导出 `MultiTFFractalStrategy` 和 `MultiTFFractalStrategyExecutor`

- [x] Task 5: 运行 dry-run 验证
  - [x] 验证30分钟支撑位预判逻辑
  - [x] 验证15分钟多信号检测输出
  - [x] 验证两阶段仓位管理信号
  - [x] 验证风控规则触发

# Task Dependencies
- Task 2 依赖 Task 1 ✓
- Task 3 依赖 Task 2 ✓
- Task 4、Task 5 与 Task 2、3 并行 ✓