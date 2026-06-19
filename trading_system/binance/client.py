import asyncio
import logging
import sys
import time
import ssl
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import wraps

# 添加项目根目录到 Python 路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 重试装饰器
def retry_on_network_error(max_retries: int = 3, delay: float = 2.0, backoff: float = 2.0):
    """
    网络请求重试装饰器
    
    :param max_retries: 最大重试次数
    :param delay: 初始延迟（秒）
    :param backoff: 延迟倍增系数
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_str = str(e)
                    # 判断是否是网络相关错误
                    if any(err in error_str for err in ['ProxyError', 'TimeoutError', 'SSLError', 
                                                        'ConnectionError', 'Max retries', 'handshake']):
                        logger.warning(f"[retry] 网络请求失败 (尝试 {attempt + 1}/{max_retries}): {error_str}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(current_delay)
                            current_delay *= backoff
                            continue
                    # 非网络错误直接抛出
                    raise
            
            # 所有重试都失败
            logger.error(f"[retry] 网络请求最终失败 ({max_retries} 次尝试): {last_exception}")
            raise last_exception
        
        return wrapper
    return decorator

from binance_sdk_derivatives_trading_usds_futures.derivatives_trading_usds_futures import (
    DerivativesTradingUsdsFutures,
)
from binance_common.configuration import ConfigurationRestAPI
from binance_common.constants import (
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL,
    DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL, DERIVATIVES_TRADING_USDS_FUTURES_REST_API_DEMO_URL,
    DERIVATIVES_TRADING_USDS_FUTURES_WS_API_PROD_URL,
)
from binance_sdk_derivatives_trading_usds_futures.rest_api.models import (
    NewOrderSideEnum,
    NewOrderPositionSideEnum,
    NewOrderTimeInForceEnum,
    NewOrderNewOrderRespTypeEnum,
)
from pydantic import BaseModel
from trading_system.binance.config import config as binance_config

logger = logging.getLogger(__name__)

# 全局时间偏移量（毫秒）
_time_offset_ms: int = 0


def _set_time_offset(offset_ms: int):
    """设置全局时间偏移量"""
    global _time_offset_ms
    _time_offset_ms = offset_ms
    logger.info(f"时间偏移已设置: {offset_ms}ms")


def _get_timestamp_with_offset() -> int:
    """返回带偏移的时间戳（毫秒）"""
    return int(time.time() * 1000) + _time_offset_ms


def _patch_binance_timestamp():
    """Patch binance_common.utils.get_timestamp 函数"""
    import binance_common.utils as binance_utils
    binance_utils.get_timestamp = _get_timestamp_with_offset
    logger.info("已 patch binance_common.utils.get_timestamp")


def _to_dict(data: Any) -> Any:
    """将 Pydantic 模型或列表转换为 dict"""
    if isinstance(data, BaseModel):
        return data.model_dump()
    elif isinstance(data, list):
        return [_to_dict(item) for item in data]
    return data


class BinanceRestClient:
    """Binance REST API客户端（基于官方 binance-sdk-derivatives-trading-usds-futures SDK）"""

    def __init__(self, api_key: str = None, secret_key: str = None, is_simulated: bool = False):
        """初始化Binance REST API客户端
        :param api_key: API密钥
        :param secret_key: API密钥
        :param is_simulated: 是否使用模拟盘
        """
        self.api_key = api_key or binance_config.api_key
        self.secret_key = secret_key or binance_config.secret_key
        self.is_simulated = is_simulated or binance_config.is_simulated
        
        # 精度缓存
        self._symbol_precision_cache = {}
        
        # 持仓模式（对冲模式/单边模式）- None表示未检测
        self._is_hedge_mode = None
        
        # 选择正确的 base_url
        base_url = DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL if self.is_simulated else DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL

        # 创建配置
        configuration = ConfigurationRestAPI(
            api_key=self.api_key,
            api_secret=self.secret_key,
            base_path=base_url,
        )

        # 初始化客户端
        self._sdk = DerivativesTradingUsdsFutures(config_rest_api=configuration)
        
        # 同步服务器时间并应用时间偏移
        self._sync_server_time()
        
        # Patch SDK 的时间戳函数
        _patch_binance_timestamp()

    def _sync_server_time(self):
        """同步服务器时间，计算本地时间与服务器时间的偏移量"""
        try:
            import requests
            local_time_before = int(time.time() * 1000)
            
            # 调用 Binance 时间 API
            base_url = DERIVATIVES_TRADING_USDS_FUTURES_REST_API_TESTNET_URL if self.is_simulated else DERIVATIVES_TRADING_USDS_FUTURES_REST_API_PROD_URL
            response = requests.get(f"{base_url}/fapi/v1/time", timeout=5000)
            response.raise_for_status()
            
            server_time = response.json().get("serverTime")
            local_time_after = int(time.time() * 1000)
            
            if server_time:
                # 计算本地时间（取请求前后的平均值）
                local_time_avg = (local_time_before + local_time_after) // 2
                offset = server_time - local_time_avg
                
                _set_time_offset(offset)
                logger.info(f"时间同步成功: 服务器时间={server_time}, 本地时间={local_time_avg}, 偏移量={offset}ms")
            else:
                logger.warning("服务器时间获取失败，使用时间偏移 0")
                
        except Exception as e:
            logger.error(f"时间同步失败: {e}，使用时间偏移 0")

    def _run_sync(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def close(self):
        pass

    async def place_order(
        self,
        symbol: str,
        side: str,
        position_side: str = None,  # 改为可选参数
        order_type: str = "MARKET",
        quantity: float = 0.0,
        price: float = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """下单
        :param symbol: 交易对，如 "BTCUSDT"
        :param side: 买入或卖出 "BUY" / "SELL"
        :param position_side: 持仓方向 "LONG" / "SHORT"（对冲模式必需，单边模式不传）
        :param order_type: 订单类型 "LIMIT" / "MARKET"
        :param quantity: 数量
        :param price: 价格（限价单必需）
        :param time_in_force: 有效期限 "GTC" / "IOC" / "FOK"
        :return: 下单结果
        """
        params = {
            "symbol": symbol,
            "side": side_enum,
            "type": order_type,
            "quantity": quantity,
            "position_side": "BOTH",
        }
        if order_type == "LIMIT":
            params["price"] = price
            params["time_in_force"] = NewOrderTimeInForceEnum(time_in_force)

        logger.info(f"[place_order] Request: symbol={symbol}, side={side}, type={order_type}, quantity={quantity}, price={price}, position_side={position_side}")

        try:
            response = await self._run_sync(self._sdk.rest_api.new_order, **params)
            result = _to_dict(response.data())
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
        params = {"symbol": symbol}
        if order_id:
            params["order_id"] = order_id
        if orig_client_order_id:
            params["orig_client_order_id"] = orig_client_order_id

        logger.info(f"[get_order] Request: {params}")

        try:
            response = await self._run_sync(self._sdk.rest_api.query_order, **params)
            return _to_dict(response.data())
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
        params = {"symbol": symbol}
        if order_id:
            params["order_id"] = order_id
        if orig_client_order_id:
            params["orig_client_order_id"] = orig_client_order_id

        logger.info(f"[cancel_order] Request: {params}")

        try:
            response = await self._run_sync(self._sdk.rest_api.cancel_order, **params)
            result = _to_dict(response.data())
            logger.info(f"[cancel_order] Cancelled: {result}")
            return result
        except Exception as e:
            logger.error(f"[cancel_order] Cancel failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """查询所有未成交订单（使用 current_all_open_orders API）
        :param symbol: 交易对（可选），不传则返回所有交易对的未成交订单
        :return: 未成交订单列表
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        logger.info(f"[get_open_orders] Request: {params}")

        try:
            response = await self._run_sync(self._sdk.rest_api.current_all_open_orders, **params)
            result = _to_dict(response.data())
            if isinstance(result, list):
                logger.info(f"[get_open_orders] 获取到 {len(result)} 个未成交订单")
                return result
            return []
        except Exception as e:
            logger.error(f"[get_open_orders] Failed: {e}")
            return []

    @staticmethod
    def is_order_filled(order: Dict[str, Any]) -> bool:
        """判断订单是否完全成交
        :param order: 订单信息字典
        :return: 是否完全成交
        """
        return order.get("status") == "FILLED"

    @staticmethod
    def is_order_partially_filled(order: Dict[str, Any]) -> bool:
        """判断订单是否部分成交
        :param order: 订单信息字典
        :return: 是否部分成交
        """
        return order.get("status") == "PARTIALLY_FILLED"

    @staticmethod
    def is_order_cancelled(order: Dict[str, Any]) -> bool:
        """判断订单是否已取消
        :param order: 订单信息字典
        :return: 是否已取消
        """
        return order.get("status") == "CANCELED"

   

    async def get_account_balance(self) -> Dict[str, Any]:
        """获取账户余额（使用 futures_account_balance_v3 API）
        
        返回字段说明：
        - positionInitialMargin: 仓位占初始保证金
        - openOrderInitialMargin: 挂单占初始保证金
        - crossWalletBalance: 跨仓钱包余额
        - crossUnPnl: 跨仓未实现盈亏
        - availableBalance: 可用余额
        - maxWithdrawAmount: 最大可提
        
        :return: 账户余额信息字典，包含上述字段
        """
        try:
            response = await self._run_sync(self._sdk.rest_api.futures_account_balance_v3, recv_window=6000)
            result = _to_dict(response.data())
            
            # futures_account_balance_v3 返回的是列表，找到 USDT 资产
            if isinstance(result, list):
                usdt_balance = None
                for asset in result:
                    if asset.get("asset") == "USDT":
                        usdt_balance = asset
                        break
                
                if usdt_balance:
                    # 提取需要的字段（SDK返回snake_case格式）
                    balance_info = {
                        "positionInitialMargin": float(usdt_balance.get("position_initial_margin", 0)),
                        "openOrderInitialMargin": float(usdt_balance.get("open_order_initial_margin", 0)),
                        "crossWalletBalance": float(usdt_balance.get("cross_wallet_balance", 0)),
                        "crossUnPnl": float(usdt_balance.get("cross_un_pnl", 0)),
                        "availableBalance": float(usdt_balance.get("available_balance", 0)),
                        "maxWithdrawAmount": float(usdt_balance.get("max_withdraw_amount", 0)),
                        "asset": "USDT"
                    }
                    logger.info(f"[get_account_balance] Success - 可用余额: {balance_info['availableBalance']:.2f} USDT")
                    return balance_info
                else:
                    logger.warning("[get_account_balance] 未找到 USDT 资产")
                    return {"error": "USDT asset not found", "msg": "未找到 USDT 资产"}
            else:
                logger.error(f"[get_account_balance] 返回格式异常: {type(result)}")
                return {"error": "Invalid response format", "msg": "返回格式异常"}
                
        except Exception as e:
            logger.error(f"[get_account_balance] Failed: {e}")
            return {"error": str(e), "msg": str(e)}

    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """获取持仓信息（使用 position_information_v3 API）
        :param symbol: 交易对（可选）
        :return: 持仓列表
        """
        params = {}
        if symbol:
            params["symbol"] = symbol

        logger.info(f"[get_positions] Request: {params}")

        try:
            response = await self._run_sync(self._sdk.rest_api.position_information_v3, **params)
            result = _to_dict(response.data())
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
            response = await self._run_sync(self._sdk.rest_api.exchange_information)
            result = _to_dict(response.data())
            # 缓存精度信息
            self._cache_precision(result)
            return result
        except Exception as e:
            logger.error(f"[get_exchange_info] Failed: {e}")
            return {"error": str(e), "msg": str(e)}
    
    async def detect_hedge_mode(self) -> bool:
        """检测账户是否为对冲模式
        :return: True-对冲模式，False-单边模式
        """
        try:
            response = await self._run_sync(self._sdk.rest_api.get_position_mode)
            data = _to_dict(response.data())
            self._is_hedge_mode = data.get("dualSidePosition", False)
            logger.info(f"[detect_hedge_mode] Detected: {self._is_hedge_mode}")
            return self._is_hedge_mode
        except Exception as e:
            logger.error(f"[detect_hedge_mode] Failed: {e}")
            # 默认使用单边模式
            self._is_hedge_mode = False
            return False
    
    def _cache_precision(self, exchange_info: Dict):
        """缓存交易对精度信息"""
        try:
            symbols = exchange_info.get("symbols", [])
            for symbol_info in symbols:
                symbol = symbol_info.get("symbol")
                if not symbol:
                    continue
                
                price_precision = 0
                quantity_precision = 0
                
                filters = symbol_info.get("filters", [])
                for f in filters:
                    filter_type = f.get("filterType")
                    if filter_type == "PRICE_FILTER":
                        tick_size = f.get("tickSize", "0.0001")
                        price_precision = max(0, len(str(tick_size).split(".")[1]) if "." in tick_size else 0)
                    elif filter_type == "LOT_SIZE":
                        step_size = f.get("stepSize", "0.001")
                        quantity_precision = max(0, len(str(step_size).split(".")[1]) if "." in step_size else 0)
                
                self._symbol_precision_cache[symbol] = {
                    "price_precision": price_precision,
                    "quantity_precision": quantity_precision
                }
        except Exception as e:
            logger.error(f"[cache_precision] Failed: {e}")
    
    def _get_precision(self, symbol: str) -> Dict[str, int]:
        """获取交易对精度
        :param symbol: 交易对
        :return: {"price_precision": int, "quantity_precision": int}
        """
        # 先检查缓存
        if symbol in self._symbol_precision_cache:
            return self._symbol_precision_cache[symbol]
        
        # 默认精度
        return {"price_precision": 2, "quantity_precision": 4}
    
    def _format_price(self, symbol: str, price: float) -> float:
        """格式化价格到正确精度"""
        precision = self._get_precision(symbol)["price_precision"]
        return round(price, precision)
    
    def _format_quantity(self, symbol: str, quantity: float) -> float:
        """格式化数量到正确精度"""
        precision = self._get_precision(symbol)["quantity_precision"]
        return round(quantity, precision)

    @retry_on_network_error(max_retries=3, delay=3.0)
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
        logger.debug(f"[get_continuous_klines] pair={pair}, interval={interval}, limit={limit}")

        params = {
            "pair": pair,
            "contract_type": contractType,
            "interval": interval,
            "limit": limit
        }
        if startTime:
            params["start_time"] = startTime
        if endTime:
            params["end_time"] = endTime

        try:
            response = await self._run_sync(self._sdk.rest_api.continuous_contract_kline_candlestick_data, **params)
            return _to_dict(response.data())
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
        :param contractType: 合约类型（此参数在现货K线中不使用）
        :param interval: 时间间隔，如1m, 5m, 15m, 30m, 1h, 4h, 1d
        :param startTime: 起始时间，毫秒时间戳
        :param endTime: 结束时间，毫秒时间戳
        :param limit: 返回数据量，默认500，最大1500
        :return: K线数据列表
        """
        logger.info(f"[get_spot_klines] symbol={symbol}, interval={interval}, limit={limit}")

        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        if startTime:
            params["start_time"] = startTime
        if endTime:
            params["end_time"] = endTime

        try:
            response = await self._run_sync(self._sdk.rest_api.kline_candlestick_data, **params)
            return _to_dict(response.data())
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
            account = await client.get_account_balance()
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
