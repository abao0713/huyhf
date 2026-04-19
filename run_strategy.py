import asyncio
import logging
import sys
from trading_system.strategies.trend_following_strategy import TrendFollowingStrategy
from trading_system.strategies.config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('strategy.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def main():
    """运行策略"""
    # 检查API凭证
    if not config.okx_api_key or not config.okx_secret_key or not config.okx_passphrase:
        logger.error("Missing OKX API credentials. Please set them in .env file.")
        sys.exit(1)

    # 创建策略实例
    strategy = TrendFollowingStrategy(
        api_key=config.okx_api_key,
        secret_key=config.okx_secret_key,
        passphrase=config.okx_passphrase,
        symbol=config.symbol,
        amount=config.amount,
        is_simulated=config.is_simulated
    )

    logger.info(f"Starting strategy with symbol: {config.symbol}, amount: {config.amount}, is_simulated: {config.is_simulated}")

    # 运行策略（长期运行，直到手动停止）
    try:
        asyncio.run(strategy.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, stopping strategy...")
        asyncio.run(strategy.stop())


if __name__ == "__main__":
    main()
