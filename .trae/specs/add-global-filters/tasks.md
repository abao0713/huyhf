# Tasks

- [x] Task 1: 回测引擎预计算 SMA60：在 `CryptoChan4HBacktestEngine._precompute_all_indicators` 中新增日线 SMA60 预计算，并将结果注入策略。
  - [x] 1.1 添加 `_precomputed_sma60` 属性
  - [x] 1.2 在 `_precompute_all_indicators` 中使用 `df_daily["close"].rolling(60).mean()` 计算 SMA60
  - [x] 1.3 在策略 `_calculate_all_indicators` 中添加读取预计算 SMA60 的逻辑

- [x] Task 2: 新增 market_state 判定方法：在 `CryptoChan4HMasterStrategy` 中添加 `_determine_market_state()` 方法，根据4H中枢震荡情况和ADX判定 "trend" / "volatile"。
  - [x] 2.1 实现 `_determine_market_state()` — 中枢震荡触碰≥3次判定为 volatile
  - [x] 2.2 实现 `_count_zhongshu_touches()` — 统计最近N根4H K线在中枢上下沿的触碰次数

- [x] Task 3: 重写 `_apply_global_filters` 为统一过滤器入口，集成5个过滤器。
  - [x] 3.1 实现 `_filter_daily_ma60(direction, price)` — 日线MA60趋势过滤器 (Filter #1)
  - [x] 3.2 实现 `_filter_zhongshu_oscillation(signal_type)` — 中枢震荡过滤器 (Filter #2)
  - [x] 3.3 增强 `_check_funding_rate_fuse` — 添加做空方向资金费率检查 (Filter #3)
  - [x] 3.4 实现 `_filter_risk_reward(entry, sl, tp1, direction)` — 盈亏比过滤器 (Filter #5)
  - [x] 3.5 统一入口方法 `_apply_global_filters(direction, price, signal_type, entry, sl, tp1)` 串联所有过滤器

- [x] Task 4: 修改所有信号生成方法，应用新止损止盈规则并通过全局过滤器。
  - [x] 4.1 修改 `_detect_type_2_buy()` — 动态止损(market_state)、分段止盈(tp1/tp2)、添加全局过滤器调用
  - [x] 4.2 修改 `_detect_type_2b_buy()` — 同上
  - [x] 4.3 修改 `_detect_type_2_sell()` — 同上
  - [x] 4.4 修改 `_eval_rule_001_002()` — 同上，并补齐 `_apply_global_filters` 调用
  - [x] 4.5 修改 `_check_hedge_trigger()` — 应用动态止损和分段止盈

- [x] Task 5: 修改出场逻辑支持 TP1 部分平仓和 TP2 全部平仓。
  - [x] 5.1 在 `HedgingState` 中添加 `long_tp2`、`short_tp2`、`long_tp1_hit`、`short_tp1_hit` 字段
  - [x] 5.2 修改 `_check_long_exit()` — 先检查 TP1 触发（平50%，移止损至开仓价），再检查 TP2 触发（全平）
  - [x] 5.3 修改 `_check_short_exit()` — 同上逻辑
  - [x] 5.4 修改 `apply_signal()` — 适配新的 tp1/tp2/market_state 字段

# Task Dependencies
- [Task 2] depends on [Task 1] (需要 SMA60 判定 market_state)
- [Task 3] depends on [Task 1, Task 2] (过滤器需要 SMA60 和 market_state)
- [Task 4] depends on [Task 2, Task 3] (信号生成需要过滤器和 market_state)
- [Task 5] depends on [Task 4] (出场逻辑依赖新的信号字段结构)