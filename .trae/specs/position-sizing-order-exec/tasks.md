# 仓位管理与订单执行优化 - 实施计划

## [x] Task 1: 新增仓位管理配置模型
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 在 `SizingConfig` 或其附近新增 `PositionSizingConfig` 配置 dataclass，包含以下字段：
    - `capital_usage_ratio: float = 0.6`（60% 资金用于策略）
    - `first_entry_pct: float = 0.4`（首次开仓 = 40%）
    - `add_entry_pcts: List[float]` = `[0.25, 0.18, 0.10]`（3 次加仓比例）
    - `max_add_count: int = 3`
  - 更新 `PositionManagementConfig` 引用新配置
  - 更新 `from_dict` 方法支持 JSON 反序列化
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3
- **Test Requirements**:
  - `programmatic` TR-1.1: `PositionSizingConfig` 可被正确实例化，默认值验证通过
  - `programmatic` TR-1.2: `from_dict` 可正确反序列化 JSON 配置
  - `programmatic` TR-1.3: `PositionManagementConfig` 包含 `position_sizing` 字段
- **Notes**: 创建新的 dataclass 而非修改现有 `SizingConfig`，保持向后兼容

## [x] Task 2: 实现新的仓位计算逻辑 `_calculate_position_size_v2`
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 新增 `_calculate_position_size_v2(entry_price, is_add=False)` 方法
  - 计算策略可操作资金：`total_capital * capital_usage_ratio`
  - 计算可用资金：`operable_capital - current_position_value`（当前持仓市值）
  - 首次开仓：`available_funds * first_entry_pct`
  - 加仓：`available_funds * add_entry_pcts[add_count]`
  - 返回 `quantity = allocation_amount / entry_price`
  - 新增 `_add_count` 状态变量跟踪当前加仓次数
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-7
- **Test Requirements**:
  - `programmatic` TR-2.1: 总资金 $10,000，首次开仓金额 = $2,400（$10,000 × 0.6 × 0.4）
  - `programmatic` TR-2.2: 第 1 次加仓金额 = $(6000-2400) × 0.25 = $900
  - `programmatic` TR-2.3: 第 2 次加仓金额 = $(6000-2400-900) × 0.18 = $486
  - `programmatic` TR-2.4: 第 3 次加仓金额 = $(6000-2400-900-486) × 0.10 = $221.40
  - `programmatic` TR-2.5: 超过 3 次加仓返回 0 或 None
  - `programmatic` TR-2.6: 平仓后 `_add_count` 重置为 0

## [x] Task 3: 实现方向切换时的自动平仓逻辑
- **Priority**: P0
- **Depends On**: Task 2
- **Description**:
  - 修改 `apply_signal` 方法中的 `OPEN_LONG` 分支：
    - 若 `hedging.short_qty > 0`，先执行 `CLOSE_SHORT`
    - 平仓完成后再执行 `OPEN_LONG`
  - 修改 `OPEN_SHORT` 分支：
    - 若 `hedging.long_qty > 0`，先执行 `CLOSE_LONG`
    - 平仓完成后再执行 `OPEN_SHORT`
  - 方向切换时，加仓计数器重置为 0
  - 平仓产生的 PnL 更新 `current_capital`
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` TR-3.1: 持有空仓时收到 OPEN_LONG，交易记录先出现 CLOSE_SHORT 再出现 OPEN_LONG
  - `programmatic` TR-3.2: 持有多仓时收到 OPEN_SHORT，交易记录先出现 CLOSE_LONG 再出现 OPEN_SHORT
  - `programmatic` TR-3.3: 方向切换后 `_add_count` 重置为 0
  - `programmatic` TR-3.4: 同方向已有仓位时，按加仓逻辑处理（而非跳过）

## [x] Task 4: 实现限价单成交逻辑
- **Priority**: P1
- **Depends On**: Task 3
- **Description**:
  - 新增 `_execute_limit_order(price, quantity, side, bar_data)` 方法
  - 回测模式：限价单在 bar 开盘价 ≤ 限价 ≤ bar 最高价（做多）或 bar 最低价 ≤ 限价 ≤ bar 开盘价（做空）时成交
  - 成交价：若限价在 bar 范围内，以限价成交；否则以触发价成交
  - 新增 `_pending_limit_orders` 列表存储未成交的限价单
  - 修改 `TradeRecordV2` 新增 `order_type: str` 和 `limit_price: float` 字段
  - 修改 `apply_signal` 中开仓部分，调用 `_execute_limit_order` 而非直接记录
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `programmatic` TR-4.1: 限价 $3,000，bar 的 high=$3,100, low=$2,900，成交价为 $3,000
  - `programmatic` TR-4.2: 限价 $3,000, bar 的 high=$2,950, low=$2,900，做多限价单未成交，加入 pending 列表
  - `programmatic` TR-4.3: 未成交限价单在后续 bar 条件满足时成交
  - `programmatic` TR-4.4: TradeRecord 中 `order_type="limit"` 和 `limit_price` 正确记录

## [x] Task 5: 更新信号生成和回测引擎集成
- **Priority**: P1
- **Depends On**: Task 4
- **Description**:
  - 更新 `generate_signal` 中所有调用 `_calculate_position_size` 的地方改为 `_calculate_position_size_v2`
  - 更新 `CryptoChan4HBacktestEngine.run` 中处理 pending 限价单的逻辑
  - 更新 `apply_signal` 中 `CLOSE_SHORT_AND_OPEN_LONG` 的处理（已由 Task 3 自动处理，可简化）
  - 更新 `run_crypto_chan_backtest` 中 JSON 配置模板，包含新的 `position_sizing` 配置
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7
- **Test Requirements**:
  - `programmatic` TR-5.1: 完整回测运行，exit code 0
  - `programmatic` TR-5.2: 回测报告中的交易记录包含正确的 `order_type` 和 `limit_price` 字段
  - `programmatic` TR-5.3: 回测结果中无方向冲突持仓（不会同时持有 long 和 short 主仓位）

## [x] Task 6: 回归测试与验证
- **Priority**: P1
- **Depends On**: Task 5
- **Description**:
  - 运行完整回测验证所有 AC 通过
  - 检查日志输出确认加仓次数限制、方向切换等逻辑正确
  - 验证生成的 JSON 报告格式正确
- **Acceptance Criteria Addressed**: All AC
- **Test Requirements**:
  - `programmatic` TR-6.1: 回测正常完成，无 crash 或异常
  - `programmatic` TR-6.2: 所有验证检查点通过

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 5