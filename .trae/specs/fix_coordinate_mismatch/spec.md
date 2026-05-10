# 修复分型索引与K线索引坐标系不匹配 Spec

## Why
`_merge_inclusion()` 在处理K线包含关系时会**缩减数据行数**（1000行→~600行），导致分型的`idx`在**处理后坐标系**（0~599）中。而回测引擎主循环迭代的是**原始坐标系**（0~999），将`bar_idx=i`传给`generate_signal(bar_idx=i)`时，两个坐标系不一致。当引擎循环的原始索引遍历到~500-600以上时，所有分型已在处理坐标空间中被消耗完毕，剩余K线全部返回HOLD。

## 根因调用链

```
用户数据: 1000行 30m K线 (index 0-999)
    ↓
ChanStrategy._process_data():
    df_processed = df_30m.copy()      # 1000行
    df_processed = _merge_inclusion()  # → ~600行（缩编！）
    fractals = _find_fractals()        # idx范围: 0~599
    ↓
V2._sync_internal_data():
    self.fractals ← fractals           # idx在0~599（处理后空间）
    ↓
Engine主循环 (原始数据, index 0-999):
    generate_signal(bar_idx=i)         # i是原始坐标 (0-999)
    → 匹配 fractal.idx == i           # 但fractal.idx在处理后空间 (0-599)
    → 坐标系不匹配！
```

## What Changes
- **ChanStrategy** 新增 `use_inclusion_merge` 参数（默认True保持V1兼容）
- **V2策略** 在 `load_data_for_backtest` 中将内部策略的 `use_inclusion_merge` 设为 `False`
- 跳过包含关系处理后，`df_processed` 与 `df_30m` 行数一致，分型索引与原始K线索引对齐

## Impact
- Affected specs: `fix_signal_cessation`
- Affected code: `chan_strategy.py` (_process_data), `chan_strategy_v2.py` (load_data_for_backtest)

## MODIFIED Requirements

### Requirement: V2分型索引与K线索引对齐
V2策略的 `generate_signal(bar_idx)` SHALL 使用与回测引擎主循环相同的坐标系（原始K线索引），确保分型能正确匹配到对应的K线位置。

#### Scenario: 完整K线覆盖
- **GIVEN** 回测有1000根原始30m K线
- **WHEN** 初始化完成并运行回测
- **THEN** 分型索引与K线索引一致，信号分布覆盖全部1000根K线范围

#### Scenario: V1向后兼容
- **GIVEN** V1策略使用默认参数
- **WHEN** V1策略处理数据
- **THEN** 包含关系处理正常工作（use_inclusion_merge=True）