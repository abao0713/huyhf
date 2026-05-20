import asyncio
import logging
from typing import Dict, Any, Optional, List
from binance.um_futures import UMFutures
from trading_system.binance.config import config as binance_config

logger = logging.getLogger(__name__)


class BinanceRestClient:
    """Binance REST API客户端（基于官方 UMFutures SDK）"""

    def __init__(self, api_key: str = None, secret_key: str = None, is_simulated: bool = False):
        """初始化Binance REST API客户端
        :param api_key: API密钥
        :param secret_key: API密钥
        :param is_simulated: 是否使用模拟盘
        """
        self.api_key = api_key or binance_config.api_key
        self.secret_key = secret_key or binance_config.secret_key
        self.is_simulated = is_simulated or binance_config.is_simulated

        if self.is_simulated:
            base_url = "https://testnet.binancefuture.com"
        else:
            base_url = "https://fapi.binance.com"

        self._sdk = UMFutures(key=self.api_key, secret=self.secret_key, base_url=base_url)
        self._sdk.session.trust_env = False

    def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def close(self):
        pass

    async def place_order(
        self,
        symbol: str,
        side: str,
        position_side: str,
        order_type: str,
        quantity: float,
        price: float = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """下单
        :param symbol: 交易对，如 "BTCUSDT"
        :param side: 买入或卖出 "BUY" / "SELL"
        :param position_side: 持仓方向 "LONG" / "SHORT"
        :param order_type: 订单类型 "LIMIT" / "MARKET"
        :param quantity: 数量
        :param price: 价格（限价单必需）
        :param time_in_force: 有效期限 "GTC" / "IOC" / "FOK"
        :return: 下单结果
        """
        params = dict(symbol=symbol, side=side, type=order_type, quantity=quantity,
                      positionSide=position_side)
        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force

        logger.info(f"[place_order] Request: {params}")

        try:
            result = await self._run_sync(self._sdk.new_order, **params)
            logger.info(f"[place_order] Order placed: {result}")
            return result
        except Exception as e:
            logger.error(f"[place_order] Order failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def get_order(
        self,
        symbol: str,
        order_id: int = None,
        orig_client_order_id: str = None
    ) -> Dict[str, Any]:
        """查询订单
        :param symbol: 交易对
        :param order_id: 订单ID
        :param orig_client_order_id: 客户端订单ID
        :return: 订单信息
        """
        params = dict(symbol=symbol)
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        logger.info(f"[get_order] Request: {params}")

        try:
            result = await self._run_sync(self._sdk.query_order, **params)
            return result
        except Exception as e:
            logger.error(f"[get_order] Query failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def cancel_order(
        self,
        symbol: str,
        order_id: int = None,
        orig_client_order_id: str = None
    ) -> Dict[str, Any]:
        """取消订单
        :param symbol: 交易对
        :param order_id: 订单ID
        :param orig_client_order_id: 客户端订单ID
        :return: 取消结果
        """
        params = dict(symbol=symbol)
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        logger.info(f"[cancel_order] Request: {params}")

        try:
            result = await self._run_sync(self._sdk.cancel_order, **params)
            logger.info(f"[cancel_order] Cancelled: {result}")
            return result
        except Exception as e:
            logger.error(f"[cancel_order] Cancel failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def get_account(self) -> Dict[str, Any]:
        """获取账户信息
        :return: 账户信息
        """
        try:
            result = await self._run_sync(self._sdk.account, recvWindow=6000)
            return result
        except Exception as e:
            logger.error(f"[get_account] Failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """获取持仓信息
        :param symbol: 交易对（可选）
        :return: 持仓列表
        """
        params = dict()
        if symbol:
            params["symbol"] = symbol

        logger.info(f"[get_positions] Request: {params}")

        try:
            result = await self._run_sync(self._sdk.get_position_risk, **params)
            if isinstance(result, list):
                return result
            return []
        except Exception as e:
            logger.error(f"[get_positions] Failed: {e}")
            return []

    async def get_exchange_info(self) -> Dict[str, Any]:
        """获取交易所信息
        :return: 交易所信息
        """
        logger.info(f"[get_exchange_info] Request")
        try:
            result = await self._run_sync(self._sdk.exchange_info)
            return result
        except Exception as e:
            logger.error(f"[get_exchange_info] Failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def get_continuous_klines(
        self,
        pair: str,
        contractType: str = "PERPETUAL",
        interval: str = "30m",
        startTime: int = None,
        endTime: int = None,
        limit: int = 500
    ) -> List[List[Any]]:
        """获取永续合约K线数据
        :param pair: 标的交易对，如BTCUSDT
        :param contractType: 合约类型，如PERPETUAL
        :param interval: 时间间隔，如1m, 5m, 15m, 30m, 1h, 4h, 1d
        :param startTime: 起始时间，毫秒时间戳
        :param endTime: 结束时间，毫秒时间戳
        :param limit: 返回数据量，默认500，最大1500
        :return: K线数据列表
        """
        logger.info(f"[get_continuous_klines] pair={pair}, interval={interval}, limit={limit}")

        params = dict(pair=pair, contractType=contractType, interval=interval, limit=limit)
        if startTime:
            params["startTime"] = startTime
        if endTime:
            params["endTime"] = endTime

        try:
            result = await self._run_sync(self._sdk.continuous_klines, **params)
            return result
        except Exception as e:
            logger.error(f"[get_continuous_klines] Failed: {e}")
            return []

    async def get_spot_klines(
        self,
        symbol: str,
        contractType: str = "PERPETUAL",
        interval: str = "30m",
        startTime: int = None,
        endTime: int = None,
        limit: int = 500
    ) -> List[List[Any]]:
        """获取现货K线数据
        :param symbol: 标的交易对，如BTCUSDT
        :param contractType: 合约类型
        :param interval: 时间间隔，如1m, 5m, 15m, 30m, 1h, 4h, 1d
        :param startTime: 起始时间，毫秒时间戳
        :param endTime: 结束时间，毫秒时间戳
        :param limit: 返回数据量，默认500，最大1500
        :return: K线数据列表
        """
        logger.info(f"[get_spot_klines] symbol={symbol}, interval={interval}, limit={limit}")

        params = dict(symbol=symbol, interval=interval, limit=limit)
        if startTime:
            params["startTime"] = startTime
        if endTime:
            params["endTime"] = endTime

        try:
            result = await self._run_sync(self._sdk.klines, **params)
            return result
        except Exception as e:
            logger.error(f"[get_spot_klines] Failed: {e}")
            return []


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="调试Binance REST API客户端")
    parser.add_argument("--api-key", help="API密钥")
    parser.add_argument("--secret-key", help="API密钥")
    parser.add_argument("--simulated", action="store_true", help="使用模拟盘")
    args = parser.parse_args()

    async def main():
        client = BinanceRestClient(
            api_key=args.api_key,
            secret_key=args.secret_key,
            is_simulated=args.simulated
        )

        try:
            print("=" * 60)
            print("测试1: 获取交易所信息")
            print("=" * 60)
            info = await client.get_exchange_info()
            print(f"交易所信息: {info}")

            print("\n" + "=" * 60)
            print("测试2: 获取永续合约K线数据")
            print("=" * 60)
            continuous_klines = await client.get_continuous_klines(
                pair="BTCUSDT",
                contractType="PERPETUAL",
                interval="30m",
                limit=800
            )
            print(f"永续合约K线数据: {continuous_klines}")
            print(f"获取到 {len(continuous_klines) if continuous_klines else 0} 条K线数据")

            print("\n" + "=" * 60)
            print("测试3: 获取现货K线数据")
            print("=" * 60)
            spot_klines = await client.get_spot_klines(
                symbol="BTCUSDT",
                contractType="PERPETUAL",
                interval="30m",
                limit=100
            )
            print(f"现货K线数据: {spot_klines}")
            print(f"获取到 {len(spot_klines) if spot_klines else 0} 条K线数据")

            print("\n" + "=" * 60)
            print("测试4: 获取账户信息")
            print("=" * 60)
            account = await client.get_account()
            print(f"账户信息: {account}")

            print("\n" + "=" * 60)
            print("测试5: 下限价单")
            print("=" * 60)
            tick_size = 0.01
            for s in (info.get("symbols") or []) if isinstance(info, dict) else []:
                if s.get("symbol") == "BTCUSDT":
                    for f in s.get("filters", []):
                        if f.get("filterType") == "PRICE_FILTER":
                            tick_size = float(f.get("tickSize", 0.01))
                    break
            latest_price = float(continuous_klines[-1][4]) if continuous_klines else 77000.0
            price = round(round(latest_price * 0.99 / tick_size) * tick_size, 8)
            price_str = f"{price:.{str(tick_size).rstrip('0').split('.')[1]}f}" if '.' in str(tick_size) else str(int(price))
            order_result = await client.place_order(
                symbol="BTCUSDT",
                side="BUY",
                position_side="BOTH",
                order_type="LIMIT",
                quantity=0.001,
                price=float(price_str),
                time_in_force="GTC"
            )
            print(f"下单结果: {order_result}")
            order_id = order_result.get("orderId") or order_result.get("order_id")
            print(f"订单ID: {order_id}")

            print("\n" + "=" * 60)
            print("测试6: 查询订单")
            print("=" * 60)
            if order_id:
                query_result = await client.get_order(symbol="BTCUSDT", order_id=order_id)
                print(f"查询订单结果: {query_result}")

            print("\n" + "=" * 60)
            print("测试7: 取消订单")
            print("=" * 60)
            if order_id:
                cancel_result = await client.cancel_order(symbol="BTCUSDT", order_id=order_id)
                print(f"取消订单结果: {cancel_result}")

            print("\n" + "=" * 60)
            print("测试8: 获取持仓信息")
            print("=" * 60)
            positions = await client.get_positions(symbol="BTCUSDT")
            print(f"持仓信息: {positions}")

        finally:
            await client.close()

    asyncio.run(main())
