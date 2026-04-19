from trading_system.okx.websocket.client import OKXWebSocketClient
from trading_system.okx.rest.client import OKXRestClient
from trading_system.okx.config import config
from trading_system.okx.utils.rate_limiter import request_limiter, order_limiter
from trading_system.okx.utils.logger import log_api_call
from typing import Optional, Dict, Any, Callable, List
import asyncio
import logging

logger = logging.getLogger(__name__)


class OKXAPI:
    """OKX API封装"""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, 
                 passphrase: Optional[str] = None, is_simulated: bool = False):
        """
        初始化OKX API
        :param api_key: API Key
        :param secret_key: Secret Key
        :param passphrase: Passphrase
        :param is_simulated: 是否使用模拟盘
        """
        self.api_key = api_key or config.api_key
        self.secret_key = secret_key or config.secret_key
        self.passphrase = passphrase or config.passphrase
        self.is_simulated = is_simulated
        self.client = OKXWebSocketClient(is_simulated=is_simulated, channel_type="business")
        self.rest_client = OKXRestClient(is_simulated=is_simulated)
        self._subscriptions = set()
    
    @log_api_call
    async def connect(self):
        """连接到WebSocket服务器"""
        await self.client.connect()
    
    @log_api_call
    async def login(self):
        """登录到OKX"""
        if not self.api_key or not self.secret_key or not self.passphrase:
            raise ValueError("API credentials are required")
        # 设置REST API客户端凭证
        self.rest_client.set_credentials(self.api_key, self.secret_key, self.passphrase)
        # WebSocket登录
        await self.client.login(self.api_key, self.passphrase, self.secret_key)
    
    @log_api_call
    async def subscribe(self, channel: str, inst_id: str, 
                      callback: Optional[Callable] = None):
        """
        订阅频道
        :param channel: 频道名称
        :param inst_id: 交易对
        :param callback: 回调函数
        """
        # 限速检查
        request_limiter.wait()
        
        subscription_key = f"{channel}:{inst_id}"
        if subscription_key not in self._subscriptions:
            await self.client.subscribe(channel, inst_id)
            self._subscriptions.add(subscription_key)
            logger.info(f"Subscribed to {channel} for {inst_id}")
        
        if callback:
            self.client.register_handler(channel, callback)
    
    @log_api_call
    async def unsubscribe(self, channel: str, inst_id: str):
        """
        取消订阅
        :param channel: 频道名称
        :param inst_id: 交易对
        """
        # 限速检查
        request_limiter.wait()
        
        subscription_key = f"{channel}:{inst_id}"
        if subscription_key in self._subscriptions:
            await self.client.unsubscribe(channel, inst_id)
            self._subscriptions.remove(subscription_key)
            logger.info(f"Unsubscribed from {channel} for {inst_id}")
    
    @log_api_call
    async def place_order(self, **order_params):
        """
        下单
        :param order_params: 订单参数
        """
        # 限速检查
        order_limiter.wait()
        
        # 验证必要参数
        required_params = ['side', 'instId', 'tdMode', 'ordType', 'sz']
        for param in required_params:
            if param not in order_params:
                raise ValueError(f"Missing required parameter: {param}")
        
        result = await self.client.send_order(order_params)
        logger.info(f"Placed order: {order_params}")
        return result
    
    @log_api_call
    async def place_batch_orders(self, order_params_list):
        """
        批量下单
        :param order_params_list: 订单参数列表
        """
        # 限速检查
        order_limiter.wait()
        
        # 验证必要参数
        for order_params in order_params_list:
            required_params = ['side', 'instId', 'tdMode', 'ordType', 'sz']
            for param in required_params:
                if param not in order_params:
                    raise ValueError(f"Missing required parameter: {param} in order {order_params}")
        
        result = await self.client.send_batch_orders(order_params_list)
        logger.info(f"Placed batch orders: {order_params_list}")
        return result
    
    @log_api_call
    async def cancel_order(self, inst_id, ord_id):
        """
        撤单
        :param inst_id: 交易对
        :param ord_id: 订单ID
        """
        # 限速检查
        order_limiter.wait()
        
        cancel_params = {
            "instId": inst_id,
            "ordId": ord_id
        }
        
        result = await self.client.cancel_order(cancel_params)
        logger.info(f"Canceled order: {cancel_params}")
        return result
    
    @log_api_call
    async def cancel_batch_orders(self, cancel_params_list):
        """
        批量撤单
        :param cancel_params_list: 撤单参数列表
        """
        # 限速检查
        order_limiter.wait()
        
        # 验证必要参数
        for cancel_params in cancel_params_list:
            required_params = ['instId', 'ordId']
            for param in required_params:
                if param not in cancel_params:
                    raise ValueError(f"Missing required parameter: {param} in cancel request {cancel_params}")
        
        result = await self.client.cancel_batch_orders(cancel_params_list)
        logger.info(f"Canceled batch orders: {cancel_params_list}")
        return result
    
    @log_api_call
    async def close(self):
        """关闭连接"""
        # 关闭WebSocket连接
        await self.client.close()
        # 关闭REST API会话
        await self.rest_client.close()
        logger.info("OKX API connection closed")
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.client.is_connected
    
    @property
    def is_authenticated(self) -> bool:
        """是否已认证"""
        return self.client.is_authenticated
    
    @log_api_call
    async def get_order(self, ord_id: str, inst_id: str) -> Dict[str, Any]:
        """
        获取订单信息
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: 订单信息
        """
        # 验证凭证
        if not self.api_key or not self.secret_key or not self.passphrase:
            raise ValueError("API credentials are required")
        
        # 调用REST API获取订单信息
        result = await self.rest_client.get_order(ord_id, inst_id)
        logger.info(f"Retrieved order: {ord_id} for {inst_id}")
        return result
    
    @log_api_call
    async def get_batch_orders(self, ord_ids: list, inst_id: str) -> Dict[str, Any]:
        """
        批量获取订单信息
        :param ord_ids: 订单ID列表
        :param inst_id: 交易对
        :return: 订单信息列表
        """
        # 验证凭证
        if not self.api_key or not self.secret_key or not self.passphrase:
            raise ValueError("API credentials are required")
        
        # 调用REST API批量获取订单信息
        result = await self.rest_client.get_batch_orders(ord_ids, inst_id)
        logger.info(f"Retrieved batch orders: {ord_ids} for {inst_id}")
        return result
    
    async def is_order_filled(self, ord_id: str, inst_id: str) -> bool:
        """
        检查订单是否完全成交
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: True表示订单完全成交，False表示未完全成交
        """
        order_info = await self.get_order(ord_id, inst_id)
        if order_info and order_info.get('data'):
            order_data = order_info['data'][0]
            return order_data.get('state') == 'filled'
        return False
    
    async def get_order_state(self, ord_id: str, inst_id: str) -> str:
        """
        获取订单状态
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: 订单状态
        """
        order_info = await self.get_order(ord_id, inst_id)
        if order_info and order_info.get('data'):
            order_data = order_info['data'][0]
            return order_data.get('state', 'unknown')
        return 'unknown'
    
    def get_order_state_sync(self, ord_id: str, inst_id: str) -> str:
        """
        同步获取订单状态
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: 订单状态
        """
        return asyncio.run(self.get_order_state(ord_id, inst_id))
    
    def is_order_filled_sync(self, ord_id: str, inst_id: str) -> bool:
        """
        同步检查订单是否完全成交
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: True表示订单完全成交，False表示未完全成交
        """
        return asyncio.run(self.is_order_filled(ord_id, inst_id))


# 同步版本的API封装
class OKXSyncAPI:
    """同步版本的OKX API"""
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None, 
                 passphrase: Optional[str] = None, is_simulated: bool = False):
        """
        初始化同步API
        :param api_key: API Key
        :param secret_key: Secret Key
        :param passphrase: Passphrase
        :param is_simulated: 是否使用模拟盘
        """
        self.api = OKXAPI(api_key, secret_key, passphrase, is_simulated)
    
    @log_api_call
    def connect(self):
        """连接到WebSocket服务器"""
        asyncio.run(self.api.connect())
    
    @log_api_call
    def login(self):
        """登录到OKX"""
        asyncio.run(self.api.login())
    
    @log_api_call
    def subscribe(self, channel: str, inst_id: str, callback: Optional[Callable] = None):
        """订阅频道"""
        asyncio.run(self.api.subscribe(channel, inst_id, callback))
    
    @log_api_call
    def unsubscribe(self, channel: str, inst_id: str):
        """取消订阅"""
        asyncio.run(self.api.unsubscribe(channel, inst_id))
    
    @log_api_call
    def place_order(self, **order_params):
        """下单"""
        return asyncio.run(self.api.place_order(**order_params))
    
    @log_api_call
    def place_batch_orders(self, order_params_list):
        """批量下单"""
        return asyncio.run(self.api.place_batch_orders(order_params_list))
    
    @log_api_call
    def cancel_order(self, inst_id, ord_id):
        """撤单"""
        return asyncio.run(self.api.cancel_order(inst_id, ord_id))
    
    @log_api_call
    def cancel_batch_orders(self, cancel_params_list):
        """批量撤单"""
        return asyncio.run(self.api.cancel_batch_orders(cancel_params_list))
    
    @log_api_call
    def close(self):
        """关闭连接"""
        asyncio.run(self.api.close())
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self.api.is_connected
    
    @property
    def is_authenticated(self) -> bool:
        """是否已认证"""
        return self.api.is_authenticated
    
    @log_api_call
    def get_order(self, ord_id: str, inst_id: str) -> Dict[str, Any]:
        """
        获取订单信息
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: 订单信息
        """
        return asyncio.run(self.api.get_order(ord_id, inst_id))
    
    @log_api_call
    def get_batch_orders(self, ord_ids: list, inst_id: str) -> Dict[str, Any]:
        """
        批量获取订单信息
        :param ord_ids: 订单ID列表
        :param inst_id: 交易对
        :return: 订单信息列表
        """
        return asyncio.run(self.api.get_batch_orders(ord_ids, inst_id))
    
    def is_order_filled(self, ord_id: str, inst_id: str) -> bool:
        """
        检查订单是否完全成交
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: True表示订单完全成交，False表示未完全成交
        """
        return self.api.is_order_filled_sync(ord_id, inst_id)
    
    def get_order_state(self, ord_id: str, inst_id: str) -> str:
        """
        获取订单状态
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: 订单状态
        """
        return self.api.get_order_state_sync(ord_id, inst_id)
