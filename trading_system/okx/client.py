import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from trading_system.okx.signer import BinanceSigner
from trading_system.okx.config import config as binance_config

logger = logging.getLogger(__name__)


class BinanceRestClient:
    """Binance REST API客户端"""

    def __init__(self, api_key: str = None, secret_key: str = None, is_simulated: bool = False):
        """初始化Binance REST API客户端
        :param api_key: API密钥
        :param secret_key: API密钥
        :param is_simulated: 是否使用模拟盘
        """
        self.api_key = api_key or binance_config.api_key
        self.secret_key = secret_key or binance_config.secret_key
        self.is_simulated = is_simulated or binance_config.is_simulated
        self.base_url = binance_config.rest_url

        self.signer = BinanceSigner(self.secret_key)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        params: Dict[str, Any] = None,
        body: Dict[str, Any] = None,
        signed: bool = False
    ) -> Dict[str, Any]:
        """发送HTTP请求
        :param method: HTTP方法
        :param path: 请求路径
        :param params: URL参数
        :param body: 请求体
        :param signed: 是否需要签名
        :return: 响应数据
        """
        url = f"{self.base_url}{path}"
        headers = {"X-MBX-APIKEY": self.api_key}

        if params is None:
            params = {}

        if signed:
            params["timestamp"] = BinanceSigner.get_timestamp()
            params["signature"] = self.signer.sign_request(params)

        try:
            session = await self._get_session()

            if method == "GET":
                async with session.get(url, params=params, headers=headers, timeout=30) as response:
                    result = await response.json()
                    return result
            elif method == "POST":
                async with session.post(url, json=body, params=params, headers=headers, timeout=30) as response:
                    result = await response.json()
                    return result
            elif method == "DELETE":
                async with session.delete(url, params=params, headers=headers, timeout=30) as response:
                    result = await response.json()
                    return result
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP请求失败: {str(e)}")
            return {"error": str(e), "code": -1}
        except Exception as e:
            logger.error(f"请求异常: {str(e)}")
            return {"error": str(e), "code": -1}

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
        path = "/order"

        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "quantity": quantity
        }

        if order_type == "LIMIT":
            params["price"] = price
            params["timeInForce"] = time_in_force

        logger.info(f"[place_order] Request: {params}")

        result = await self._request("POST", path, params=params, signed=True)

        if result.get("code") == 0 or result.get("msg") == "Success":
            logger.info(f"[place_order] Order placed successfully: {result}")
        else:
            logger.error(f"[place_order] Order failed: {result.get('msg', result.get('error', 'Unknown error'))}")

        return result

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
        path = "/order"

        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        logger.info(f"[get_order] Request: {params}")

        result = await self._request("GET", path, params=params, signed=True)

        return result

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
        path = "/order"

        params = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id

        logger.info(f"[cancel_order] Request: {params}")

        result = await self._request("DELETE", path, params=params, signed=True)

        if result.get("code") == 0 or result.get("msg") == "Success":
            logger.info(f"[cancel_order] Order cancelled successfully")
        else:
            logger.error(f"[cancel_order] Cancel failed: {result.get('msg', 'Unknown error')}")

        return result

    async def get_account(self) -> Dict[str, Any]:
        """获取账户信息
        :return: 账户信息
        """
        path = "/account"

        params = {"timestamp": BinanceSigner.get_timestamp()}
        params["signature"] = self.signer.sign_request(params)

        logger.info(f"[get_account] Request")

        result = await self._request("GET", path, params=params, signed=True)

        return result

    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """获取持仓信息
        :param symbol: 交易对（可选）
        :return: 持仓列表
        """
        path = "/positionRisk"

        params = {"timestamp": BinanceSigner.get_timestamp()}
        if symbol:
            params["symbol"] = symbol
        params["signature"] = self.signer.sign_request(params)

        logger.info(f"[get_positions] Request: {params}")

        result = await self._request("GET", path, params=params, signed=True)

        if isinstance(result, list):
            return result
        return []

    async def get_exchange_info(self) -> Dict[str, Any]:
        """获取交易所信息
        :return: 交易所信息
        """
        path = "/exchangeInfo"

        logger.info(f"[get_exchange_info] Request")

        result = await self._request("GET", path)

        return result

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

        path = "/continuousKlines"
        params = {
            "pair": pair,
            "contractType": contractType,
            "interval": interval,
            "limit": limit
        }

        if startTime:
            params["startTime"] = startTime
        if endTime:
            params["endTime"] = endTime

        result = await self._request("GET", path, params=params)
        return result

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

        path = "/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }

        if startTime:
            params["startTime"] = startTime
        if endTime:
            params["endTime"] = endTime

        result = await self._request("GET", path, params=params)
        return result


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
            # 测试获取永续合约K线
            print("测试获取永续合约K线数据...")
            continuous_klines = await client.get_continuous_klines(
                pair="BTCUSDT",
                contractType="PERPETUAL",
                interval="30m",
                limit=800
            )
            print(f"永续合约K线数据: {continuous_klines}")
            print(f"获取到 {len(continuous_klines) if continuous_klines else 0} 条K线数据")
            
            # 测试获取现货K线
            print("\n测试获取现货K线数据...")
            spot_klines = await client.get_spot_klines(
                symbol="BTCUSDT",
                contractType="PERPETUAL",
                interval="30m",
                limit=100
            )
            print(f"现货K线数据: {spot_klines}")
            print(f"获取到 {len(spot_klines) if spot_klines else 0} 条K线数据")

        finally:
            await client.close()
    
    asyncio.run(main())
