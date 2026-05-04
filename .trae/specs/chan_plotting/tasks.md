# 缠论划线图生成 - 实现计划

## [ ] Task 1: 创建绘图工具类 ChanPlotter
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - 创建新文件 `trading_system/utils/chan_plotter.py`
  - 实现ChanPlotter类，封装绘图逻辑
  - 支持初始化时传入K线数据和缠论分析结果
- **Acceptance Criteria Addressed**: AC-1, AC-6
- **Test Requirements**:
  - `programmatic` TR-1.1: 成功创建ChanPlotter类
  - `programmatic` TR-1.2: 图表能成功保存为PNG文件
- **Notes**: 使用matplotlib库

## [ ] Task 2: 实现K线图绘制功能
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 实现 `_plot_kline()` 方法绘制K线
  - 支持红绿K线（涨红跌绿）
  - 添加坐标轴标签和标题
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `human-judgment` TR-2.1: K线图清晰可读
  - `human-judgment` TR-2.2: 颜色正确（涨红跌绿）
- **Notes**: 使用matplotlib的bar绘制K线实体，vlines绘制影线

## [ ] Task 3: 实现分型标记功能
- **Priority**: P0
- **Depends On**: Task 2
- **Description**:
  - 实现 `_plot_fractals()` 方法
  - 顶分型用红色三角形向下标记
  - 底分型用绿色三角形向上标记
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `human-judgment` TR-3.1: 顶分型标记正确（红色向下三角）
  - `human-judgment` TR-3.2: 底分型标记正确（绿色向上三角）
- **Notes**: 使用scatter绘制标记

## [ ] Task 4: 实现笔绘制功能
- **Priority**: P0
- **Depends On**: Task 3
- **Description**:
  - 实现 `_plot_pens()` 方法
  - 上升笔用绿色线段连接
  - 下降笔用红色线段连接
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `human-judgment` TR-4.1: 上升笔绘制正确（绿色）
  - `human-judgment` TR-4.2: 下降笔绘制正确（红色）
- **Notes**: 使用plot绘制线段

## [ ] Task 5: 实现线段绘制功能
- **Priority**: P1
- **Depends On**: Task 4
- **Description**:
  - 实现 `_plot_segments()` 方法
  - 线段用较粗的线绘制，与笔区分
  - 上升线段用蓝色，下降线段用橙色
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `human-judgment` TR-5.1: 线段比笔更粗
  - `human-judgment` TR-5.2: 线段颜色与笔区分明显
- **Notes**: 设置linewidth参数区分粗细

## [ ] Task 6: 实现背驰信号标记功能
- **Priority**: P1
- **Depends On**: Task 5
- **Description**:
  - 实现 `_plot_signals()` 方法
  - 底背驰（买入信号）用绿色箭头向上标记
  - 顶背驰（卖出信号）用红色箭头向下标记
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `human-judgment` TR-6.1: 买入信号标记正确（绿色上箭头）
  - `human-judgment` TR-6.2: 卖出信号标记正确（红色下箭头）
- **Notes**: 在信号位置添加箭头注释

## [ ] Task 7: 整合到回测引擎
- **Priority**: P1
- **Depends On**: Task 6
- **Description**:
  - 修改BacktestEngine类，在回测完成后调用绘图功能
  - 添加参数控制是否生成图表
  - 图表文件保存在指定目录
- **Acceptance Criteria Addressed**: AC-1, AC-6
- **Test Requirements**:
  - `programmatic` TR-7.1: 回测完成后自动生成图表
  - `programmatic` TR-7.2: 图表文件保存在正确位置
- **Notes**: 需要导入ChanPlotter类

## [x] Task 8: 测试和验证
- **Priority**: P2
- **Depends On**: Task 7
- **Description**:
  - 运行回测并验证图表生成
  - 检查所有缠论元素是否正确显示
- **Acceptance Criteria Addressed**: 所有AC
- **Test Requirements**:
  - `human-judgment` TR-8.1: 图表包含所有缠论元素
  - `human-judgment` TR-8.2: 图表清晰可读
- **Notes**: 手动检查生成的图表