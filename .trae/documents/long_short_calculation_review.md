# 做多/做空计算 Review 计划

## 审查范围
文件：`trading_system/strategies/mtf_fractal_strategy.py`

## 已确认正确（无问题）

| 检查项 | 方法 | 结论 |
|--------|------|------|
| 做多 SL 计算 | `_detect_type_2_buy`, `_detect_type_2b_buy`, `_eval_rule_001_002` | `entry - ATR * 1.2`(trend) / `0.8`(volatile) 正确 |
| 做空 SL 计算 | `_detect_type_2_sell`, `_eval_rule_001_002` | `entry + ATR * 1.2`(trend) / `0.8`(volatile) 正确 |
| 做多 TP1/TP2 | 所有做多方法 | `entry + ATR * 1.5/3.0` 正确 |
| 做空 TP1/TP2 | 所有做空方法 | `entry - ATR * 1.5/3.0` 正确 |
| 盈亏比计算 | `_filter_risk_reward` | `abs(tp1 - entry) / abs(entry - sl)` 使用 abs 正确处理双向 |
| 仓位计算 | `_calculate_position_size` | `(capital * risk_pct) / abs(entry - sl)` 使用 abs 正确 |
| 资金费率双向 | `_check_funding_rate_fuse` | `>0.001` 禁多, `< -0.001` 禁空 正确 |
| TP1 部分平仓 | `_check_long_exit`, `_check_short_exit` | `current_price >= tp1` 做多 / `<= tp1` 做空 正确 |
| TP2 全部平仓 | `_check_long_exit`, `_check_short_exit` | `current_price >= tp2` 做多 / `<= tp2` 做空 正确 |
| TP1 后移止损 | `_check_long_exit:1496`, `_check_short_exit:1525` | 移至开仓价 正确 |
| `apply_signal` PnL | `CLOSE_LONG`, `CLOSE_SHORT` | `(price - entry) * qty` 做多 / `(entry - price) * qty` 做空 正确 |
| 部分平仓 PnL | `CLOSE_LONG_PARTIAL`, `CLOSE_SHORT_PARTIAL` | 同上，使用 close_qty 正确 |
| 状态重置 | `CLOSE_LONG`, `CLOSE_SHORT` | 重置 tp1, tp1_hit 等字段 正确 |

## 发现的问题

### 问题 1（中）：对冲信号绕过全局过滤器

**文件**: `mtf_fractal_strategy.py`  
**方法**: `_check_hedge_trigger` (约 line 1518)  
**现象**: 对冲信号（`OPEN_SHORT_HEDGE` / `OPEN_LONG_HEDGE`）直接返回信号字典，不经过 `_apply_global_filters()`。  
**影响**: 对冲单不受日线 MA60 过滤器、资金费率过滤器、盈亏比过滤器的约束。  
**修复建议**: 在 `_check_hedge_trigger` 返回信号前调用 `_apply_global_filters`。

### 问题 2（低）：_eval_rule_003 返回 REJECT_ENTRY 过于激进

**文件**: `mtf_fractal_strategy.py`  
**方法**: `_eval_rule_003` 和 `_generate_signal_v2` (约 line 1449)  
**现象**: 当资金费率触发熔断时，`_eval_rule_003` 返回 `REJECT_ENTRY`，`_generate_signal_v2` 收到后直接 `return None`，阻止了后续所有 `type_2_buy`、`type_2b_buy`、`type_2_sell` 信号的生成。  
**但注意**: `_apply_global_filters` 中的 `_check_funding_rate_fuse` 已经是第二道防线，所以这不一定是 bug——只是拦截时机不同。  
**影响**: 低。`_apply_global_filters` 中的资金费率检查仍会生效。  
**修复建议**: 如果 `_apply_global_filters` 已覆盖，可考虑移除 `_eval_rule_003` 的 `REJECT_ENTRY` 逻辑（或保留作为双重保险）。

### 问题 3（低）：_filter_daily_ma60 的 price 参数冗余

**文件**: `mtf_fractal_strategy.py`  
**方法**: `_filter_daily_ma60` (line 1361-1377)  
**现象**: 参数 `price` 被设为 `daily_close` 的默认值，但实际使用 `df_daily.iloc[-1]["close"]` 覆盖。参数 `price` 在 `df_daily` 存在时未被使用。  
**影响**: 无运行时影响，但签名误导。  
**修复建议**: 移除 `price` 参数，直接从 `df_daily` 读取。

## 建议修复顺序

1. **修复问题 1**（对冲绕过全局过滤器）— 影响最大
2. **修复问题 3**（参数冗余）— 代码清理
3. **问题 2**（REJECT_ENTRY）— 低优先级，可选

## 验证方法

修复后运行：`python run_crypto_chan_backtest.py --fast --no-plot`
确认：无运行时错误，交易信号正常通过/被过滤，日志输出符合预期。