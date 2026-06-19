# Checklist

## 账户余额查询验证
- [ ] `get_account_balance()` 方法已实现
- [ ] 方法调用 `futures_account_balance_v3` API
- [ ] 返回值包含 `availableBalance` 字段
- [ ] 异常处理完善，失败时返回错误字典

## Live 模式余额获取验证
- [ ] `run_crypto_chan_live.py` 使用 `get_account_balance()` 获取余额
- [ ] 成功时显示实际账户余额
- [ ] 失败时使用默认值 $10,000.00
- [ ] 日志输出正确

## 限价单处理方法验证
- [ ] `CryptoChan4HMasterStrategy` 类包含 `_process_pending_limit_orders()` 方法
- [ ] 方法调用不抛出 `AttributeError`

## 集成测试验证
- [ ] 运行 `run_crypto_chan_live.py` 无报错
- [ ] 余额正确获取并显示
- [ ] 限价单处理方法正常调用
