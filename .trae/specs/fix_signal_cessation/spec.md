# 修复V2策略K线索引100后信号停止 Spec

## Why
V2策略的`generate_signal()`方法按调用次数依次处理分型，而非按K线索引匹配分型。每次调用`_current_fractal_idx++`，导致~100个分型在100次调用后被耗尽，剩余4000+根K线全部返回HOLD，回测图表在索引100后无任何交易信号。

## What Changes
- **修复 `generate_signal()`**：改为按K线索引匹配分型，而非顺序消耗
- **修复 回测引擎主循环**：传递当前bar索引给 `generate_signal(bar_idx)`
- **修复 `on_bar()`**：支持传递bar索引参数
- 保持与现有回测引擎完全兼容（默认参数兜底）

## Impact
- Affected specs: 无
- Affected code: `chan_strategy_v2.py` (generate_signal, on_bar), `backtest_engine.py` (主循环)

## 根因分析

### 问题代码
[chan_strategy_v2.py:L534-L603](file:///e:/Auto_test/huyhf/trading_system/strategies/chan_strategy_v2.py#L534-L603)

```python
def generate_signal(self) -> Optional[Dict[str, Any]]:
    if self._current_fractal_idx >= len(self.fractals):
        return {"action": "HOLD"}
    fractal = self.fractals[self._current_fractal_idx]
    # ... 生成信号 ...
    self._current_fractal_idx += 1  # 每调用一次就+1
```

### 调用路径
[backtest_engine.py:L590](file:///e:/Auto_test/huyhf/trading_system/strategies/backtest_engine.py#L590)
```python
for i, (kline, daily_end_idx) in iterator:  # i=0..999 (1000根K线)
    signal = strategy.generate_signal()  # 每根K线调用一次，无bar索引
```

### 后果
- 1000根K线（90天30m数据限制1000根），但只有~100个分型
- `generate_signal()`被调用1000次，`_current_fractal_idx`从0递增到1000
- 索引100后`_current_fractal_idx >= len(fractals)` → 永远返回HOLD
- 剩余900根K线零信号，图表在K线100处戛然而止

## MODIFIED Requirements

### Requirement: 分型信号按K线索引匹配
V2策略的`generate_signal(bar_idx)` SHOULD 接受当前K线索引参数，仅当存在分型的`idx`匹配当前bar时才生成信号。

#### Scenario: 正常匹配分型
- **GIVEN** 分型列表 `[{idx: 5, type: "bottom"}, {idx: 20, type: "top"}, ...]`
- **WHEN** 回测引擎调用 `generate_signal(bar_idx=5)`
- **THEN** 生成底分型买入信号
- **WHEN** 回测引擎调用 `generate_signal(bar_idx=6)` 到 `generate_signal(bar_idx=19)`
- **THEN** 返回HOLD（无分型在这些位置）
- **WHEN** 回测引擎调用 `generate_signal(bar_idx=20)`
- **THEN** 生成顶分型卖出/反转信号

#### Scenario: 全部K线覆盖
- **GIVEN** 回测有1000根K线，100个分型分布在0-999之间
- **WHEN** 回测完成后
- **THEN** 100个分型对应的K线位置生成了100个信号，其余900个位置返回HOLD，而非从第100根后再无信号

### Requirement: 向后兼容的无参数调用
`generate_signal()` 在无参数调用时 SHALL 保持原有顺序处理行为，通过`on_bar`方法桥接。

### Requirement: 回测引擎传递bar索引
回测引擎的主循环 SHALL 在调用 `strategy.generate_signal()` 时传递当前bar索引`i`。