# 缠论五大买卖点串联策略 + 回测实施计划

## 当前状态

根据代码库调研，以下文件**已创建/已修改**：

| 文件 | 状态 | 说明 |
|------|------|------|
| `trading_system/strategies/chan_buy_sell_strategy.py` | ✅ 已创建 (275行) | 核心策略：StrategyState(8状态)、PositionTracker、ChanBuySellStrategy |
| `run_chan_buy_sell_backtest.py` | ✅ 已创建 (75行) | 回测启动脚本，通过 subprocess 调用 run_backtest.py |
| `trading_system/strategies/__init__.py` | ✅ 已修改 | 导出 ChanBuySellStrategy, StrategyState, PositionTracker |
| `trading_system/backtest/run_backtest.py` | ⚠️ 部分集成 | chan_buy_sell 分支已添加，但 choices 列表缺少该值 |

## 发现的问题

**P0 阻塞问题**: `trading_system/backtest/run_backtest.py` 第97行：
```python
choices=["v1", "v2", "mtf"],  # 缺少 "chan_buy_sell"
```
argparse 会拒绝 `--strategy-version chan_buy_sell`，回测无法启动。

---

## 执行步骤

### 步骤1: 修复 argparse choices 问题

**文件**: `trading_system/backtest/run_backtest.py`

将 `--strategy-version` 参数的 `choices` 列表从：
```python
choices=["v1", "v2", "mtf"],
```
修改为：
```python
choices=["v1", "v2", "mtf", "chan_buy_sell"],
```

### 步骤2: 验证导入和策略初始化

运行以下命令，验证策略可以正确导入和初始化：
```bash
python -c "from trading_system.strategies.chan_buy_sell_strategy import ChanBuySellStrategy, StrategyState, PositionTracker; s = ChanBuySellStrategy(); print('导入成功'); print(s.get_state_summary())"
```

### 步骤3: 运行回测

使用启动脚本运行完整回测：
```bash
cd e:\Auto_test\huyhf
python run_chan_buy_sell_backtest.py --days 120
```

预期输出包括：
- 回测配置信息（交易对、时间周期、初始资金、杠杆等）
- K线数据加载确认
- 回测进度条
- 最终绩效报告（收益率、夏普比率、最大回撤、胜率等）

### 步骤4: 分析回测结果

回测完成后，检查以下关键指标：
1. **收益率** — 总收益率和年化收益率
2. **夏普比率** — 风险调整后收益
3. **最大回撤** — 最大资金回撤幅度
4. **胜率** — 盈利交易占比
5. **交易次数** — 总交易次数，一买→二买触发次数，类二买加仓次数
6. **一卖→二卖→类二卖** 链路的触发情况
7. **买卖点触发统计** — 各买卖点在历史数据中的触发频率

### 步骤5: 分析日志/导出结果

如果存在回测日志或导出功能，检查：
- 每次交易的入场/出场时间、价格、方向
- 各买卖点的信号触发时间线
- 状态机转换历史（IDLE → WATCHING → ENTRY → WATCHING_SIMILAR）

---

## 回测参数配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 交易对 | ETHUSDC | 以太坊永续合约 |
| 主周期 | 4h | 4小时K线 |
| 辅助周期 | 30m | 30分钟K线（用于精确入场） |
| 初始资金 | 10000 USDC | |
| 杠杆 | 5x | |
| 单次投入比例 | 15% | 每次投入账户总额的15% |
| 最大加仓次数 | 2次 | 类二买/类二卖最多加仓2次 |
| 止损（多单） | 1.50x ATR | |
| 止损（空单） | 0.70x ATR | |

---

## 策略状态机逻辑（已实现，仅供理解）

```
                    ┌─────────────────────────────────┐
                    │            IDLE                  │
                    └──────┬──────────────┬───────────┘
                一买检测   │              │   一卖检测
                    ▼                      ▼
    ┌──────────────────────┐  ┌──────────────────────┐
    │ WATCHING_SECOND_BUY  │  │ WATCHING_SECOND_SELL │
    └──────────┬───────────┘  └──────────┬───────────┘
        二买确认│                  二卖确认│
               ▼                         ▼
    ┌──────────────────┐    ┌───────────────────┐
    │   LONG_ENTRY     │    │   SHORT_ENTRY     │
    │   (首次做多)      │    │   (首次做空)       │
    └────────┬─────────┘    └────────┬──────────┘
      类二买检测│             类二卖检测│
               ▼                         ▼
    ┌─────────────────────┐  ┌──────────────────────┐
    │ WATCHING_SIMILAR_BUY│  │ WATCHING_SIMILAR_SELL│
    └──────────┬──────────┘  └──────────┬───────────┘
     类二买确认 │ (add_count < 2) 类二卖确认│
               ▼                         ▼
    ┌──────────────────┐    ┌───────────────────┐
    │   LONG_ENTRY     │    │   SHORT_ENTRY     │
    │   (加仓做多)      │    │   (加仓做空)       │
    └──────────────────┘    └───────────────────┘
```

核心规则：
- 从 IDLE 发现一买 → 进入监听二买状态
- 监听中确认二买 → 立即做多
- 做多后检测到类二买 → 加仓（最多2次）
- 做空链路完全镜像
- 冷却机制：止损后进入 STOPPED 状态，冷却3根K线
- 反方向保护：监听二买时出现一卖信号，自动切换方向

---

## 验收标准

1. ✅ `argparse` choices 包含 `"chan_buy_sell"`
2. ✅ `ChanBuySellStrategy` 可以正确导入和初始化
3. ✅ 回测可以正常运行至完成（无异常崩溃）
4. ✅ 回测输出包含完整的绩效报告
5. ✅ 状态机各状态都有被触发（日志中可观察到）