# Checklist

- [x] `inject_data()` 中将 `_chan.df_processed` 传播到 `self.df_processed`
- [x] `_process_data()` 中通过 `inject_data()` 自动传播 `df_processed`
- [x] 回测无Python异常
- [x] 生成的 `backtest_plot.png` K线数与分型索引一致