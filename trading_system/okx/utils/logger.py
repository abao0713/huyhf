import time
import logging
import asyncio
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def log_api_call(func: Callable) -> Callable:
    """
    API调用日志装饰器
    记录函数调用的详细信息，包括：
    - 请求开始时间
    - 函数参数
    - 处理时间
    - 返回结果
    - 错误信息（如果发生异常）
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        # 记录开始时间
        start_time = time.time()
        start_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))
        
        # 记录函数信息和参数
        func_name = func.__name__
        logger.info(f"[API CALL] {func_name} - Start at {start_time_str}")
        logger.debug(f"[API CALL] {func_name} - Parameters: args={args}, kwargs={kwargs}")
        
        try:
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 计算处理时间
            end_time = time.time()
            end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
            duration = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 记录成功结果
            logger.info(f"[API CALL] {func_name} - Success at {end_time_str}")
            logger.info(f"[API CALL] {func_name} - Duration: {duration:.2f}ms")
            logger.debug(f"[API CALL] {func_name} - Result: {result}")
            
            return result
        except Exception as e:
            # 计算处理时间
            end_time = time.time()
            end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
            duration = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 记录错误信息
            logger.error(f"[API CALL ERROR] {func_name} - Failed at {end_time_str}")
            logger.error(f"[API CALL ERROR] {func_name} - Duration: {duration:.2f}ms")
            logger.error(f"[API CALL ERROR] {func_name} - Error: {str(e)}", exc_info=True)
            
            # 重新抛出异常
            raise
    
    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        # 记录开始时间
        start_time = time.time()
        start_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))
        
        # 记录函数信息和参数
        func_name = func.__name__
        logger.info(f"[API CALL] {func_name} - Start at {start_time_str}")
        logger.debug(f"[API CALL] {func_name} - Parameters: args={args}, kwargs={kwargs}")
        
        try:
            # 执行函数
            result = func(*args, **kwargs)
            
            # 计算处理时间
            end_time = time.time()
            end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
            duration = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 记录成功结果
            logger.info(f"[API CALL] {func_name} - Success at {end_time_str}")
            logger.info(f"[API CALL] {func_name} - Duration: {duration:.2f}ms")
            logger.debug(f"[API CALL] {func_name} - Result: {result}")
            
            return result
        except Exception as e:
            # 计算处理时间
            end_time = time.time()
            end_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))
            duration = (end_time - start_time) * 1000  # 转换为毫秒
            
            # 记录错误信息
            logger.error(f"[API CALL ERROR] {func_name} - Failed at {end_time_str}")
            logger.error(f"[API CALL ERROR] {func_name} - Duration: {duration:.2f}ms")
            logger.error(f"[API CALL ERROR] {func_name} - Error: {str(e)}", exc_info=True)
            
            # 重新抛出异常
            raise
    
    # 根据函数类型返回相应的包装器
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper



