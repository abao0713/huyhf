from pydantic_settings import BaseSettings
from typing import Optional


class StrategyConfig(BaseSettings):
    """策略配置"""
    # OKX API配置
    okx_api_key: Optional[str] = "222bf1bc-6412-447d-84f0-8e9bab2f3ef4"
    okx_secret_key: Optional[str] = "F33751EFB0B7912B01BEC2275DEE72E0"
    okx_passphrase: Optional[str] = "Aim98433@65@#"
    
    # 策略配置
    symbol: str = "BTC-USDT"  # 交易品种
    amount: float = 0.001  # 交易金额
    is_simulated: bool = True  # 是否使用模拟盘
    
    class Config:
        env_file = ".env"
        env_prefix = "STRATEGY_"
        extra = "ignore"


config = StrategyConfig()
