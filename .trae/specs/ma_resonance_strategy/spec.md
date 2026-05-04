# 缠论与均线共振交易策略 Spec

## Why
单一技术指标容易产生假信号。将缠论买卖点（基于价格结构和MACD背驰）与均线支撑/压力位结合，可以显著提高信号的可靠性：
- **共振确认**: 两种独立方法同时发出信号 → 高质量操作机会
- **矛盾处理**: 缠论结构优先，但通过仓位管理控制风险
- **风险降低**: 在不确定情况下减少仓位或保持观望

## What Changes
本规格为**策略增强功能**，在现有缠论策略基础上增加均线支撑/压力验证层：

### 核心功能
- 实现均线支撑/压力位识别算法（MA20、MA60等关键均线）
- 定义缠论信号与均线的共振判定规则
- 修改信号生成逻辑，加入共振强度分级
- 调整仓位管理策略（根据共振等级动态调整）
- 增强日志输出和可视化标注

### 影响范围
- **主要修改文件**:
  - `chan_strategy.py`: 增加 `_check_ma_support_resistance()`, 修改 `generate_signal()`
  - `backtest_engine.py`: 根据 resonance_level 调整仓位大小
  - `chan_plotter.py`: 在图表上标注均线和共振信号

### 非破坏性变更
- ✅ 保持原有背驰判断逻辑不变
- ✅ 向后兼容：无共振模式时行为与原版一致
- ✅ 可配置开关：支持启用/禁用共振验证

---

## ADDED Requirements

### Requirement: 均线支撑/压力识别系统

#### 1.1 均线计算模块
系统 SHALL 提供多周期均线计算能力：

**配置参数**:
```python
MA_CONFIG = {
    "ma_short": 20,      # 短期均线（支撑/压力参考）
    "ma_medium": 60,     # 中期均线（趋势确认）
    "ma_long": 120,      # 长期均线（大趋势方向）
}
```

**WHEN** 系统初始化或数据更新时  
**THEN** 自动计算指定周期的SMA/EMA均线序列并存储为实例属性

#### 1.2 支撑位识别规则
系统 SHALL 能够识别价格获得均线支撑的情况：

**场景: 价格接近并获得短期均线支撑**
- **GIVEN** 当前价格为 P，短期均线（如MA20）价格为 M
- **AND** 价格从上方回落至均线附近（P ≈ M，偏差 < 0.5%）
- **AND** 出现止跌K线形态（如锤子线、十字星）或成交量萎缩
- **THEN** 判定为 **"均线支撑"** 信号，返回 `support_level = "strong"` 或 `"weak"`

**具体条件**:
```python
def _check_ma_support(self, price, ma_price, tolerance=0.005):
    """
    判断是否获得均线支撑
    
    Args:
        price: 当前价格
        ma_price: 均线价格
        tolerance: 容差比例（默认0.5%）
    
    Returns:
        support_level: "strong" | "weak" | None
    """
    ratio = abs(price - ma_price) / ma_price
    if ratio <= tolerance * 0.5:      # 极近距离（<0.25%）
        return "strong"
    elif ratio <= tolerance:           # 接近距离（<0.5%）
        return "weak"
    else:
        return None
```

#### 1.3 压力位识别规则
系统能够识别价格遇到均线压力的情况：

**场景: 价格接近但未能突破中期均线**
- **GIVEN** 当前价格为 P，中期均线（如MA60）价格为 M
- **AND** 价格从下方上涨至均线附近（P ≈ M，偏差 < 0.5%）
- **AND** 出现滞涨K线形态（如射击之星、乌云盖顶）或放量滞涨
- **THEN** 判定为 **"均线压力"** 信号，返回 `resistance_level = "strong"` 或 `"weak"`

---

### Requirement: 共振判定引擎

#### 2.1 共振定义与分级
系统 SHALL 将缠论信号与均线信号组合，定义以下共振级别：

| 共振级别 | 条件描述 | 操作建议 |
|---------|---------|---------|
| **强烈共振 (Strong)** | 缠论信号 + 强支撑/压力 + 日线趋势同向 | 满仓操作（100%标准仓位）|
| **一般共振 (Normal)** | 缠论信号 + 弱支撑/压力 或 无均线信号但趋势同向 | 正常操作（70%标准仓位）|
| **弱共振 (Weak)** | 缠论信号 + 均线信号矛盾 或 趋势反向 | 降低仓位（30-50%）或观望 |
| **无共振 (None)** | 仅缠论信号，无均线信息 | 正常操作（需谨慎）|

#### 2.2 底背驰 + 均线支撑共振
**场景: 买入信号的质量评估**

**WHEN** 检测到底背驰（`_check_bottom_divergence()` 返回 True）
**THEN** 执行以下共振检查：

```python
def _evaluate_buy_signal_resonance(self, pen):
    """
    评估买入信号的共振强度
    
    Returns:
        resonance_level: "strong" | "normal" | "weak" | "none"
        reason: 共振原因说明
    """
    chan_signal = "BUY (底背驰)"
    daily_trend = self._get_daily_trend()
    
    # 检查均线支撑
    ma_support = self._check_ma_support(
        price=pen.low,
        ma_price=self.ma_short.iloc[-1]  # MA20
    )
    
    # 判定共振级别
    if ma_support == "strong" and daily_trend in ["up", "neutral"]:
        return "strong", f"{chan_signal} + 强支撑(MA20) + {daily_trend}趋势"
    elif ma_support == "weak" and daily_trend != "down":
        return "normal", f"{chan_signal} + 弱支撑 + {daily_trend}趋势"
    elif daily_trend == "down":
        return "weak", f"{chan_signal} + 下降趋势(矛盾)"
    else:
        return "none", f"{chan_signal} (纯缠论信号)"
```

**示例输出**:
```
[ChanStrategy] 信号评估: STRONG 共振
  - 缠论信号: BUY (底背驰)
  - 均线状态: 价格2250触及MA20(2248)强支撑
  - 日线趋势: neutral
  - 建议: 满仓买入
```

#### 2.3 顶背驰 + 均线压力共振
**场景: 卖出信号的质量评估**

**WHEN** 检测到顶背驰（`_check_top_divergence()` 返回 True）
**THEN** 执行类似共振检查：

```python
def _evaluate_sell_signal_resonance(self, pen):
    """
    评估卖出信号的共振强度
    
    Returns:
        resonance_level: "strong" | "normal" | "weak" | "none"
        reason: 共振原因说明
    """
    chan_signal = "SELL (顶背驰)"
    daily_trend = self._get_daily_trend()
    
    # 检查均线压力
    ma_resistance = self._check_ma_resistance(
        price=pen.high,
        ma_price=self.ma_medium.iloc[-1]  # MA60
    )
    
    # 判定共振级别
    if ma_resistance == "strong" and daily_trend in ["down", "neutral"]:
        return "strong", f"{chan_signal} + 强压力(MA60) + {daily_trend}趋势"
    elif ma_resistance == "weak" and daily_trend != "up":
        return "normal", f"{chan_signal} + 弱压力 + {daily_trend}趋势"
    elif daily_trend == "up":
        return "weak", f"{chan_signal} + 上升趋势(矛盾)"
    else:
        return "none", f"{chan_signal} (纯缠论信号)"
```

---

### Requirement: 动态仓位管理系统

#### 3.1 仓位调整矩阵
系统 SHALL 根据共振级别自动调整仓位大小：

**配置参数**:
```python
RESONANCE_POSITION_SIZING = {
    "strong": 1.0,    # 100% 标准仓位
    "normal": 0.7,    # 70% 标准仓位
    "weak": 0.4,      # 40% 标准仓位（或观望）
    "none": 0.7,      # 70% 标准仓位（保守）
}
```

**WHEN** 生成交易信号时
**THEN** 信号字典包含 `resonance_level` 字段，回测引擎据此调整实际投入金额

**修改后的信号格式**:
```python
signal = {
    "action": "BUY" | "SELL" | "HOLD",
    "resonance_level": "strong" | "normal" | "weak" | "none",
    "reason": "详细原因说明",
    "position_size_ratio": 0.4 ~ 1.0,  # 仓位比例
    "stop_loss": 止损价格,
    "ma_support_resistance": {
        "ma_type": "MA20" | "MA60",
        "ma_price": 2248.50,
        "signal_type": "support" | "resistance" | null,
        "strength": "strong" | "weak" | null
    }
}
```

#### 3.2 回测引擎适配
**WHEN** 回测引擎执行交易 (`_execute_trade()`)
**THEN** 从信号中读取 `position_size_ratio` 并调整投入金额：

```python
# 原始代码
buy_amount = self.balance * investment_ratio  # 固定10%

# 修改后
base_amount = self.balance * investment_ratio
actual_amount = base_amount * signal.get("position_size_ratio", 0.7)
# 例如: strong共振 → actual_amount = balance * 10% * 1.0 = 10%
#       weak共振   → actual_amount = balance * 10% * 0.4 = 4%
```

---

### Requirement: 可视化增强

#### 4.1 图表标注
系统 SHALL 在回测图表上清晰展示共振信息：

**标注内容**:
- 绘制 MA20（蓝色）、MA60（橙色）、MA120（紫色）均线
- 在买卖信号旁添加共振级别标签（★ strongly / ○ normal / △ weak）
- 用不同颜色区分共振强度（绿色=强，黄色=正常，红色=弱）

**示例效果**:
```
价格走势图:
  ┃                    ★ SELL (顶背驰+MA60压力)
  ┃                 ╱
  ┃  ╲────────────╱  ← MA60 压力位
  ┃   ╲          ╱
  ┃    ╲   ★ BUY (底背驰+MA20支撑)
  ┃     ╲  ╱
  ┃      ╲╱  ← MA20 支撑位
  ┃━━━━━━━━━━━━━━━ MA20 (蓝)
  ┃━━━━━━━━━━━━━━━━━━━━━━━━━ MA60 (橙)
```

---

## MODIFIED Requirements

### Requirement: generate_signal() 方法增强

**原实现**:
```python
def generate_signal(self):
    if last_pen.direction == "down":
        if self._check_bottom_divergence(last_pen):
            return {"action": "BUY", "reason": "底背驰"}
    elif last_pen.direction == "up":
        if self._check_top_divergence(last_pen):
            return {"action": "SELL", "reason": "顶背驰"}
    return {"action": "HOLD"}
```

**修改后**:
```python
def generate_signal(self):
    signal = {"action": "HOLD", "resonance_level": "none"}
    
    if last_pen.direction == "down":
        if self._check_bottom_divergence(last_pen):
            resonance, reason = self._evaluate_buy_signal_resonance(last_pen)
            signal = {
                "action": "BUY",
                "resonance_level": resonance,
                "reason": reason,
                "position_size_ratio": RESONANCE_POSITION_SIZING[resonance],
                ...  # 其他字段
            }
    
    elif last_pen.direction == "up":
        if self._check_top_divergence(last_pen):
            resonance, reason = self._evaluate_sell_signal_resonance(last_pen)
            signal = {
                "action": "SELL",
                "resonance_level": resonance,
                "reason": reason,
                "position_size_ratio": RESONANCE_POSITION_SIZING[resonance],
                ...
            }
    
    # 记录详细日志
    logger.info(f"[ChanStrategy] 共振信号: {signal}")
    return signal
```

**影响**:
- 信号字典新增字段（向后兼容，旧字段保留）
- 调用链中增加共振评估步骤
- 日志输出更丰富

---

## Impact Analysis

### Affected Specs
- `divergence_analysis`: 背驰判断机制（作为基础，不修改）
- `continuous_klines_api`: 数据获取（可能需要获取更多历史数据以计算长期均线）

### Affected Code Files
1. **chan_strategy.py** (主要修改)
   - 新增: `_calculate_mavgs()`, `_check_ma_support()`, `_check_ma_resistance()`
   - 新增: `_evaluate_buy_signal_resonance()`, `_evaluate_sell_signal_resonance()`
   - 修改: `generate_signal()` - 增加共振评估
   - 修改: `__init__()` - 增加均线配置参数

2. **backtest_engine.py** (次要修改)
   - 修改: `_execute_trade()` - 根据 position_size_ratio 调整仓位

3. **chan_plotter.py** (可视化增强)
   - 修改: `plot()` - 增加均线绘制
   - 修改: `_plot_signals()` - 显示共振级别标签

4. **run_backtest.py** (配置扩展)
   - 新增命令行参数: `--enable-resonance`, `--ma-short`, `--ma-medium`, `--ma-long`

### Risk Assessment
- **风险等级**: 低（增强型功能，不影响核心逻辑）
- **回退方案**: 通过 `--enable-resonance false` 禁用新功能，恢复原始行为
- **测试策略**: 先在小范围数据上验证，再全面推广

---

## Implementation Phases

### Phase 1: 基础设施（低风险）
- [ ] 实现均线计算和存储
- [ ] 实现支撑/压力识别算法
- [ ] 单元测试：验证识别准确性

### Phase 2: 共振引擎（中风险）
- [ ] 实现共振判定逻辑
- [ ] 修改 `generate_signal()` 方法
- [ ] 增强日志输出
- [ ] 集成测试：验证信号质量提升

### Phase 3: 仓位管理（低风险）
- [ ] 修改回测引擎的仓位计算
- [ ] 测试不同共振级别的仓位调整
- [ ] 性能对比：有/无共振的收益差异

### Phase 4: 可视化与优化（低风险）
- [ ] 图表绘制均线和共振标注
- [ ] 参数优化（均线周期选择）
- [ ] 文档更新和用户指南

---

## Success Metrics

### 定量指标
- **信号准确率**: 共振信号胜率 > 非共振信号胜率
- **最大回撤**: 使用共振策略后回撤降低 > 15%
- **夏普比率**: 共振策略 Sharpe > 原始策略 Sharpe
- **交易频率**: 弱共振信号触发频率降低 30-50%（过滤假信号）

### 定性指标
- **可解释性**: 每个信号都有清晰的共振原因说明
- **可视化**: 图表直观显示共振关系
- **灵活性**: 用户可自定义均线参数和仓位比例

---

## Configuration Examples

### 示例1: 启用共振策略（推荐配置）
```bash
python run_backtest.py \
  --symbol ETHUSDT \
  --interval 30m \
  --enable-resonance true \
  --ma-short 20 \
  --ma-medium 60 \
  --ma-long 120 \
  --investment-ratio 0.10
```

### 示例2: 保守模式（仅强烈共振才操作）
```python
# 自定义配置
config = {
    "enable_resonance": True,
    "only_strong_resonance": True,  # 只执行 strong 级别信号
    "weak_resonance_action": "skip",  # weak 级别跳过
}
```

### 示例3: 禁用共振（兼容旧版本）
```bash
python run_backtest.py \
  --symbol ETHUSDT \
  --interval 30m \
  --enable-resonance false  # 行为与原版完全一致
```
