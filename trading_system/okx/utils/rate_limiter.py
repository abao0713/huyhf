import time
from collections import deque
from threading import Lock


class RateLimiter:
    """限速管理器"""
    
    def __init__(self, max_calls: int, time_frame: int):
        """
        初始化限速器
        :param max_calls: 时间框架内的最大调用次数
        :param time_frame: 时间框架（秒）
        """
        self.max_calls = max_calls
        self.time_frame = time_frame
        self.calls = deque()
        self.lock = Lock()
    
    def __call__(self):
        """检查是否允许调用"""
        with self.lock:
            now = time.time()
            # 移除时间框架外的调用记录
            while self.calls and now - self.calls[0] > self.time_frame:
                self.calls.popleft()
            
            # 检查是否超过限制
            if len(self.calls) < self.max_calls:
                self.calls.append(now)
                return True
            return False
    
    def wait(self):
        """等待直到允许调用"""
        while not self():
            time.sleep(0.1)


# 全局限速器实例
connection_limiter = RateLimiter(max_calls=3, time_frame=1)  # 3次/秒
request_limiter = RateLimiter(max_calls=480, time_frame=3600)  # 480次/小时
order_limiter = RateLimiter(max_calls=50, time_frame=2)  # 50个/2秒
