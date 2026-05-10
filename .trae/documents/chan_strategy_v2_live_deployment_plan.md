# 缠论V2策略模拟盘部署方案

## 背景

V2策略已完成回测验证，最佳风控参数组合为：
- hg1=8（分型窗口）
- leverage=20x（杠杆）
- investment_ratio=10%（投入比例）
- max_add_positions=3（最大加仓次数）
- long_stop_loss_multiplier=1.50 / short_stop_loss_multiplier=0.70（止损倍数）

现在需要将V2策略部署到Binance模拟盘（paper trading），实现实时信号生成和自动交易执行。

## 架构分析

当前项目已有：
- `ChanStrategyExecutor`（[chan_strategy.py:L2150](file:///e:/Auto_test/huyhf/trading_system/strategies/chan_strategy.py#L2150)）：V1策略的实时执行器，负责数据获取→信号生成→下单执行
- `BinanceRestClient`（[client.py:L11](file:///e:/Auto_test/huyhf/trading_system/okx/client.py#L11)）：支持 `is_simulated=True` 的模拟盘模式
- V2策略类 `ChanStrategyV2`（[chan_strategy_v2.py](file:///e:/Auto_test/huyhf/trading_system/strategies/chan_strategy_v2.py)）：已实现回测信号生成

需要新建：
1. **V2策略执行器**：适配V2的信号类型（REVERSE_TO_SHORT/REVERSE_TO_LONG/加仓BUY/SELL）
2. **模拟盘启动脚本**：配置最佳参数，连接模拟盘API

## 实现步骤

### Step 1: 创建 V2 策略执行器 `ChanStrategyV2Executor`

**文件**: `trading_system/strategies/chan_strategy_v2.py`（追加到现有文件末尾）

**核心设计**：
- 继承现有 `ChanStrategyExecutor` 的执行流程框架（数据获取→处理→信号生成→执行）
- 适配 V2 特有的信号类型：
  - `action="BUY"` + `is_add_position=True` → 加仓（不反转，仅增加仓位）
  - `action="SELL"` + `is_add_position=True` → 加仓空单
  - `action="REVERSE_TO_SHORT"` → 平掉全部多单 + 开空单（反转）
  - `action="REVERSE_TO_LONG"` → 平掉全部空单 + 开多单（反转）
- 使用V2策略的最佳风控参数

**关键代码结构**：
```python
class ChanStrategyV2Executor:
    def __init__(self, client, symbol, time_frame, check_interval=60,
                 investment_ratio=0.10, leverage=20, max_add_positions=3,
                 long_sl_multiplier=1.50, short_sl_multiplier=0.70,
                 hg1=8):
        # 创建V2策略实例
        self.strategy = ChanStrategyV2(
            symbol=symbol, time_frame=time_frame,
            hg1=hg1, use_binance_client=True,
            max_add_positions=max_add_positions
        )
        # 存储风控参数
    
    async def _execute_signal(self, signal):
        # 处理4种V2信号类型
        if signal["action"] == "REVERSE_TO_SHORT":
            await self._close_all_long()  # 平掉全部多单
            await self._open_short()       # 开空单
        elif signal["action"] == "REVERSE_TO_LONG":
            await self._close_all_short()
            await self._open_long()
        elif signal.get("is_add_position"):
            # 加仓：在当前方向追加仓位
            await self._add_position(signal)
        else:
            # 首次开仓
            await self._open_position(signal)
```

### Step 2: 创建模拟盘启动脚本 `run_ethusdc_v2_live.py`

**文件**: 项目根目录

**配置参数**（最佳风控）:
```python
SYMBOL = "ETHUSDC"
TIMEFRAME = "30m"
CHECK_INTERVAL = 60       # 60秒检查一次
INVESTMENT_RATIO = 0.10   # 10%投入
LEVERAGE = 20             # 20倍杠杆
MAX_ADD_POSITIONS = 3     # 最大加仓3次
LONG_SL_MULTIPLIER = 1.50
SHORT_SL_MULTIPLIER = 0.70
HG1 = 8
IS_SIMULATED = True       # 模拟盘模式
```

**脚本流程**：
1. 创建 `BinanceRestClient(is_simulated=True)` 
2. 创建 `ChanStrategyV2Executor` 并传入配置参数
3. 调用 `executor.start()` 启动循环执行
4. 处理 Ctrl+C 优雅退出

### Step 3: 适配 V2 策略的 `initialize()` 方法

V2策略的 `initialize()` 当前只创建内部策略但不初始化（避免网络下载），需要在执行器中使用 `use_binance_client=True` 模式时正常获取数据。

**修改点**：`chan_strategy_v2.py` 的 `initialize()` 方法中，当 `use_binance_client=True` 时调用内部策略的 `initialize()` 来获取实时数据。

### Step 4: 测试验证

1. 先以 `is_simulated=True` 模式启动，验证策略能正常生成信号（不下真实单）
2. 检查日志输出，确认信号生成和执行流程正确
3. 如有必要，可先运行 `--dry-run` 模式（仅生成信号不执行）