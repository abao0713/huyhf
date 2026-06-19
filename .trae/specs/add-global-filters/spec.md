# 全局过滤器（强制） Spec

## Why
当前策略缺少强制性的全局风控过滤器，导致在不适合的市场环境下开仓（如逆日线趋势做多、中枢震荡频繁时追趋势单、资金费率极端时开单），且止损止盈规则过于单一，无盈亏比过滤。需要添加不可绕过的全局过滤器来提升策略稳健性。

## What Changes
- 新增 **日线 MA60 趋势过滤器**：Daily Close vs MA60 决定只允许做多或做空方向
- 新增 **4H 中枢震荡过滤器**：价格在同一中枢内触碰上下沿 ≥3 次时禁止趋势单，仅允许中枢对冲
- **增强资金费率过滤器**：双向禁止（>0.1% 禁多，<-0.1% 禁空），之前仅禁多
- **修改止损规则**：根据 market_state 动态调整（趋势=1.2×ATR，震荡=0.8×ATR）
- **修改止盈规则**：分两段止盈 TP1=1.5×ATR(平50%) + TP2=3.0×ATR(平剩余)
- 新增 **盈亏比过滤器**：(TP - Entry) / (Entry - SL) < 1.5 拒绝开仓

## Impact
- Affected specs: 无（新增能力）
- Affected code: `trading_system/strategies/mtf_fractal_strategy.py`
- **BREAKING**: 信号生成方法返回值结构变更（止盈字段从单值变为双值；新增 market_state 字段）；回测引擎需预计算 SMA60

## ADDED Requirements

### Requirement: 日线 MA60 趋势过滤器（Filter #1）
系统 SHALL 在每次开仓前检查日线收盘价与 MA60 的关系：
- IF Daily Close < MA60 → 只允许做空，禁止做多
- IF Daily Close > MA60 → 只允许做多，禁止做空

#### Scenario: 日线在 MA60 下方时阻止做多
- **WHEN** 日线收盘价 < MA60 且策略生成 OPEN_LONG 信号
- **THEN** 信号被拒绝，记录日志 "日线MA60过滤器: Close<MA60, 禁止做多"

#### Scenario: 日线在 MA60 上方时允许做多
- **WHEN** 日线收盘价 > MA60 且策略生成 OPEN_LONG 信号
- **THEN** 信号通过此过滤器

#### Scenario: 日线在 MA60 上方时阻止做空
- **WHEN** 日线收盘价 > MA60 且策略生成 OPEN_SHORT 信号
- **THEN** 信号被拒绝，记录日志 "日线MA60过滤器: Close>MA60, 禁止做空"

### Requirement: 4H 中枢震荡过滤器（Filter #2）
系统 SHALL 在开趋势单前检查 4H 中枢触碰次数：
- 统计当前 4H K线价格在过去 N 根K线内触碰当前活跃中枢上下沿的次数
- IF 触碰次数 ≥ 3 → 禁止所有趋势单（二买/类二买/三买），仅允许中枢双侧对冲（各20%仓位）

#### Scenario: 中枢震荡达3次时阻止二买
- **WHEN** 价格在4H中枢内触碰上下沿 ≥3 次 且 `_detect_type_2_buy` 触发
- **THEN** 信号被拒绝，记录日志 "中枢震荡过滤器: 触碰≥3次, 禁止趋势单"

#### Scenario: 中枢震荡时允许对冲
- **WHEN** 价格在4H中枢内触碰上下沿 ≥3 次 且 `_check_hedge_trigger` 触发
- **THEN** 对冲信号正常生成，仓位为正常的20%

### Requirement: 资金费率双向过滤器（Filter #3）
系统 SHALL 检查资金费率：
- IF Funding Rate > 0.1% → 禁止开多
- IF Funding Rate < -0.1% → 禁止开空

#### Scenario: 资金费率高时阻止做多
- **WHEN** Funding Rate > 0.001 (0.1%) 且生成 OPEN_LONG 信号
- **THEN** 信号被拒绝

#### Scenario: 资金费率低时阻止做空
- **WHEN** Funding Rate < -0.001 (-0.1%) 且生成 OPEN_SHORT 信号
- **THEN** 信号被拒绝

### Requirement: 动态止损规则（Filter #4）
系统 SHALL 根据 market_state 动态设置止损：
- market_state == "trend" → SL = entry_price ± 1.2 × ATR_4H
- market_state == "volatile" → SL = entry_price ± 0.8 × ATR_4H

#### Scenario: 趋势市做多止损
- **WHEN** market_state == "trend" 且开多
- **THEN** SL = entry_price - 1.2 × ATR_4H

#### Scenario: 震荡市做多止损
- **WHEN** market_state == "volatile" 且开多
- **THEN** SL = entry_price - 0.8 × ATR_4H

### Requirement: 分段止盈规则
系统 SHALL 使用两段止盈：
- TP1 = Entry ± 1.5 × ATR（平仓 50%）
- TP2 = Entry ± 3.0 × ATR（平仓剩余 50%）

#### Scenario: 做多分段止盈
- **WHEN** 开多且价格触及 TP1
- **THEN** 平掉50%仓位，剩余仓位止损移至开仓价

### Requirement: 盈亏比过滤器（Filter #5）
系统 SHALL 在开仓前计算盈亏比：
- IF (TP1 - Entry) / (Entry - SL) < 1.5 → 拒绝开仓

#### Scenario: 盈亏比不足时拒绝
- **WHEN** 做多信号 TP1=105, Entry=100, SL=97 → (105-100)/(100-97)=1.67 ≥ 1.5
- **THEN** 信号通过

#### Scenario: 盈亏比不足时拒绝
- **WHEN** 做多信号 TP1=103, Entry=100, SL=97 → (103-100)/(100-97)=1.0 < 1.5
- **THEN** 信号被拒绝，记录日志 "盈亏比过滤器: RRR=1.00<1.5, 拒绝开仓"

## MODIFIED Requirements

### Requirement: 信号返回结构
**修改**：所有 `OPEN_LONG`/`OPEN_SHORT` 信号返回值 SHALL 新增字段：
- `tp1`: float — 第一止盈位
- `tp2`: float — 第二止盈位
- `tp1_ratio`: float = 0.5 — TP1 平仓比例
- `market_state`: str — "trend" 或 "volatile"

### Requirement: 回测引擎预计算
**修改**：`_precompute_all_indicators` SHALL 新增预计算 `_precomputed_sma60`（日线 SMA60）

### Requirement: CryptoChan4HMasterStrategy
**修改**：`_apply_global_filters` 方法 SHALL 成为所有开仓信号的统一入口，强制调用所有5个过滤器

### Requirement: 出场信号（止盈）
**修改**：`_check_long_exit` / `_check_short_exit` SHALL 支持 TP1 部分平仓和 TP2 全部平仓