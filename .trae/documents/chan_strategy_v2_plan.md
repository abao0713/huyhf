# 缠论策略V2优化方案 - 分型驱动交易系统

## 📋 项目概述

基于现有 `chan_strategy.py` 创建新的 **ChanStrategyV2**，实现**分型驱动的快速交易系统**：
- **核心改变**：从"背驰判断"转向"分型识别"作为交易触发条件
- **交易模式**：底分型做多/顶分型做空 + 动态加仓 + 快速反转
- **目标品种**：ETHUSDC
- **配置化**：投入比例、杠杆、止损等参数完全可配置

---

## 🎯 核心策略逻辑

### 1️⃣ 买入（做多）逻辑

```
场景A: 空仓状态
├─ 识别到底分型 (bottom fractal)
│  └─ ✅ 开多单（首仓）
│
├─ 持仓中遇到新底分型
│  ├─ 加仓次数 < 3次？
│  │  └─ ✅ 继续加仓多单
│  └─ 加仓次数 >= 3次？
│     └─ ❌ 忽略（已达上限）
│
└─ 持仓中遇到顶分型
   └─ ⚡ 立即平掉所有多仓 + 开空单（反转）
```

### 2️⃣ 卖出（做空）逻辑

```
场景B: 空仓状态  
├─ 识别到顶分型 (top fractal)
│  └─ ✅ 开空单（首仓）
│
├─ 持仓中遇到新顶分型
│  ├─ 加仓次数 < 3次？
│  │  └─ ✅ 继续加仓空单
│  └─ 加仓次数 >= 3次？
│     └─ ❌ 忽略（已达上限）
│
└─ 持仓中遇到底分型
   └─ ⚡ 立即平掉所有空仓 + 开多单（反转）
```

### 3️⃣ 关键特性

| 特性 | 原策略 (V1) | 新策略 (V2) |
|------|------------|------------|
| **触发条件** | 背驰判断（MACD面积） | 分型识别（纯价格结构）|
| **信号延迟** | 较慢（需完整笔确认） | **更快**（分型出现即触发）|
| **加仓机制** | 无 | ✅ 最多3次 |
| **反转机制** | 需重新触发信号 | **即时反转**（顶/底分型切换）|
| **过滤条件** | RSI+EMA+ATR+量能等多重过滤 | **简化**（保留核心风控）|

---

## 📦 文件结构

### 新建文件

```
e:\Auto_test\huyhf\
├── trading_system/
│   └── strategies/
│       └── chan_strategy_v2.py    # 【新建】新策略实现
│
├── run_ethusdc_v2_backtest.py      # 【新建】ETHUSDC回测运行脚本
│
└── .trae/documents/
    └── chan_strategy_v2_plan.md    # 本计划文件
```

### 复用文件（无需修改）

- `trading_system/strategies/backtest_engine.py` - 回测引擎（已支持双仓位模式）
- `trading_system/strategies/base_strategy.py` - 策略基类
- `trading_system/backtest/run_backtest.py` - 回测入口（支持参数配置）

---

## 🔧 实施步骤

### 步骤1: 创建 ChanStrategyV2 策略类

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\chan_strategy_v2.py`

#### 1.1 继承基础结构

```python
from .base_strategy import BaseStrategy
from .chan_strategy import ChanStrategy  # 复用数据处理方法

class ChanStrategyV2(BaseStrategy):
    """
    缠论策略V2 - 分型驱动交易系统
    
    核心改进：
    - 使用分型识别替代背驰判断作为主要触发条件
    - 支持动态加仓（最多3次）
    - 支持即时反转（顶底分型切换时立即平仓反向开仓）
    """
```

#### 1.2 初始化参数（配置化）

```python
def __init__(
    self,
    symbol: str = "ETHUSDC",
    time_frame: str = "30m",
    hg1: int = 8,                    # 分型窗口（复用原参数）
    
    # ===== 交易配置（新增）=====
    max_add_positions: int = 3,       # 最大加仓次数
    investment_ratio: float = 0.10,   # 投入比例（10%）
    leverage: int = 20,               # 杠杆倍数
    
    # ===== 止损配置 ======
    long_stop_loss_ratio: float = 0.05,    # 多单固定止损5%
    short_stop_loss_ratio: float = 0.05,   # 空单固定止损5%
    use_atr_stop: bool = True,             # 是否使用ATR动态止损
    atr_multiplier: float = 3.5,           # ATR倍数
    
    # ===== 追踪止损配置 =====
    use_trailing_stop: bool = True,
    trailing_activation: float = 0.025,    # 激活阈值2.5%
    trailing_distance: float = 0.020,      # 追踪距离2%
):
```

#### 1.3 状态管理变量

```python
# 持仓状态跟踪
self.position_state = {
    "direction": None,           # "long" / "short" / None
    "entry_count": 0,            # 当前加仓次数（0=首仓, 1/2/3=加仓）
    "total_position_size": 0.0,  # 总持仓数量
    "avg_entry_price": 0.0,      # 平均入场价
    "initial_stop_loss": 0.0,    # 初始止损价
}

# 分型历史记录（用于检测新分型）
self.last_fractal_type = None   # 上一次分型类型
self.last_fractal_idx = -1      # 上一次分型索引
```

#### 1.4 核心方法：generate_signal()

**位置**: 重写父类的信号生成逻辑

```python
def generate_signal(self) -> Optional[Dict[str, Any]]:
    """
    V2策略信号生成逻辑
    
    流程：
    1. 检查最新分型（是否出现新的顶/底分型）
    2. 根据当前持仓状态决定操作：
       - 空仓 + 底分型 → BUY（首仓）
       - 持多 + 底分型 → BUY_ADD（加仓，<3次）
       - 持多 + 顶分型 → CLOSE_LONG + SELL（反转）
       - 空仓 + 顶分型 → SELL（首仓）
       - 持空 + 顶分型 → SELL_ADD（加仓，<3次）
       - 持空 + 底分型 → CLOSE_SHORT + BUY（反转）
    3. 计算止损和仓位大小
    4. 返回信号字典
    """
    
    # 1. 获取最新的分型
    latest_fractal = self._get_latest_fractal()
    if not latest_fractal:
        return {"action": "HOLD"}
    
    # 2. 判断是新分型还是旧分型
    if not self._is_new_fractal(latest_fractal):
        return {"action": "HOLD"}  # 已处理过，跳过
    
    # 3. 根据分型和持仓状态生成信号
    current_state = self.position_state["direction"]
    fractal_type = latest_fractal.type  # "top" or "bottom"
    
    if current_state is None:
        # ===== 空仓状态 =====
        if fractal_type == "bottom":
            return self._create_buy_signal(latest_fractal, is_first=True)
        elif fractal_type == "top":
            return self._create_sell_signal(latest_fractal, is_first=True)
            
    elif current_state == "long":
        # ===== 持有多单 =====
        if fractal_type == "bottom":
            # 底分型：考虑加仓
            if self.position_state["entry_count"] < self.max_add_positions:
                return self._create_buy_signal(latest_fractal, is_add=True)
            else:
                logger.info("已达最大加仓次数(3次)，忽略底分型")
                return {"action": "HOLD"}
        elif fractal_type == "top":
            # 顶分型：立即反转！
            return self._create_reversal_signal("long_to_short", latest_fractal)
            
    elif current_state == "short":
        # ===== 持有空单 =====
        if fractal_type == "top":
            # 顶分型：考虑加仓
            if self.position_state["entry_count"] < self.max_add_positions:
                return self._create_sell_signal(latest_fractal, is_add=True)
            else:
                logger.info("已达最大加仓次数(3次)，忽略顶分型")
                return {"action": "HOLD"}
        elif fractal_type == "bottom":
            # 底分型：立即反转！
            return self._create_reversal_signal("short_to_long", latest_fractal)
    
    return {"action": "HOLD"}
```

#### 1.5 辅助方法

```python
def _get_latest_fractal(self) -> Optional[Fractal]:
    """获取最新的分型（最后一个分型）"""
    if not self.fractals:
        return None
    return self.fractals[-1]

def _is_new_fractal(self, fractal: Fractal) -> bool:
    """检查是否是新的未处理分型"""
    if self.last_fractal_idx != fractal.idx:
        self.last_fractal_idx = fractal.idx
        self.last_fractal_type = fractal.type
        return True
    return False

def _create_buy_signal(self, fractal: Fractal, is_first: bool=False, is_add: bool=False) -> Dict:
    """创建买入信号"""
    entry_price = fractal.low * 1.001  # 在底分型低点上方入场
    
    signal = {
        "action": "BUY",
        "entry_price": entry_price,
        "stop_loss": self._calculate_long_stop_loss(entry_price),
        "reason": f"{'首仓' if is_first else '加仓(' + str(self.position_state['entry_count']+1) + '/3)'} - 底分型@{fractal.low:.2f}",
        "position": "long",
        "is_first_position": is_first,
        "is_add_position": is_add,
        "fractal_idx": fractal.idx,
    }
    return signal

def _create_sell_signal(self, fractal: Fractal, is_first: bool=False, is_add: bool=False) -> Dict:
    """创建卖出信号"""
    entry_price = fractal.high * 0.999  # 在顶分型高点下方入场
    
    signal = {
        "action": "SELL",
        "entry_price": entry_price,
        "stop_loss": self._calculate_short_stop_loss(entry_price),
        "reason": f"{'首仓' if is_first else '加仓(' + str(self.position_state['entry_count']+1) + '/3)'} - 顶分型@{fractal.high:.2f}",
        "position": "short",
        "is_first_position": is_first,
        "is_add_position": is_add,
        "fractal_idx": fractal.idx,
    }
    return signal

def _create_reversal_signal(self, reversal_type: str, fractal: Fractal) -> Dict:
    """创建反转信号（平仓+反向开仓）"""
    if reversal_type == "long_to_short":
        action = "REVERSE_TO_SHORT"
        close_reason = f"顶分型反转@{fractal.high:.2f}"
        new_action = "SELL"
    else:  # short_to_long
        action = "REVERSE_TO_LONG"
        close_reason = f"底分型反转@{fractal.low:.2f}"
        new_action = "BUY"
    
    signal = {
        "action": action,
        "close_reason": close_reason,
        "new_action": new_action,
        "new_entry_price": fractal.low if new_action == "BUY" else fractal.high,
        "new_stop_loss": self._calculate_long_stop_loss(fractal.low) if new_action == "BUY" else self._calculate_short_stop_loss(fractal.high),
        "reason": f"⚡ 反转信号: {close_reason}",
        "fractal_idx": fractal.idx,
    }
    return signal

def _calculate_long_stop_loss(self, entry_price: float) -> float:
    """计算多单止损价"""
    if self.use_atr_stop and self.current_atr > 0:
        return entry_price - (self.current_atr * self.atr_multiplier)
    else:
        return entry_price * (1 - self.long_stop_loss_ratio)

def _calculate_short_stop_loss(self, entry_price: float) -> float:
    """计算空单止损价"""
    if self.use_atr_stop and self.current_atr > 0:
        return entry_price + (self.current_atr * self.atr_multiplier)
    else:
        return entry_price * (1 + self.short_stop_loss_ratio)
```

#### 1.6 数据处理（复用V1）

```python
async def initialize(self, symbol: str) -> bool:
    """初始化策略（复用V1的数据获取和处理）"""
    self.symbol = symbol
    # 直接调用父类ChanStrategy的数据处理方法
    parent_strategy = ChanStrategy(
        symbol=symbol,
        time_frame=self.time_frame,
        hg1=self.hg1,
        use_binance_client=False
    )
    
    success = await parent_strategy.initialize(symbol)
    if success:
        # 复用处理后的数据
        self.fractals = parent_strategy.fractals
        self.pens = parent_strategy.pens
        self.segments = parent_strategy.segments
        self.df_processed = parent_strategy.df_processed
        self.df_30m = parent_strategy.df_30m
        self.df_daily = parent_strategy.df_daily
        
        # 计算ATR（用于动态止损）
        self._calculate_atr()
        
    return success
```

---

### 步骤2: 修改回测引擎以支持V2策略

**文件**: `e:\Auto_test\huyhf\trading_system\strategies\backtest_engine.py`

#### 2.1 新增信号处理逻辑（在 `_execute_trade` 方法中）

在现有的 BUY/SELL 处理逻辑基础上，增加：

```python
def _execute_trade(self, signal: Dict[str, Any], kline) -> None:
    action = signal.get("action")
    
    # ===== V2新增：反转信号处理 =====
    if action == "REVERSE_TO_SHORT":
        # 1. 平掉所有多仓
        if self.long_position > 0:
            self._close_all_long(signal.get("close_reason", "反转平仓"))
        
        # 2. 开空单（使用新信号的价格）
        signal["action"] = "SELL"
        signal["is_first_position"] = True
        self._execute_single_trade(signal, kline, direction="short")
        return
        
    elif action == "REVERSE_TO_LONG":
        # 1. 平掉所有空仓
        if self.short_position > 0:
            self._close_all_short(signal.get("close_reason", "反转平仓"))
        
        # 2. 开多单
        signal["action"] = "BUY"
        signal["is_first_position"] = True
        self._execute_single_trade(signal, kline, direction="long")
        return
    
    # ===== 原有逻辑：普通BUY/SELL =====
    if action == "BUY":
        if signal.get("is_add_position"):
            # 加仓逻辑
            self._execute_add_trade(signal, kline, direction="long")
        else:
            # 首仓逻辑
            self._execute_single_trade(signal, kline, direction="long")
            
    elif action == "SELL":
        if signal.get("is_add_position"):
            # 加仓逻辑
            self._execute_add_trade(signal, kline, direction="short")
        else:
            # 首仓逻辑
            self._execute_single_trade(signal, kline, direction="short")
```

#### 2.2 新增辅助方法

```python
def _close_all_long(self, reason: str) -> None:
    """平掉所有多仓"""
    if self.long_position <= 0:
        return
    current_price = self._get_current_price(kline)
    self._close_long(timestamp=current_time, price=current_price, reason=reason)
    logger.info(f"[V2] 平掉全部多仓: {self.long_position:.4f}个, 原因: {reason}")

def _close_all_short(self, reason: str) -> None:
    """平掉所有空仓"""
    if self.short_position <= 0:
        return
    current_price = self._get_current_price(kline)
    self._close_short(timestamp=current_time, price=current_price, reason=reason)
    logger.info(f"[V2] 平掉全部空仓: {self.short_position:.4f}个, 原因: {reason}")

def _execute_single_trade(self, signal, kline, direction: str) -> None:
    """执行首仓交易"""
    # 计算仓位大小（使用investment_ratio）
    base_amount = self.balance * self.config.investment_ratio
    actual_amount = base_amount  # 首仓不应用其他系数
    
    # 执行开仓...
    if direction == "long":
        self._open_long(...)
        strategy.update_position_state("long", entry_count=0)
    else:
        self._open_short(...)
        strategy.update_position_state("short", entry_count=0)

def _execute_add_trade(self, signal, kline, direction: str) -> None:
    """执行加仓交易"""
    # 加仓可以使用更小的仓位（例如首仓的50%）
    base_amount = self.balance * self.config.investment_ratio * 0.5
    
    # 执行加仓...
    if direction == "long":
        self._open_long(...)
        current_count = strategy.position_state["entry_count"]
        strategy.update_position_state("long", entry_count=current_count + 1)
    else:
        self._open_short(...)
        current_count = strategy.position_state["entry_count"]
        strategy.update_position_state("short", entry_count=current_count + 1)
```

---

### 步骤3: 创建 ETHUSDC 回测运行脚本

**文件**: `e:\Auto_test\huyhf\run_ethusdc_v2_backtest.py`

```python
"""
缠论策略V2 - ETHUSDC 30分钟回测脚本
分型驱动交易系统测试
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BACKTEST_SCRIPT = PROJECT_ROOT / "trading_system" / "backtest" / "run_backtest.py"


def get_date_range(days=60):
    """获取日期范围（默认最近60天）"""
    today = datetime.now()
    end_date = today.strftime("%Y-%m-%d")
    start_date = (today - timedelta(days=days)).strftime("%Y-%m-%d")
    return start_date, end_date


def main():
    print("=" * 70)
    print("🚀 缠论策略V2 - ETHUSDC 30分钟回测")
    print("   特性: 分型驱动 + 动态加仓(最多3次) + 即时反转")
    print("=" * 70)
    
    start_date, end_date = get_date_range(days=60)
    
    cmd = [
        sys.executable,
        str(BACKTEST_SCRIPT),
        
        # ===== 基础配置 =====
        "--symbol", "ETHUSDC",
        "--interval", "30m",
        "--initial-balance", "10000",
        
        # ===== 日期范围 =====
        "--start-date", start_date,
        "--end-date", end_date,
        
        # ===== 仓位管理配置 =====
        "--investment-ratio", "0.10",         # 10%投入
        "--leverage", "20",                     # 20倍杠杆
        
        # ===== 止损配置 =====
        "--long-stop-loss-multiplier", "1.50",  # 多单止损150%
        "--short-stop-loss-multiplier", "0.70", # 空单止损70%
        
        # ===== V2特有参数（通过环境变量或配置文件传递）=====
        # 注意：这些参数需要在 run_backtest.py 中添加对应的命令行选项
    ]
    
    print("\n📊 配置信息:")
    print(f"  交易对: ETHUSDC")
    print(f"  K线周期: 30分钟")
    print(f"  初始资金: $10,000")
    print(f"  数据范围: {start_date} ~ {end_date}")
    print(f"  投入比例: 10%")
    print(f"  杠杆倍数: 20x")
    print(f"  最大加仓: 3次")
    print(f"  多单止损: 爆仓价 × 150%")
    print(f"  空单止损: 爆仓价 × 70%")
    print("\n" + "-" * 70)
    
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), check=False)
    
    if result.returncode == 0:
        print("\n✅ 回测成功完成！")
        print("\n📈 生成的图表:")
        print(f"  - 缠论图表: backtest_plot.png")
        print(f"  - 权益曲线: charts/equity_curve.png")
        print(f"  - 收益率图: charts/returns.png")
        print(f"  - 回撤图: charts/drawdown.png")


if __name__ == "__main__":
    main()
```

---

### 步骤4: 扩展 run_backtest.py 的命令行参数

**文件**: `e:\Auto_test\huyhf\trading_system\backtest\run_backtest.py`

在 `parse_args()` 函数中添加V2特有参数：

```python
# V2策略特有参数
parser.add_argument(
    "--strategy-version",
    type=str,
    default="v1",
    choices=["v1", "v2"],
    help="策略版本（v1=原始背驰策略, v2=分型驱动策略）"
)

parser.add_argument(
    "--max-add-positions",
    type=int,
    default=3,
    help="V2策略: 最大加仓次数（默认3次）"
)

parser.add_argument(
    "--use-atr-stop",
    action="store_true",
    default=True,
    help="V2策略: 是否使用ATR动态止损"
)
```

并在 `run_backtest()` 函数中根据版本选择策略：

```python
if args.strategy_version == "v2":
    from trading_system.strategies.chan_strategy_v2 import ChanStrategyV2
    strategy = ChanStrategyV2(
        symbol=symbol,
        hg1=hg1,
        max_add_positions=args.max_add_positions,
        investment_ratio=investment_ratio,
        leverage=leverage,
        use_atr_stop=args.use_atr_stop,
    )
else:
    strategy = ChanStrategy(symbol=symbol, hg1=hg1, use_binance_client=False)
```

---

## 🎨 信号流程图

```
K线数据更新
    ↓
_process_data()  ← 复用V1的数据处理
    ↓
识别分型 (fractals列表)
    ↓
获取最新分型 → _get_latest_fractal()
    ↓
是否新分型？ → _is_new_fractal()
    ├─ 否 → HOLD（跳过）
    └─ 是 ↓
当前持仓状态？
    ├─ None（空仓）
    │   ├─ 底分型 → BUY（首仓）
    │   └─ 顶分型 → SELL（首仓）
    │
    ├─ long（持多）
    │   ├─ 底分型 → 加仓次数<3? 
    │   │   ├─ YES → BUY_ADD（加仓+1）
    │   │   └─ NO  → HOLD
    │   └─ 顶分型 → REVERSE_TO_SHORT（平多+开空）
    │
    └─ short（持空）
        ├─ 顶分型 → 加仓次数<3?
        │   ├─ YES → SELL_ADD（加仓+1）
        │   └─ NO  → HOLD
        └─ 底分型 → REVERSE_TO_LONG（平空+开多）
    ↓
返回信号字典 → BacktestEngine执行
```

---

## ⚙️ 配置参数说明

### 运行时配置（命令行参数）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--symbol` | ETHUSDC | 交易对 |
| `--interval` | 30m | K线周期 |
| `--initial-balance` | 10000 | 初始资金($）|
| `--investment-ratio` | 0.10 | 投入比例(10%) |
| `--leverage` | 20 | 杠杆倍数 |
| `--long-stop-loss-multiplier` | 1.50 | 多单止损倍数 |
| `--short-stop-loss-multiplier` | 0.70 | 空单止损倍数 |
| `--strategy-version` | v1 | 策略版本(v1/v2) |
| `--max-add-positions` | 3 | 最大加仓次数 |
| `--start-date` | 近60天 | 开始日期 |
| `--end-date` | 今天 | 结束日期 |

### 策略内部配置（代码常量）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `hg1` | 8 | 分型窗口大小 |
| `long_stop_loss_ratio` | 0.05 | 多单固定止损(5%) |
| `short_stop_loss_ratio` | 0.05 | 空单固定止损(5%) |
| `atr_multiplier` | 3.5 | ATR止损倍数 |
| `trailing_activation` | 0.025 | 追踪止损激活(2.5%) |
| `trailing_distance` | 0.020 | 追踪止损距离(2%) |

---

## 🧪 测试计划

### 1. 单元测试

- [ ] 测试 `_get_latest_fractal()` 正确返回最后分型
- [ ] 测试 `_is_new_fractal()` 正确识别新旧分型
- [ ] 测试加仓计数器正确累加（0→1→2→3→停止）
- [ ] 测试反转信号生成（long_to_short / short_to_long）
- [ ] 测试止损计算（固定比率 vs ATR动态）

### 2. 集成测试

- [ ] 运行30天数据回测，验证无报错
- [ ] 检查交易记录中的加仓/反转操作是否符合预期
- [ ] 对比V1和V2的收益率、最大回撤、胜率指标
- [ ] 验证图表生成正常（包含分型标记、买卖点）

### 3. 性能测试

- [ ] 60天30m数据的回测时间 < 30秒
- [ ] 内存占用 < 500MB

---

## 📊 预期效果对比

| 指标 | V1（背驰策略） | V2（分型策略）预期 |
|------|----------------|-------------------|
| **交易频率** | 低（等待背驰） | **高**（每个分型都触发）|
| **响应速度** | 慢（需完整笔确认） | **快**（分型出现即反应）|
| **加仓能力** | 无 | ✅ 最多3次 |
| **反转速度** | 需重新触发信号 | **即时反转** |
| **风险等级** | 中等 | **较高**（频繁交易）|
| **适用市场** | 趋势明显行情 | **震荡+趋势均可** |

---

## ⚠️ 风险提示

1. **频繁交易成本**：V2会显著增加交易次数，手续费累积较多
2. **假突破风险**：分型可能失败（被后续K线破坏），需配合确认机制
3. **加仓风险**：连续加仓3次后如果行情不利，亏损会放大
4. **杠杆风险**：20倍杠杆在震荡市中容易触发止损

**建议**：
- 先用小资金实盘测试1-2周
- 观察加仓频率，如果太频繁可降低至2次
- 监控最大回撤，如果>15%需调整参数

---

## 🚀 实施优先级

1. **P0 (必须)**: 完成 `chan_strategy_v2.py` 核心逻辑
2. **P0 (必须)**: 修改 `backtest_engine.py` 支持反转信号
3. **P1 (重要)**: 创建 `run_ethusdc_v2_backtest.py` 运行脚本
4. **P1 (重要)**: 扩展 `run_backtest.py` 命令行参数
5. **P2 (优化)**: 添加单元测试
6. **P2 (优化)**: 性能优化和日志完善

---

## 📝 后续优化方向

1. **分型确认机制**：要求后续1-2根K线确认分型有效才触发（减少假突破）
2. **自适应加仓**：根据ATR波动率动态调整加仓次数（高波动少加仓）
3. **时间过滤**：避开低流动性时段（亚盘）的加仓操作
4. **量能过滤**：放量分型才触发，缩量分型降低仓位
5. **机器学习增强**：训练模型预测分型成功率，动态调整仓位大小

---

**预计开发时间**: 2-3小时（核心功能）
**预计测试时间**: 1小时（回测验证）
