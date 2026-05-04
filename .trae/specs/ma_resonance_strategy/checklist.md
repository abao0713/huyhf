# Checklist - 缠论与均线共振交易策略

## Phase 1: 基础设施验证

### Task 1: 均线计算基础设施 ✅
- [ ] 1.1 ChanStrategy.__init__() 包含均线配置参数
  - [ ] `ma_short_period = 20`
  - [ ] `ma_medium_period = 60`
  - [ ] `ma_long_period = 120`
  - [ ] 存储变量已声明 (`ma_short`, `ma_medium`, `ma_long`)

- [ ] 1.2 `_calculate_mavgs()` 方法实现正确
  - [ ] 调用 `calculate_ma()` 计算SMA（非EMA）
  - [ ] 处理数据不足情况（返回空Series或部分计算）
  - [ ] 结果存储到实例属性
  - [ ] 添加日志输出

- [ ] 1.3 集成到数据处理流程
  - [ ] 在 `_process_data()` 中调用 `_calculate_mavgs()`
  - [ ] 调用时机正确（MACD之后，分型之前）
  - [ ] 无异常抛出

**验证方法**: 
```python
strategy = ChanStrategy(symbol="ETHUSDT", time_frame="30m")
strategy._process_data()
assert len(strategy.ma_short) > 0
assert len(strategy.ma_short) == len(strategy.df_processed)
```

---

### Task 2: 支撑/压力识别算法 ✅
- [ ] 2.1 `_check_ma_support()` 方法
  - [ ] 输入参数完整 (price, ma_price, tolerance=0.005)
  - [ ] 强支撑判定: 偏差 < 0.25% → "strong"
  - [ ] 弱支撑判定: 0.25% ≤ 偏差 ≤ 0.5% → "weak"
  - [ ] 无支撑: 偏差 > 0.5% → None

- [ ] 2.2 `_check_ma_resistance()` 方法
  - [ ] 逻辑与 support 类似
  - [ ] 返回值类型一致

- [ ] 2.3 `_get_ma_signal()` 综合检测
  - [ ] 同时检查 MA20 和 MA60
  - [ ] 返回结构化字典包含所有信息
  - [ ] 字段完整:
    ```python
    {
      "has_support": bool,
      "support_level": str|None,
      "support_ma_type": str|None,
      "support_ma_price": float|None,
      "has_resistance": bool,
      "resistance_level": str|None,
      "resistance_ma_type": str|None,
      "resistance_ma_price": float|None
    }
    ```

**验证方法**:
```python
# 测试强支撑
result = strategy._check_ma_support(2250.0, 2248.0)
assert result == "strong"

# 测试无支撑
result = strategy._check_ma_support(2300.0, 2248.0)
assert result is None

# 测试综合信号
ma_signal = strategy._get_ma_signal(2250.0)
assert isinstance(ma_signal, dict)
assert "has_support" in ma_signal
```

---

## Phase 2: 共振引擎验证

### Task 3: 共振判定引擎 ✅
- [ ] 3.1 `_evaluate_buy_signal_resonance()` 实现
  - [ ] 获取日线趋势方向
  - [ ] 检查 MA20 支撑
  - [ ] 判定规则正确:
    ```
    strong支撑 + (up/neutral)趋势 → "strong"
    weak支撑 + 非down趋势 → "normal"
    any支撑 + down趋势 → "weak"
    无支撑 → "none"
    ```
  - [ ] 返回元组 `(level, reason)`
  - [ ] reason 字段包含完整诊断信息

- [ ] 3.2 `_evaluate_sell_signal_resonance()` 实现
  - [ ] 检查 MA60 压力（而非MA20支撑）
  - [ ] 规则与买入镜像对称:
    ```
    strong压力 + (down/neutral)趋势 → "strong"
    weak压力 + 非up趋势 → "normal"
    any压力 + up趋势 → "weak"
    无压力 → "none"
    ```

- [ ] 3.3 仓位配置常量定义
  - [ ] `RESONANCE_POSITION_SIZING` 字典存在
  - [ ] 包含4个级别: strong/normal/weak/none
  - [ ] 数值合理 (strong=1.0, normal=0.7, weak=0.4, none=0.7)

**验证方法**:
```python
# 场景1: 强共振买入
pen = create_test_pen(direction="down", low=2250)
level, reason = strategy._evaluate_buy_signal_resonance(pen)
assert level == "strong"
assert "强支撑" in reason

# 场景2: 弱共振买入（趋势矛盾）
# (模拟下降趋势环境)
level, reason = strategy._evaluate_buy_signal_resonance(pen)
assert level == "weak"
assert "下降趋势" in reason or "矛盾" in reason
```

---

### Task 4: generate_signal() 修改 ✅
- [ ] 4.1 信号格式增强
  - [ ] 新增字段: `resonance_level`, `position_size_ratio`, `ma_info`
  - [ ] 原有字段保留: `action`, `reason`, `stop_loss`, `position`
  - [ ] HOLD 信号格式不变

- [ ] 4.2 开关控制实现
  - [ ] `enable_resonance` 参数存在
  - [ ] 默认值为 True
  - [ ] 当 False 时，resonance_level="none", position_size_ratio=0.7

- [ ] 4.3 日志输出增强
  - [ ] 每次信号生成都有详细日志
  - [ ] 包含: 缠论基础信号、均线状态、共振级别、建议仓位
  - [ ] 日志级别为 INFO

**验证方法**:
```python
# 启用共振
signal = strategy.generate_signal()
assert "resonance_level" in signal
assert "position_size_ratio" in signal
assert "ma_info" in signal

# 禁用共振
strategy.enable_resonance = False
signal = strategy.generate_signal()
# 仍包含字段但值为默认值
assert signal["resonance_level"] == "none"

# HOLD信号不受影响
# (在无背驰时测试)
```

---

## Phase 3: 回测引擎适配验证

### Task 5: 仓位管理 ✅
- [ ] 5.1 `_execute_trade()` 修改
  - [ ] 读取 `signal.get("position_size_ratio", 0.7)`
  - [ ] 计算实际投入: `base_amount * size_ratio`
  - [ ] 日志显示调整前后对比

- [ ] 5.2 交易记录更新
  - [ ] TradeRecord 包含 position_size_ratio 字段
  - [ ] 可追溯每笔交易的共振级别

- [ ] 5.3 命令行参数支持
  - [ ] `--enable-resonance` 参数可解析
  - [ ] 正确传递给策略和引擎

**验证方法**:
```bash
# 运行回测并检查日志
python run_backtest.py --symbol ETHUSDT --interval 30m --enable-resonance true

# 检查输出:
# - strong信号: 投入$1000 (10% × 100%)
# - weak信号: 投入$400 (10% × 40%)
```

---

## Phase 4: 可视化验证

### Task 6: 图表增强 ✅
- [ ] 6.1 均线绘制
  - [ ] MA20 显示为蓝色实线
  - [ ] MA60 显示为橙色实线
  - [ ] MA120 显示为紫色实线
  - [ ] 透明度合适（不遮挡K线）

- [ ] 6.2 共振标注
  - [ ] 买卖信号旁有星级标记 (★/○/△)
  - [ ] 颜色区分:
    - green = strong
    - yellow = normal
    - red = weak
  - [ ] 图例包含说明

- [ ] 6.3 支撑/压力区域（可选）
  - [ ] 半透明带状区域
  - [ ] 文字标注

**验证方法**:
```python
# 生成图表
plotter.plot()
plotter.save("backtest_with_resonance.png")

# 目视检查:
# - 三条均线清晰可见
# - 信号标记有颜色和星级
# - 整体美观且信息丰富
```

---

## Phase 5: 全面测试验证

### Task 7: 测试与优化 ✅
- [ ] 7.1 单元测试全部通过
  - [ ] 均线计算测试
  - [ ] 支撑/压力识别测试
  - [ ] 共振判定测试
  - [ ] 边界条件测试

- [ ] 7.2 回测对比实验完成
  - [ ] 实验 A（原始策略）结果记录
  - [ ] 实验 B（共振策略）结果记录
  - [ ] 对比指标:
    - [ ] 总收益率
    - [ ] 最大回撤
    - [ ] 夏普比率
    - [ ] 交易次数
    - [ ] 胜率

- [ ] 7.3 参数敏感性分析
  - [ ] 至少测试3组不同均线周期
  - [ ] 至少测试2组容差参数
  - [ ] 找到最优配置

- [ ] 7.4 性能测试
  - [ ] 回测耗时增长 < 20%
  - [ ] 无内存泄漏
  - [ ] 并发安全（如适用）

**验收标准**:
```
✅ 所有单元测试通过 (覆盖率 >85%)
✅ 共振策略表现 ≥ 原始策略
✅ 默认参数合理且有文档说明
✅ 用户可通过命令行灵活配置
✅ 可视化直观易懂
✅ 向后兼容（禁用共振后行为一致）
```

---

## 文档完整性检查

### 代码注释 ✅
- [ ] 所有新增方法有 docstring
- [ ] 关键逻辑有行内注释
- [ ] 参数和返回值说明清晰
- [ ] 使用中文注释（符合项目规范）

### 配置说明 ✅
- [ ] README 或用户指南包含共振功能说明
- [ ] 提供示例命令
- [ ] 解释参数含义
- [ ] 说明风险和注意事项

### 变更日志 ✅
- [ ] 记录本次修改的内容
- [ ] 标注版本号
- - [ ] 列出 breaking changes（如有）

---

## 最终确认清单

### 功能完整性 ✅
- [ ] 均线计算模块正常工作
- [ ] 支撑/压力识别准确
- [ ] 共振判定逻辑合理
- [ ] 信号生成集成完成
- [ ] 仓位管理有效执行
- [ ] 可视化效果良好

### 质量标准 ✅
- [ ] 代码无严重Bug
- [ ] 测试覆盖充分
- [ ] 性能可接受
- [ ] 日志完整有用
- [ ] 文档齐全

### 业务价值 ✅
- [ ] 信号质量提升（或至少不降低）
- [ ] 提供更丰富的决策信息
- [ ] 灵活可配置
- [ ] 向后兼容
- [ ] 易于使用和理解

---

## 签署确认

**开发完成时间**: _______________  
**测试通过时间**: _______________  
**文档完成时间**: _______________  
**负责人**: _______________  

**备注**: 
_________________________________
