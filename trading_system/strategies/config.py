from pydantic_settings import BaseSettings
from typing import Optional


class StrategyConfig(BaseSettings):
    """策略配置类，用于管理交易策略的各项参数配置"""

    # ==================== OKX API配置 ====================
    # OKX交易所API密钥，用于身份认证
    okx_api_key: Optional[str] = "222bf1bc-6412-447d-84f0-8e9bab2f3ef4"
    # OKX交易所密钥，用于签名验证
    okx_secret_key: Optional[str] = "F33751EFB0B7912B01BEC2275DEE72E0"
    # OKX交易所密码，用于API访问验证
    okx_passphrase: Optional[str] = "Aim98433@65@#"

    # ==================== 策略配置 ====================
    # 交易品种，表示要交易的货币对，默认为BTC-USDT（比特币/泰达币）
    symbol: str = "BTC-USDT"
    # 交易金额，表示每次交易的数量，默认为0.001
    amount: float = 0.001
    # 是否使用模拟盘，True表示使用模拟交易（不真实下单），False表示使用实盘
    is_simulated: bool = True

    class Config:
        """
        Pydantic配置类，定义配置加载方式

        配置加载说明：
        - env_file: 指定环境变量文件的路径，默认为".env"文件
        - env_prefix: 环境变量前缀，加载时会忽略此前缀并转换剩余部分为小写
          例如：STRATEGY_OKX_API_KEY 会被映射到 okx_api_key 字段
        - extra: 额外字段的处理方式，"ignore"表示忽略.env文件中未定义的字段
        """
        env_file = ".env"
        env_prefix = "STRATEGY_"
        extra = "ignore"


# 全局配置实例，供其他模块导入使用
config = StrategyConfig()
