# Tasks

- [x] Task 1: 修复 argparse choices 缺失问题
  - [x] 1.1 在 `trading_system/backtest/run_backtest.py` 第96行，将 `choices=["v1", "v2", "mtf"]` 改为 `choices=["v1", "v2", "mtf", "chan_buy_sell"]`
  - [x] 1.2 同步更新 help 文本，增加 chan_buy_sell 的描述

- [x] Task 2: 实现反向平仓逻辑（一卖平多 + 一买平空）
  - [x] 2.1 在 `_check_state_transitions()` 中新增两个分支：
    - `LONG_ENTRY` / `WATCHING_SIMILAR_BUY` 状态下检测到 `fs.divergence_confirmed` → 重置到 `IDLE`，清空 tracker
    - `SHORT_ENTRY` / `WATCHING_SIMILAR_SELL` 状态下检测到 `fb.divergence_confirmed` → 重置到 `IDLE`，清空 tracker
  - [x] 2.2 在 `generate_signal()` 中，于所有 BUY/SELL 信号判断之前，新增反向平仓信号返回：
    - 多仓 + 一卖 → `{'action': 'CLOSE_LONG', ...}`
    - 空仓 + 一买 → `{'action': 'CLOSE_SHORT', ...}`
  - [x] 2.3 确保反向平仓信号优先级高于加仓信号（即先检查是否需要平仓，再检查加仓）

- [x] Task 3: 验证导入和策略正确性
  - [x] 3.1 验证 ChanBuySellStrategy 可正常导入和初始化
  - [x] 3.2 验证 argparse choices 已包含 chan_buy_sell

- [x] Task 4: 运行回测验证端到端功能
  - [x] 4.1 执行 `python run_chan_buy_sell_backtest.py --days 120`
  - [x] 4.2 检查回测是否无异常完成
  - [x] 4.3 检查回测结果报告是否完整（收益率、夏普比率、最大回撤、胜率）

# Task Dependencies
- Task 2（反向平仓）不依赖 Task 1，可并行
- Task 3（验证）依赖 Task 1 + Task 2
- Task 4（回测）依赖 Task 1 + Task 2 + Task 3