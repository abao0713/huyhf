# 仓位管理与订单执行优化 - 产品需求文档

## Overview
- **Summary**: 重构策略的仓位计算逻辑、加仓机制、方向切换处理以及订单执行方式，从 ATR 动态仓位改为固定比例阶梯仓位，开仓时使用限价单并记录实际成交价。
- **Purpose**: 提升资金利用率，控制风险暴露，支持多次加仓，确保方向切换时先平仓再开仓，订单执行更加贴近真实交易环境。
- **Target Users**: 策略回测用户、实盘模拟盘用户

## Goals
- 将策略可操作资金限制为总资金的 60%
- 首次开仓使用可用资金的 40%，支持最多 3 次加仓（25%/18%/10%）
- 方向切换时自动先平仓对立方向仓位，再开新仓位
- 开仓时使用限价单，记录服务器实际成交价

## Non-Goals (Out of Scope)
- 不修改止损/止盈逻辑
- 不修改缠论信号生成逻辑
- 不修改对冲套利逻辑
- 不新增交易品种或时间周期
- 不涉及实盘交易所 API 对接（限价单实际成交价通过回测引擎模拟亦可）

## Background & Context
- 当前 `_calculate_position_size` 使用 ATR 动态计算仓位，公式为 `(Account_Equity * 1%) / (entry_price - stop_loss)`，风险敞口不可控
- 当前 `apply_signal` 中的 `OPEN_LONG`/`OPEN_SHORT` 不会检查是否存在对立仓位，仅检查同方向仓位是否已存在
- 当前开仓直接使用 `signal["price"]`（通常为当前 bar 收盘价）作为成交价，等同于市价单
- 策略配置文件 `SizingConfig` 中 `risk_per_trade_percent = 1.0` 仅表示风险比例，并非投入资金比例

## Functional Requirements
- **FR-1**: 新增 `capital_usage_ratio` 配置项，默认 0.6（60%），策略可操作资金 = 总资金 × 60%
- **FR-2**: 首次开仓金额 = 可用资金 × 40%，可用资金 = 策略可操作资金 - 已占用保证金
- **FR-3**: 支持最多 3 次加仓，第 1 次加仓 = 可用资金 × 25%，第 2 次 = 可用资金 × 18%，第 3 次 = 可用资金 × 10%
- **FR-4**: 当信号为 OPEN_LONG，但当前持有空头仓位时，先执行平空，再执行开多
- **FR-5**: 当信号为 OPEN_SHORT，但当前持有空头仓位时，先执行平空，再执行开多
- **FR-6**: 开仓时下限价单（limit order），记录开仓价时使用模拟成交价（回测）或服务器实际成交价（实盘）
- **FR-7**: 平仓仍然使用市价单（按当前 bar 收盘价执行），以满足快速退出需求

## Non-Functional Requirements
- **NFR-1**: 仓位计算逻辑需在回测和实盘模式下均能正确运行
- **NFR-2**: 加仓次数限制需持久化记录，跨 bar 保持状态
- **NFR-3**: 方向切换（平仓+开仓）需在同一 bar 内完成，不产生跨 bar 延迟

## Constraints
- **Technical**: Python 3.x, 不引入新的第三方依赖
- **Dependencies**: 仅修改 `mtf_fractal_strategy.py` 中的策略类和相关配置类

## Assumptions
- 回测中限价单以当前 bar 的收盘价（或 open）作为成交价模拟
- 实盘模式下限价单将通过交易所 API 查询实际成交价
- 加仓次数计数器在平仓后重置为 0

## Acceptance Criteria

### AC-1: 资金分配比例生效
- **Given**: 总资金 $10,000，`capital_usage_ratio = 0.6`
- **When**: 策略初始化
- **Then**: 策略可操作资金 = $6,000，首次开仓使用 $2,400（$6,000 × 40%）
- **Verification**: `programmatic`

### AC-2: 加仓比例正确
- **Given**: 已开 1 次仓位，可用资金 = $6,000 - $2,400 = $3,600
- **When**: 第 2 次开仓（首次加仓）
- **Then**: 投入金额 = $3,600 × 25% = $900
- **Verification**: `programmatic`

### AC-3: 加仓次数限制
- **Given**: 已加仓 3 次（共 4 次开仓）
- **When**: 第 5 次开仓信号触发
- **Then**: 不执行开仓，记录日志 "已达最大加仓次数(3次)"
- **Verification**: `programmatic`

### AC-4: 做多时先平空仓
- **Given**: 当前持有空头仓位 0.5 ETH
- **When**: 收到 OPEN_LONG 信号
- **Then**: 先执行平空（CLOSE_SHORT），再执行开多（OPEN_LONG），交易记录中有连续两条记录
- **Verification**: `programmatic`

### AC-5: 做空时先平多仓
- **Given**: 当前持有空头仓位 0.5 ETH
- **When**: 收到 OPEN_SHORT 信号
- **Then**: 先执行平多（CLOSE_LONG），再执行开空（OPEN_SHORT），交易记录中有连续两条记录
- **Verification**: `programmatic`

### AC-6: 限价单记录
- **Given**: 策略发出限价单信号，限价 = $3,000
- **When**: 订单成交
- **Then**: TradeRecord 中记录的 price 为实际成交价（回测中等于限价或当前 bar 价格的合理模拟值）
- **Verification**: `programmatic`

### AC-7: 平仓后加仓计数器重置
- **Given**: 已加仓 2 次，持仓全部平仓
- **When**: 新开仓信号到来
- **Then**: 加仓计数器从 0 开始，首次开仓仍为可用资金 × 40%
- **Verification**: `programmatic`

## Open Questions
- [ ] 限价单在回测中如何模拟实际成交价？（当前假设：若限价 ≤ 当前 high 且 ≥ 当前 low，则成交价为限价；否则不成交）
- [ ] 方向切换平仓是否需要考虑对冲仓位（hedge）的平仓？