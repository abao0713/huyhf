from pydantic_settings import BaseSettings
from typing import Optional


class OKXConfig(BaseSettings):
    # API配置
    api_key: Optional[str] = None
    secret_key: Optional[str] = None
    passphrase: Optional[str] = None
    
    # 实盘WebSocket地址（私有频道）
    real_ws_url: str = "wss://ws.okx.com:8443/ws/v5/private"
    # 模拟盘WebSocket地址（私有频道）
    sim_ws_url: str = "wss://wspap.okx.com:8443/ws/v5/private"
    # 实盘WebSocket地址（业务频道）
    real_business_ws_url: str = "wss://ws.okx.com:8443/ws/v5/business"
    # 模拟盘WebSocket地址（业务频道）
    sim_business_ws_url: str = "wss://wspap.okx.com:8443/ws/v5/business"
    
    # 限速配置
    max_connections_per_second: int = 3  # 基于IP的连接限制
    max_requests_per_hour: int = 480  # 每个连接的请求限制
    max_orders_per_2s: int = 50  # 订单限速
    
    # 超时配置
    request_timeout: int = 30  # 请求超时时间（秒）
    reconnect_interval: int = 5  # 重连间隔（秒）
    
    class Config:
        env_file = ".env"
        env_prefix = "OKX_"
        extra = "ignore"


config = OKXConfig()
