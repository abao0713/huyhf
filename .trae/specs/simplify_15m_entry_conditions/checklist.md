# Checklist

- [x] `_check_15m_first_buy()` 不再调用 `ChanTheoryFirstBuyAnalyzer.analyze()`，改为直接MACD底背驰检测
- [x] `_check_15m_first_sell()` 不再调用 `ChanTheoryFirstBuyAnalyzer.analyze_sell()`，改为直接MACD顶背驰检测
- [x] MACD(12,26,9) 计算正确，取最近100根K线定位两个显著低点/高点
- [x] 底背驰检测：价格低点降低 AND DIF值抬高 同时成立
- [x] 顶背驰检测：价格高点抬高 AND DIF值降低 同时成立
- [x] 低点/高点之间至少间隔5根K线（避免同一波动的重复检测）
- [x] `_generate_early_entry_signal()` 使用3条件独立判断模型：一买/二买/趋势向上
- [x] `_generate_early_short_entry_signal()` 使用3条件独立判断模型：一卖/二卖/趋势向下
- [x] 做多做空的信号生成逻辑完全镜像对称
- [x] `min_early_entry_conditions` 参数默认值为 2，在策略类和Executor类中定义
- [x] 置信度阈值参数 `early_entry_min_confidence` / `early_short_entry_min_confidence` 不再影响入场判断
- [x] `run_ethusdc_mtf_backtest.py` 支持 `--min-early-entry-conditions` 参数
- [x] Python语法检查通过
- [x] 回测运行无异常退出（exit code 0）
- [x] 回测有交易产生（交易数 > 0）: 9笔交易