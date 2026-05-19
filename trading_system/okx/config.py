import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class ProxyConfig:
    """代理配置"""
    def __init__(self, host: str, port: int, protocol: str = "http"):
        self.host = host
        self.port = port
        self.protocol = protocol

    def to_dict(self) -> Dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol
        }

    @property
    def url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"


class BinanceConfig:
    """Binance API配置"""

    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY", "")
        self.private_key = os.getenv("BINANCE_PRIVATE_KEY", "") or None
        self.private_key_passphrase = os.getenv("BINANCE_PRIVATE_KEY_PASSPHRASE", "") or None
        self.is_simulated = os.getenv("BINANCE_IS_SIMULATED", "false").lower() == "true"

        # 代理配置
        proxy_host = os.getenv("BINANCE_PROXY_HOST", "")
        proxy_port = int(os.getenv("BINANCE_PROXY_PORT", "0"))
        proxy_protocol = os.getenv("BINANCE_PROXY_PROTOCOL", "http")
        self.proxy_enabled = bool(proxy_host and proxy_port > 0)
        self.proxy = ProxyConfig(proxy_host, proxy_port, proxy_protocol) if self.proxy_enabled else None

        if self.is_simulated:
            self.rest_base_url = "https://testnet.binancefuture.com"
        else:
            self.rest_base_url = "https://fapi.binance.com"

        self.rest_api_path = "/fapi/v1"

    @property
    def rest_url(self) -> str:
        return f"{self.rest_base_url}{self.rest_api_path}"

    def is_configured(self) -> bool:
        return bool(self.api_key and (self.secret_key or self.private_key))

    def get_proxy_dict(self) -> Optional[Dict[str, Any]]:
        """获取代理配置字典"""
        if self.proxy:
            return self.proxy.to_dict()
        return None


config = BinanceConfig()
