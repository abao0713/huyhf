import asyncio
import aiohttp
import json
import logging
from typing import Optional, Dict, Any
from trading_system.okx.config import config
from trading_system.okx.utils.signer import get_timestamp, generate_sign
from trading_system.okx.utils.rate_limiter import request_limiter

logger = logging.getLogger(__name__)


class OKXRestClient:
    """OKX REST API客户端"""
    
    def __init__(self, is_simulated: bool = False):
        """
        初始化REST API客户端
        :param is_simulated: 是否使用模拟盘
        """
        self.is_simulated = is_simulated
        self.base_url = "https://www.okx.com" if not is_simulated else "https://www.okx.com"
        self.session = None
        self.api_key = None
        self.secret_key = None
        self.passphrase = None
    
    async def _init_session(self):
        """初始化HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=config.request_timeout)
            )
    
    async def close(self):
        """关闭HTTP会话"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def set_credentials(self, api_key: str, secret_key: str, passphrase: str):
        """
        设置API凭证
        :param api_key: API Key
        :param secret_key: Secret Key
        :param passphrase: Passphrase
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
    
    async def _make_request(self, method: str, request_path: str, params: Optional[Dict[str, Any]] = None, 
                           data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        发送HTTP请求
        :param method: HTTP方法
        :param request_path: 请求路径
        :param params: 查询参数
        :param data: 请求体
        :return: 响应数据
        """
        # 限速检查
        request_limiter.wait()
        
        # 初始化会话
        await self._init_session()
        
        # 准备请求
        url = f"{self.base_url}{request_path}"
        headers = await self._get_headers(method, request_path, data)
        
        # 发送请求
        try:
            if method.upper() == "GET":
                response = await self.session.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                response = await self.session.post(url, headers=headers, json=data)
            elif method.upper() == "PUT":
                response = await self.session.put(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = await self.session.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # 处理响应
            response_data = await response.json()
            
            if response.status != 200:
                logger.error(f"API request failed: {response_data}")
                raise Exception(f"API request failed: {response_data.get('msg', 'Unknown error')}")
            
            # 检查API响应代码
            if response_data.get("code") != "0":
                logger.error(f"API error: {response_data}")
                raise Exception(f"API error: {response_data.get('msg', 'Unknown error')}")
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error making request: {str(e)}")
            raise
    
    async def _get_headers(self, method: str, request_path: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        获取请求头
        :param method: HTTP方法
        :param request_path: 请求路径
        :param data: 请求体
        :return: 请求头
        """
        timestamp = get_timestamp()
        body = json.dumps(data) if data else ""
        
        # 生成签名
        signature = generate_sign(timestamp, self.secret_key, method, request_path, body)
        
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        return headers
    
    async def get_order(self, ord_id: str, inst_id: str) -> Dict[str, Any]:
        """
        获取订单信息
        :param ord_id: 订单ID
        :param inst_id: 交易对
        :return: 订单信息
        """
        request_path = "/api/v5/trade/order"
        params = {
            "ordId": ord_id,
            "instId": inst_id
        }
        
        response = await self._make_request("GET", request_path, params=params)
        return response
    
    async def get_batch_orders(self, ord_ids: list, inst_id: str) -> Dict[str, Any]:
        """
        批量获取订单信息
        :param ord_ids: 订单ID列表
        :param inst_id: 交易对
        :return: 订单信息列表
        """
        request_path = "/api/v5/trade/orders"
        params = {
            "ordId": ",".join(ord_ids),
            "instId": inst_id
        }
        
        response = await self._make_request("GET", request_path, params=params)
        return response
    
    async def close_position(self, inst_id: str, mgn_mode: str) -> Dict[str, Any]:
        """
        关闭持仓
        :param inst_id: 交易对
        :param mgn_mode: 保证金模式，cross（跨仓）或isolated（逐仓）
        :return: 关闭持仓的结果
        """
        request_path = "/api/v5/trade/close-position"
        data = {
            "instId": inst_id,
            "mgnMode": mgn_mode
        }
        
        response = await self._make_request("POST", request_path, data=data)
        return response
