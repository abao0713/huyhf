import asyncio
import aiohttp
import logging
from typing import Dict, Any, Optional, List
from .signer import BinanceSigner
from .config import config as binance_config
from .enums import OrderSide, OrderType, PositionSide, TimeInForce
from .database_adapter import BinanceDatabaseAdapter

logger = logging.getLogger(__name__)


class BinanceAPIError(Exception):
    """Binance API错误"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(f"Binance API Error {code}: {message}")


class APIResponse:
    """API响应包装类"""
    def __init__(self, data: dict):
        self.data = data
        self.code = data.get("code", 0)
        self.msg = data.get("msg", "Success")
        self.rate_limits = self._extract_rate_limits()

    def _extract_rate_limits(self) -> dict:
        """提取速率限制信息"""
        return {}

    def get_data(self) -> dict:
        """获取响应数据"""
        return self.data

    def is_success(self) -> bool:
        """是否成功"""
        return self.code == 0 or self.msg == "Success"


class BinanceSDKClient:
    """Binance SDK客户端（参考官方SDK设计）"""

    def __init__(self, api_key: str = None, secret_key: str = None, is_simulated: bool = False, proxy: Dict[str, Any] = None):
        """初始化Binance SDK客户端
        :param api_key: API密钥
        :param secret_key: API密钥
        :param is_simulated: 是否使用模拟盘
        :param proxy: 代理配置 {"host": "127.0.0.1", "port": 7890, "protocol": "http"}
        """
        self.api_key = api_key or binance_config.api_key
        self.secret_key = secret_key or binance_config.secret_key
        self.is_simulated = is_simulated or binance_config.is_simulated
        self.base_url = binance_config.rest_url

        # 代理配置：优先使用传入的配置，否则使用配置文件中的配置
        if proxy:
            self.proxy = proxy
        elif binance_config.proxy_enabled:
            self.proxy = binance_config.get_proxy_dict()
        else:
            self.proxy = None

        self.signer = BinanceSigner(self.secret_key)
        self._session: Optional[aiohttp.ClientSession] = None
        self.database_adapter = None

        if self.proxy:
            logger.info(f"[BinanceSDKClient] Proxy enabled: {self.proxy['host']}:{self.proxy['port']}")

    def set_database_adapter(self, adapter: BinanceDatabaseAdapter):
        """设置数据库适配器"""
        self.database_adapter = adapter

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(keepalive_timeout=60)

            if self.proxy:
                proxy_url = f"{self.proxy['protocol']}://{self.proxy['host']}:{self.proxy['port']}"
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30),
                    connector=connector,
                    proxy=proxy_url
                )
            else:
                self._session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30),
                    connector=connector
                )
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
    ) -> APIResponse:
        """发送HTTP请求
        :param method: HTTP方法
        :param path: 请求路径
        :param params: URL参数
        :param body: 请求体
        :param signed: 是否需要签名
        :return: API响应
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
                async with session.get(url, params=params, headers=headers) as response:
                    result = await response.json()
                    logger.info(f"[{method}] {path} Response: {result}")
                    return APIResponse(result)
            elif method == "POST":
                async with session.post(url, json=body, params=params, headers=headers) as response:
                    result = await response.json()
                    logger.info(f"[{method}] {path} Response: {result}")
                    return APIResponse(result)
            elif method == "DELETE":
                async with session.delete(url, params=params, headers=headers) as response:
                    result = await response.json()
                    logger.info(f"[{method}] {path} Response: {result}")
                    return APIResponse(result)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            logger.error(f"HTTP请求失败: {str(e)}")
            return APIResponse({"error": str(e), "code": -1})
        except Exception as e:
            logger.error(f"请求异常: {str(e)}")
            return APIResponse({"error": str(e), "code": -1})

    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        position_side: PositionSide,
        order_type: OrderType,
        quantity: float,
        price: float = None,
        time_in_force: TimeInForce = TimeInForce.GTC
    ) -> Dict[str, Any]:
        """下单
        :param symbol: 交易对，如 "BTCUSDT"
        :param side: 买入或卖出
        :param position_side: 持仓方向
        :param order_type: 订单类型
        :param quantity: 数量
        :param price: 价格（限价单必需）
        :param time_in_force: 有效期限
        :return: 下单结果
        """
        path = "/order"

        params = {
            "symbol": symbol,
            "side": side.value,
            "positionSide": position_side.value,
            "type": order_type.value,
            "quantity": quantity
        }

        if order_type == OrderType.LIMIT:
            params["price"] = price
            params["timeInForce"] = time_in_force.value

        logger.info(f"[place_order] Request: {params}")

        response = await self._request("POST", path, params=params, signed=True)

        if response.is_success():
            logger.info(f"[place_order] Order placed successfully: {response.get_data()}")

            # 保存到数据库
            if self.database_adapter:
                order_data = response.get_data()
                order_data["symbol"] = symbol
                order_data["side"] = side.value
                order_data["positionSide"] = position_side.value
                order_data["type"] = order_type.value
                order_data["quantity"] = quantity
                order_data["price"] = price

                saved_order = self.database_adapter.save_order(order_data)
                if saved_order:
                    logger.info(f"[place_order] Order saved to database: {saved_order.order_id}")
        else:
            logger.error(f"[place_order] Order failed: {response.msg}")
            raise BinanceAPIError(response.code, response.msg)

        return response.get_data()

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

        response = await self._request("GET", path, params=params, signed=True)

        if not response.is_success():
            logger.error(f"[get_order] Failed: {response.msg}")
            raise BinanceAPIError(response.code, response.msg)

        return response.get_data()

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

        response = await self._request("DELETE", path, params=params, signed=True)

        if response.is_success():
            logger.info(f"[cancel_order] Order cancelled successfully")

            # 更新数据库订单状态
            if self.database_adapter and order_id:
                from trading_system.models.trading_order import OrderStatusEnum
                self.database_adapter.update_order_status(order_id, OrderStatusEnum.CANCELLED)
        else:
            logger.error(f"[cancel_order] Cancel failed: {response.msg}")
            raise BinanceAPIError(response.code, response.msg)

        return response.get_data()

    async def get_account(self) -> Dict[str, Any]:
        """获取账户信息
        :return: 账户信息
        """
        path = "/account"

        params = {"timestamp": BinanceSigner.get_timestamp()}
        params["signature"] = self.signer.sign_request(params)

        logger.info(f"[get_account] Request")

        response = await self._request("GET", path, params=params, signed=True)

        if not response.is_success():
            logger.error(f"[get_account] Failed: {response.msg}")
            raise BinanceAPIError(response.code, response.msg)

        return response.get_data()

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

        response = await self._request("GET", path, params=params, signed=True)

        if not response.is_success():
            logger.error(f"[get_positions] Failed: {response.msg}")
            raise BinanceAPIError(response.code, response.msg)

        data = response.get_data()
        if isinstance(data, list):
            return data
        return []

    async def get_exchange_info(self) -> Dict[str, Any]:
        """获取交易所信息
        :return: 交易所信息
        """
        path = "/exchangeInfo"

        logger.info(f"[get_exchange_info] Request")

        response = await self._request("GET", path)

        if not response.is_success():
            logger.error(f"[get_exchange_info] Failed: {response.msg}")
            raise BinanceAPIError(response.code, response.msg)

        return response.get_data()
