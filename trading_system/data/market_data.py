import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
import aiohttp
import pandas as pd
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class MarketDataClient:
    """市场数据获取客户端"""

    def __init__(self, base_url: str = "https://api.binance.com"):
        self.base_url = base_url
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None
    ) -> pd.DataFrame:
        """获取K线数据（支持分批下载）

        :param symbol: 交易对，如 "BTCUSDT"
        :param interval: K线周期，如 "1m", "5m", "30m", "1h", "4h", "1d"
        :param limit: 每次返回数量，最大1000（默认500）
        :param start_time: 开始时间，支持格式：
                         - 字符串: "2026-03-04" 或 "2026-03-04 00:00:00"
                         - 时间戳（毫秒）: 1772582400000
                         - 为空时获取最新数据
        :param end_time: 结束时间，格式同start_time
        :return: DataFrame，包含 open_time, open, high, low, close, volume
        """
        path = "/api/v3/klines"
        url = f"{self.base_url}{path}"

        start_ts = self._parse_time(start_time) if start_time else None
        end_ts = self._parse_time(end_time) if end_time else None

        all_data = []
        current_start = start_ts
        batch_num = 0
        max_limit = min(limit, 1000)

        while True:
            params = {
                "symbol": symbol.upper(),
                "interval": interval,
                "limit": max_limit
            }

            if current_start:
                params["startTime"] = current_start
            if end_ts:
                params["endTime"] = end_ts

            try:
                session = await self._get_session()
                async with session.get(url, params=params, timeout=30) as response:
                    data = await response.json()

                    if not data:
                        logger.info(f"[get_klines] 第{batch_num+1}批: 无数据，结束")
                        break

                    all_data.extend(data)
                    batch_num += 1

                    logger.info(f"[get_klines] {symbol} {interval} 第{batch_num}批: 获取 {len(data)} 条 | 累计 {len(all_data)} 条")

                    if len(data) < max_limit:
                        logger.info(f"[get_klines] 返回数据少于请求数({max_limit})，已到末尾")
                        break

                    last_timestamp = data[-1][0]
                    current_start = last_timestamp + 1

                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"[get_klines] 第{batch_num+1}批获取失败: {str(e)}")
                break

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data, columns=[
            "open_time", "open", "high", "low", "close", "volume",
            "close_time", "quote_volume", "trades", "taker_buy_base",
            "taker_buy_quote", "ignore"
        ])

        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)

        df = df.drop_duplicates(subset=["open_time"])
        df = df.sort_values("open_time").reset_index(drop=True)

        logger.info(f"[get_klines] 总共获取 {len(df)} 条去重后数据 ({batch_num} 批)")

        return df[["open_time", "open", "high", "low", "close", "volume"]]

    def _parse_time(self, time_input: Union[str, int]) -> Optional[int]:
        """解析时间输入为毫秒时间戳

        :param time_input: 时间输入（字符串或时间戳）
        :return: 毫秒时间戳，解析失败返回None
        """
        if isinstance(time_input, int):
            return time_input

        if isinstance(time_input, str):
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d"
            ]

            for fmt in formats:
                try:
                    dt = datetime.strptime(time_input, fmt)
                    return int(dt.timestamp() * 1000)
                except ValueError:
                    continue

            logger.warning(f"[_parse_time] 无法解析时间格式: {time_input}")
            return None

        return None

    async def get_daily_klines(
        self,
        symbol: str,
        limit: int = 1000,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None
    ) -> pd.DataFrame:
        """获取日线数据
        :param symbol: 交易对
        :param limit: 每批返回数量（最大1000）
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: DataFrame
        """
        return await self.get_klines(symbol, "1d", limit, start_time, end_time)

    async def get_30m_klines(
        self,
        symbol: str,
        limit: int = 1000,
        start_time: Optional[Union[str, int]] = None,
        end_time: Optional[Union[str, int]] = None
    ) -> pd.DataFrame:
        """获取30分钟K线数据
        :param symbol: 交易对
        :param limit: 每批返回数量（最大1000）
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: DataFrame
        """
        return await self.get_klines(symbol, "30m", limit, start_time, end_time)

    async def get_latest_price(self, symbol: str) -> Optional[float]:
        """获取最新价格
        :param symbol: 交易对
        :return: 最新价格
        """
        path = "/api/v3/ticker/price"
        url = f"{self.base_url}{path}"
        params = {"symbol": symbol.upper()}

        try:
            session = await self._get_session()
            async with session.get(url, params=params, timeout=10) as response:
                data = await response.json()
                return float(data.get("price", 0))
        except Exception as e:
            logger.error(f"[get_latest_price] 获取价格失败: {str(e)}")
            return None


_client: Optional[MarketDataClient] = None


async def get_klines(symbol: str, interval: str, limit: int = 500, start_time=None, end_time=None) -> pd.DataFrame:
    """获取K线数据的便捷函数（支持分批下载）"""
    global _client
    if _client is None:
        _client = MarketDataClient()
    return await _client.get_klines(symbol, interval, limit, start_time, end_time)


async def get_daily_klines(symbol: str, limit: int = 1000, start_time=None, end_time=None) -> pd.DataFrame:
    """获取日线数据的便捷函数"""
    global _client
    if _client is None:
        _client = MarketDataClient()
    return await _client.get_daily_klines(symbol, limit, start_time, end_time)


async def get_30m_klines(symbol: str, limit: int = 1000, start_time=None, end_time=None) -> pd.DataFrame:
    """获取30分钟K线数据的便捷函数（支持分批下载）"""
    global _client
    if _client is None:
        _client = MarketDataClient()
    return await _client.get_30m_klines(symbol, limit, start_time, end_time)


async def get_latest_price(symbol: str) -> Optional[float]:
    """获取最新价格的便捷函数"""
    global _client
    if _client is None:
        _client = MarketDataClient()
    return await _client.get_latest_price(symbol)


async def close_client():
    """关闭客户端"""
    global _client
    if _client:
        await _client.close()
        _client = None


# ─── CCXT 数据适配器 ───
# 为 Crypto_Chan_4H_Master_v1 策略提供统一的多交易所数据获取接口

class CCXTDataProvider:
    """
    使用 CCXT 库获取交易所 OHLCV 数据的适配器

    设计目的：
    - 封装 CCXT 库的复杂性，提供统一的 OHLCV 数据获取接口
    - 支持任意 CCXT 支持的交易所（默认 Binance 合约）
    - 输出格式与现有 MarketDataClient 兼容的 DataFrame

    使用示例:
        provider = CCXTDataProvider("binance")
        df = provider.fetch_ohlcv("ETH/USDC", "4h", limit=500)
        dfs = provider.fetch_multiple_timeframes("ETH/USDC", ["4h", "1h", "15m"])
    """

    def __init__(self, exchange_name: str = "binance"):
        """初始化 CCXT 数据适配器

        Args:
            exchange_name: CCXT 交易所 ID，如 'binance', 'okx', 'bybit'
        """
        self.exchange_name = exchange_name
        self._exchange = None  # 延迟初始化，避免在 import 时建立连接

    def _get_exchange(self):
        """获取或创建 CCXT 交易所实例（懒加载模式）

        Returns:
            ccxt.Exchange 实例

        Raises:
            ImportError: 如果 ccxt 库未安装
        """
        if self._exchange is None:
            try:
                import ccxt  # 延迟导入，允许在无 CCXT 环境下加载策略模块
                # 启用速率限制防止被交易所封禁，默认使用合约市场
                self._exchange = getattr(ccxt, self.exchange_name)({
                    'enableRateLimit': True,
                    'options': {'defaultType': 'future'},
                })
            except ImportError:
                logger.error("[CCXT] ccxt 库未安装，请运行: pip install ccxt")
                raise
        return self._exchange

    def fetch_ohlcv(self, symbol: str, timeframe: str = "4h", limit: int = 500,
                    since_ms: Optional[int] = None) -> pd.DataFrame:
        """
        获取单周期 OHLCV K 线数据并返回标准化 DataFrame

        Args:
            symbol: 交易对，如 "BTC/USDC"（CCXT 格式，用 '/' 分隔）
            timeframe: K线周期，如 "4h", "1h", "15m", "1d"
            limit: 获取的最大 K 线条数
            since_ms: 起始时间戳（毫秒），None 表示获取最新数据

        Returns:
            pd.DataFrame with columns: open_time, open, high, low, close, volume
            如果获取失败则返回空 DataFrame
        """
        try:
            exchange = self._get_exchange()
            # 调用 CCXT 统一 API 获取 OHLCV 数据
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit, since=since_ms)
            if not ohlcv:
                return pd.DataFrame()
            # 将 CCXT 返回的 list[list] 格式转换为标准化 DataFrame
            df = pd.DataFrame(ohlcv, columns=["open_time", "open", "high", "low", "close", "volume"])
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")  # 毫秒时间戳 → datetime
            for col in ["open", "high", "low", "close", "volume"]:
                df[col] = df[col].astype(float)  # 确保数值类型统一
            return df
        except Exception as e:
            logger.error(f"[CCXT] 获取 OHLCV 失败: {e}")
            return pd.DataFrame()  # 容错：返回空 DataFrame 而非抛出异常

    def fetch_multiple_timeframes(self, symbol: str, timeframes: List[str],
                                  limit: int = 500) -> Dict[str, pd.DataFrame]:
        """
        批量获取多个时间框架的 OHLCV 数据

        用于策略的初始化阶段，一次性加载 4H/1H/15M/1D 等多周期数据。

        Args:
            symbol: 交易对
            timeframes: 时间框架列表，如 ["4h", "1h", "15m", "1d"]
            limit: 每个时间框架的 K 线条数

        Returns:
            Dict[str, pd.DataFrame]: key 为时间框架字符串，value 为对应 DataFrame
        """
        result = {}
        for tf in timeframes:
            df = self.fetch_ohlcv(symbol, timeframe=tf, limit=limit)
            result[tf] = df
            logger.info(f"[CCXT] {symbol} {tf}: {len(df)} 条K线")
        return result


if __name__ == "__main__":
    async def test():
        client = MarketDataClient()
        try:
            print("=" * 60)
            print("测试1: 基础功能（获取最新100条30m数据）")
            print("=" * 60)
            df = await client.get_30m_klines("BTCUSDT", 100)
            
            if df.empty:
                print("⚠️  无法获取数据（网络或API限制），跳过此测试")
            else:
                print(f"30分钟K线数据:\n{df.head()}")
                print(f"\n形状: {df.shape}")
                print(f"时间范围: {df['open_time'].iloc[0]} ~ {df['open_time'].iloc[-1]}")

                print("\n" + "=" * 60)
                print("测试2: 分批下载功能（180天ETHUSDT 30m数据）")
                print("=" * 60)
                df_180d = await client.get_30m_klines(
                    "ETHUSDT",
                    limit=1000,
                    start_time="2026-03-04",
                    end_time="2026-05-03"
                )
                
                if df_180d.empty:
                    print("⚠️  无法获取180天数据")
                else:
                    print(f"\n180天30m K线数据:")
                    print(f"总条数: {len(df_180d)}")
                    print(f"时间范围: {df_180d['open_time'].iloc[0]} ~ {df_180d['open_time'].iloc[-1]}")
                    print(f"\n前5行:\n{df_180d.head()}")
                    print(f"\n后5行:\n{df_180d.tail()}")

                    expected_days = (df_180d['open_time'].iloc[-1] - df_180d['open_time'].iloc[0]).days
                    print(f"\n实际覆盖天数: {expected_days} 天")
                    print(f"预期天数: 约60天（取决于API可用性）")

        finally:
            await client.close()

    asyncio.run(test())