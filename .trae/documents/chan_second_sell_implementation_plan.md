# 缠论第二类卖点（二卖）实现计划

## 当前状态

核心分析逻辑（`ChanTheoryFirstBuyAnalyzer` 类中的方法）已全部实现：
- `SecondSellAnalysisResult` dataclass ✅
- `analyze_second_sell()` 主分析方法 ✅
- `_ss_find_first_sell_point()` 一卖定位 ✅
- `_ss_check_fall_bounce_structure()` 下跌+反弹结构检测 ✅
- `_ss_classify_strength()` 强度分级 ✅
- `_ss_check_lower_tf_divergence()` 30M小级别背驰验证 ✅
- `_ss_auxiliary_verification()` 辅助验证 ✅
- `_ss_trading_decision()` 交易决策 ✅
- `generate_second_sell_report()` 报告生成 ✅

但存在 **5处缺口** 导致二卖功能实际不可用：

---

## 待完成任务

### 步骤 1：修复 `generate_second_sell_report` 中的字符串转义问题

**文件**: `trading_system/strategies/chan_first_buy_strategy.py`

**问题**: 与二买阶段相同的 `\n` 转义 bug —— `'\n'.join(lines)` 被拆分为两行。

**受影响位置**（共4处）：
| 行号 | 当前状态 | 修复后 |
|------|----------|--------|
| 1891-1892 | `return '\n'.join(lines)` 拆行 | `return '\n'.join(lines)` 单行 |
| 1901-1902 | 同上 | 同上 |
| 1917-1918 | 同上 | 同上 |
| 1947-1948 | 同上 | 同上 |

**修复方式**: 每次使用 SearchReplace 将拆行版本替换为单行版本。

---

### 步骤 2：扩展 `ChanFirstBuyStrategy` 类 — 添加 `run_second_sell_analysis` 方法

**文件**: `trading_system/strategies/chan_first_buy_strategy.py`

参照二买的 `run_second_buy_analysis`（L2067-L2071），在 `get_second_buy_signal` 方法之后插入：

```python
def run_second_sell_analysis(self) -> SecondSellAnalysisResult:
    if self.latest_sell_result is None or not self.latest_sell_result.divergence_confirmed:
        self.run_sell_analysis()
    result = self.analyzer.analyze_second_sell(self.df_4h, self.df_30m, self.latest_sell_result)
    return result
```

关键差异：二卖依赖 `latest_sell_result`（而非 `latest_result`），需在分析前确保一卖已运行。

---

### 步骤 3：扩展 `ChanFirstBuyStrategy` 类 — 添加 `get_second_sell_signal` 方法

**文件**: `trading_system/strategies/chan_first_buy_strategy.py`

参照二买的 `get_second_buy_signal`（L2073-L2083），插入：

```python
def get_second_sell_signal(self) -> Optional[Dict[str, Any]]:
    result = self.run_second_sell_analysis()
    if not result.second_sell_confirmed:
        return {'action': 'HOLD', 'reason': '二卖条件不满足'}
    return {
        'action': 'SELL',
        'entry_price': result.suggested_entry,
        'stop_loss': result.stop_loss,
        'targets': result.targets,
        'position_advice': result.position_advice,
    }
```

---

### 步骤 4：添加模块级 `run_second_sell_analysis` async 便捷函数

**文件**: `trading_system/strategies/chan_first_buy_strategy.py`

参照二买的 `run_second_buy_analysis`（L2126-L2143），在文件末尾 `if __name__ == '__main__'` 之前插入：

```python
async def run_second_sell_analysis(symbol: str = 'ETHUSDC') -> SecondSellAnalysisResult:
    strategy = ChanFirstBuyStrategy(symbol=symbol)
    await strategy.initialize(symbol)
    await strategy.fetch_data()

    if strategy.df_4h.empty:
        logger.error(f'无法获取{symbol}的{strategy.time_frame}数据')
        return SecondSellAnalysisResult(
            first_sell_confirmed=False, first_sell_high=0.0, first_sell_idx=-1,
            has_fall_bounce=False,
            details=['数据获取失败'],
        )

    strategy.run_sell_analysis()
    result = strategy.run_second_sell_analysis()
    report = strategy.analyzer.generate_second_sell_report(result)
    print(report)
    return result
```

---

### 步骤 5：更新 `__init__.py` 导出

**文件**: `trading_system/strategies/__init__.py`

1. 在 import 语句中添加 `SecondSellAnalysisResult` 和 `run_second_sell_analysis`
2. 在 `__all__` 列表中添加 `"SecondSellAnalysisResult"` 和 `"run_second_sell_analysis"`

---

### 步骤 6：更新 `run_first_buy_analysis.py` CLI 入口

**文件**: `run_first_buy_analysis.py`

1. 在 `--direction` 的 `choices` 中添加 `'second-sell'`
2. 在帮助文字中添加 `second-sell=二卖`
3. 添加 `second-sell` 方向的处理分支：

```python
elif args.direction == 'second-sell':
    strategy.run_sell_analysis()
    result = strategy.run_second_sell_analysis()
    report = strategy.analyzer.generate_second_sell_report(result)
    print(report)
    signal = strategy.get_second_sell_signal()
```

4. 更新文件头部的用法说明注释

---

### 步骤 7：验证测试

1. **导入验证**: 执行 `python -c "from trading_system.strategies.chan_first_buy_strategy import SecondSellAnalysisResult, run_second_sell_analysis"` 确保无 ImportError
2. **类型验证**: 执行 `python -c "from trading_system.strategies import SecondSellAnalysisResult; print('OK')"` 确保模块导出正确
3. **CLI验证**: 执行 `python run_first_buy_analysis.py --help` 确认 `second-sell` 出现在选项中
4. 清理临时文件 `_insert_ss.py`

---

## 执行顺序

```
步骤1（字符串修复）→ 步骤2（run_second_sell_analysis）→ 步骤3（get_second_sell_signal）
    → 步骤4（顶层 async 函数）→ 步骤5（__init__.py）→ 步骤6（CLI入口）→ 步骤7（验证）
```

步骤2-4 都在同一文件中，可以合并执行以提高效率。