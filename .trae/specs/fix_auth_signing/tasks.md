# Tasks

- [x] Task 1: `_request()` 签名时自动追加 `recvWindow`
  - [x] 在 `params["timestamp"]` 之后、`params["signature"]` 之前，添加 `params["recvWindow"] = recvWindow`（默认 5000）
  - [x] `recvWindow` 作为 `_request()` 的可选参数，默认值 5000

- [x] Task 2: 移除 `get_account()` 冗余签名逻辑
  - [x] 删除手动 `timestamp` 赋值和 `sign_request` 调用
  - [x] 改为调用 `_request("GET", path, signed=True)`，由 `_request()` 统一处理
  - [x] 确认 `get_account` 接口使用 `/account` 路径

- [x] Task 3: 移除 `get_positions()` 冗余签名逻辑
  - [x] 删除手动 `timestamp` 赋值和 `sign_request` 调用
  - [x] 改为将 `symbol` 参数传递给 `_request()`，由 `_request()` 统一处理签名

- [x] Task 4: 语法检查验证
  - [x] `python -m py_compile` 通过

# Task Dependencies
- Task 2 and Task 3 depend on Task 1