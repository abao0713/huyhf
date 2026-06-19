# 修复 Live 模式运行错误任务

## 任务列表

### 1. 新增 get_account_balance() 方法
- [ ] 1.1 在 `client.py` 中新增 `get_account_balance()` 方法
- [ ] 1.2 调用 `futures_account_balance_v3` API 获取账户余额
- [ ] 1.3 返回包含 `availableBalance` 字段的字典
- [ ] 1.4 添加异常处理，失败时返回错误字典

### 2. 修改 Live 模式余额获取逻辑
- [ ] 2.1 在 `run_crypto_chan_live.py` 中修改余额获取逻辑
- [ ] 2.2 使用 `get_account_balance()` 替代 `get_account()` 获取余额
- [ ] 2.3 保持失败时使用默认值的逻辑

### 3. 添加缺失的限价单处理方法
- [ ] 3.1 在 `CryptoChan4HMasterStrategy` 类中添加 `_process_pending_limit_orders()` 方法
- [ ] 3.2 实现为空方法或添加 TODO 注释

### 4. 验证修复
- [ ] 4.1 运行 `client.py` 测试 `get_account_balance()` 方法
- [ ] 4.2 运行 `run_crypto_chan_live.py` 验证无报错
- [ ] 4.3 验证余额正确获取并显示

## 依赖关系
- 任务 2 依赖任务 1（余额方法必须先实现）
- 任务 3 独立于任务 1 和 2
- 任务 4 依赖任务 1、2、3 完成
