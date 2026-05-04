# 策略K线数据格式优化计划

## 一、现状分析

### 1. 现有K线接口
- `BinanceRestClient.get_continuous_klines()` - 永续合约K线
- `BinanceRestClient.get_spot_klines()` - 现货K线
- 两个接口都返回Binance API标准格式的K线数据

### 2. 现有策略
- `ChanStrategy` - 缠论策略
- 当前使用 `market_data.py` 中的 `get_klines()` 方法获取K线
- 返回的是pandas DataFrame格式，包含 `open_time, open, high, low, close, volume` 字段

### 3. 问题
- 策略使用的DataFrame格式与Binance API返回的嵌套列表格式不兼容
- 策略需要适配新的K线数据格式

## 二、优化目标

1. **统一K线数据格式**：策略使用Binance API标准格式
2. **保持策略逻辑不变**：仅修改数据格式处理部分
3. **提高兼容性**：支持从client直接获取K线数据

## 三、具体修改方案

### 1. 修改 `ChanStrategy` 类

**文件**: `trading_system/strategies/chan_strategy.py`

**修改点**:
- `_process_data()` 方法：支持处理Binance API格式的K线数据
- `initialize()` 方法：从client获取K线数据
- 添加数据格式转换方法：将Binance API格式转换为策略内部使用的格式

### 2. 新增辅助方法

**文件**: `trading_system/utils/indicators.py`

**新增方法**:
- `binance_klines_to_dataframe(klines)` - 将Binance API格式转换为DataFrame
- `dataframe_to_binance_klines(df)` - 将DataFrame转换为Binance API格式

### 3. 测试和验证

**文件**: `test_chan_strategy.py`

**测试点**:
- 策略初始化时直接从client获取K线
- 数据格式转换正确性
- 策略信号生成正常

## 四、实现步骤

1. **步骤一**: 新增数据格式转换工具方法
2. **步骤二**: 修改ChanStrategy类以支持Binance API格式
3. **步骤三**: 测试策略使用client获取K线
4. **步骤四**: 验证策略信号生成

## 五、预期结果

- 策略可以直接使用 `BinanceRestClient` 获取K线数据
- 保持原有策略逻辑不变
- 支持Binance API标准K线格式
- 提高系统的一致性和可维护性