# Tasks

- [x] Task 1: 入场函数改为限价单
  - [x] `_open_long_probe`: `order_type="MARKET"` → `"LIMIT"`，传入 `price=price`
  - [x] `_open_short_probe`: `order_type="MARKET"` → `"LIMIT"`，传入 `price=price`
  - [x] `_open_early_entry`: `order_type="MARKET"` → `"LIMIT"`，传入 `price=price`
  - [x] `_open_early_short_entry`: `order_type="MARKET"` → `"LIMIT"`，传入 `price=price`

- [x] Task 2: 加仓函数改为限价单
  - [x] `_add_long_confirm`: `order_type="MARKET"` → `"LIMIT"`，传入 `price=price`
  - [x] `_add_short_confirm`: `order_type="MARKET"` → `"LIMIT"`，传入 `price=price`

- [x] Task 3: 语法检查验证
  - [x] `python -m py_compile` 通过

# Task Dependencies
- Task 1 and Task 2 are independent (can be done in parallel)
- Task 3 depends on Task 1 and Task 2