# 删除 WebSocket 和 REST API 接口计划

## 项目分析

通过对项目结构的分析，发现以下文件涉及 WebSocket 和 REST API 接口：

### WebSocket 相关文件：
- `trading_system/api/ws.py` - WebSocket 端点实现
- `trading_system/okx/websocket/` 目录 - OKX WebSocket 客户端
- `trading_system/api/main.py` - 包含 WebSocket 端点定义
- `trading_system/okx/api.py` - 包含 WebSocket 相关代码

### REST API 相关文件：
- `trading_system/api/routers.py` - REST API 路由定义
- `trading_system/okx/rest/` 目录 - OKX REST API 客户端
- `trading_system/api/main.py` - 包含 REST API 路由注册
- `trading_system/okx/api.py` - 包含 REST API 相关代码

### 其他相关文件：
- `trading_system/okx/` 目录 - OKX API 相关代码
- `trading_system/okx/config.py` - OKX 配置
- `trading_system/okx/utils/` 目录 - OKX 工具函数
- `main.py` - 主应用入口
- `test_websocket.py` - WebSocket 测试文件

## 实施计划

### 步骤 1：删除 WebSocket 相关文件
1. **删除 `trading_system/api/ws.py`** - 完整的 WebSocket 实现
2. **删除 `trading_system/okx/websocket/` 目录** - 包含 WebSocket 客户端代码
3. **修改 `trading_system/api/main.py`** - 删除 WebSocket 端点和相关导入

### 步骤 2：删除 REST API 相关文件
1. **删除 `trading_system/api/routers.py`** - REST API 路由定义
2. **删除 `trading_system/okx/rest/` 目录** - REST API 客户端代码
3. **修改 `trading_system/api/main.py`** - 删除 REST API 路由注册和相关导入

### 步骤 3：删除 OKX 相关文件
1. **删除 `trading_system/okx/` 目录** - 包含所有 OKX API 相关代码
2. **删除 `trading_system/okx/config.py`** - OKX 配置
3. **删除 `trading_system/okx/utils/` 目录** - OKX 工具函数

### 步骤 4：修改其他文件
1. **修改 `main.py`** - 简化主应用入口
2. **删除 `test_websocket.py`** - WebSocket 测试文件
3. **检查 `trading_system/strategies/` 目录** - 移除对 OKX API 的依赖

### 步骤 5：清理依赖
1. **修改 `requirements.txt`** - 移除不需要的依赖（如 websockets、aiohttp）
2. **清理 `__pycache__` 目录** - 移除编译后的文件

## 风险评估

### 潜在风险：
1. **策略依赖** - 量化交易策略可能依赖 OKX API
2. **数据库依赖** - 某些数据库操作可能依赖 API 相关代码
3. **配置依赖** - 配置文件可能包含 API 相关配置

### 风险缓解：
1. 检查策略代码，确保移除对 OKX API 的依赖
2. 保留数据库相关功能，只移除 API 相关代码
3. 清理配置文件中的 API 相关配置

## 预期结果

执行此计划后，项目将：
1. 不再包含任何 WebSocket 接口
2. 不再包含任何 REST API 接口
3. 不再依赖 OKX API
4. 保持数据库功能和策略功能
5. 代码结构更加简洁

## 验证步骤

1. 运行 `python -m uvicorn main:app` 确认应用启动无错误
2. 运行 `python test_strategy.py` 确认策略测试通过
3. 检查数据库连接是否正常
4. 确认所有 API 相关文件已被删除