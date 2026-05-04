# 缠论划线图生成功能 - 产品需求文档

## Overview
- **Summary**: 在回测过程中生成缠论划线图，可视化展示分型、笔、线段、背驰等缠论元素，帮助用户直观理解策略决策过程
- **Purpose**: 通过可视化图表展示缠论中间数据，让用户能够看到策略是如何识别分型、构建笔和线段、判断背驰的
- **Target Users**: 策略开发者、量化交易员、需要调试和优化缠论策略的工程师

## Goals
- 在回测过程中生成缠论划线图
- 可视化展示分型（顶分型/底分型）
- 可视化展示笔（上升笔/下降笔）
- 可视化展示线段
- 标记背驰信号位置
- 支持将图表保存为图片文件

## Non-Goals (Out of Scope)
- 实时绘图（本需求仅针对回测后生成静态图表）
- 交互式图表功能（如缩放、平移）
- 实盘实时显示

## Background & Context
- 当前缠论策略在回测时只能看到最终结果，无法直观看到中间数据
- 用户需要看到分型、笔、线段是如何被识别和构建的
- 需要使用matplotlib作为绘图库

## Functional Requirements
- **FR-1**: 生成K线图并叠加缠论元素
- **FR-2**: 在图上标记顶分型和底分型
- **FR-3**: 在图上绘制笔的起点和终点连线
- **FR-4**: 在图上绘制线段
- **FR-5**: 标记背驰信号位置（底背驰/BUY、顶背驰/SELL）
- **FR-6**: 将图表保存为PNG格式图片

## Non-Functional Requirements
- **NFR-1**: 图表生成时间应在10秒内完成
- **NFR-2**: 图表应清晰可读，元素不重叠
- **NFR-3**: 支持中文显示

## Constraints
- **Technical**: 使用matplotlib库进行绘图，需要确保已安装
- **Dependencies**: 需要ChanStrategy类提供分型、笔、线段数据

## Assumptions
- 回测数据已加载到ChanStrategy中
- matplotlib库已安装在环境中

## Acceptance Criteria

### AC-1: 生成包含K线的基础图表
- **Given**: 回测数据已加载
- **When**: 调用绘图函数
- **Then**: 生成包含K线的基础图表
- **Verification**: `programmatic`

### AC-2: 标记分型
- **Given**: 策略已识别出分型
- **When**: 调用绘图函数
- **Then**: 在K线上用不同颜色标记顶分型（红色）和底分型（绿色）
- **Verification**: `human-judgment`

### AC-3: 绘制笔
- **Given**: 策略已构建笔
- **When**: 调用绘图函数
- **Then**: 在图上用线段连接笔的起点和终点
- **Verification**: `human-judgment`

### AC-4: 绘制线段
- **Given**: 策略已构建线段
- **When**: 调用绘图函数
- **Then**: 在图上用粗线段绘制线段
- **Verification**: `human-judgment`

### AC-5: 标记背驰信号
- **Given**: 策略已识别出背驰
- **When**: 调用绘图函数
- **Then**: 在背驰位置标记买入/卖出信号
- **Verification**: `human-judgment`

### AC-6: 保存图表
- **Given**: 图表已生成
- **When**: 调用保存函数
- **Then**: 将图表保存为PNG文件
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要支持不同的时间周期显示？
- [ ] 是否需要在图表中显示MACD指标？