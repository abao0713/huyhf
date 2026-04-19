import asyncio
import json
import time
import websockets
import logging
from typing import Optional, Dict, Any, Callable, List
from trading_system.okx.config import config
from trading_system.okx.utils.rate_limiter import connection_limiter
from trading_system.okx.utils.signer import get_timestamp, generate_sign
from trading_system.core.database import SessionLocal
from trading_system.services.crud import create_trading_order, create_trade_record
from trading_system.core.schemas import TradingOrderCreate, TradeRecordCreate
from trading_system.models.trading_order import OrderTypeEnum
from datetime import datetime

logger = logging.getLogger(__name__)


class OKXWebSocketClient:
    """OKX WebSocket客户端"""
    
    def __init__(self, is_simulated: bool = False, channel_type: str = "private"):
        """
        初始化WebSocket客户端
        :param is_simulated: 是否使用模拟盘
        :param channel_type: 频道类型，可选值：private（私有频道）、public（公共频道）、business（业务频道）
        """
        self.is_simulated = is_simulated
        self.channel_type = channel_type
        
        # 根据频道类型选择WebSocket URL
        if channel_type == "business":
            self.ws_url = config.sim_business_ws_url if is_simulated else config.real_business_ws_url
        else:  # private
            self.ws_url = config.sim_ws_url if is_simulated else config.real_ws_url
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_authenticated = False
        self.conn_id: Optional[str] = None
        self.message_handlers: Dict[str, Callable] = {}
        self.reconnect_task: Optional[asyncio.Task] = None
        self.order_callbacks: Dict[str, Callable] = {}
        
        # 连接管理器，用于管理与客户端的WebSocket连接
        self.connection_manager = None
    
    async def connect(self):
        """连接到WebSocket服务器"""
        # 限速检查
        connection_limiter.wait()
        
        headers = {}
        if self.is_simulated:
            headers["x-simulated-trading"] = "1"
        
        try:
            logger.info(f"Connecting to {self.ws_url}")
            self.websocket = await websockets.connect(
                self.ws_url,
                extra_headers=headers,
                ping_interval=30,
                ping_timeout=10
            )
            self.is_connected = True
            logger.info("WebSocket connected successfully")
            
            # 启动消息处理任务
            asyncio.create_task(self._process_messages())
            
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            raise
    
    async def _process_messages(self):
        """处理接收到的消息"""
        try:
            while self.is_connected and self.websocket:
                message = await self.websocket.recv()
                await self._handle_message(message)
        except websockets.ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.is_connected = False
            await self._reconnect()
        except Exception as e:
            logger.error(f"Error processing messages: {str(e)}")
            self.is_connected = False
            await self._reconnect()
    
    async def _handle_message(self, message: str):
        """处理单个消息"""
        try:
            data = json.loads(message)
            logger.debug(f"Received message: {data}")
            
            # 处理登录响应
            if "event" in data and data["event"] == "login":
                if data.get("code") == "0":
                    self.is_authenticated = True
                    self.conn_id = data.get("connId")
                    logger.info(f"Login successful, connId: {self.conn_id}")
                else:
                    logger.error(f"Login failed: {data.get('msg')}")
            
            # 处理订阅响应
            elif "event" in data and data["event"] == "subscribe":
                logger.info(f"Subscribe successful: {data.get('arg')}")
            
            # 处理取消订阅响应
            elif "event" in data and data["event"] == "unsubscribe":
                logger.info(f"Unsubscribe successful: {data.get('arg')}")
            
            # 处理服务升级通知
            elif "event" in data and data["event"] == "notice":
                if data.get("code") == "64008":
                    logger.warning(f"Service upgrade notice: {data.get('msg')}")
                    # 可以在这里添加重连逻辑
            
            # 处理订单响应
            elif "op" in data and data["op"] == "order":
                logger.info(f"Order response: {data}")
                # 处理订单响应，记录到数据库
                await self._handle_order_response(data)
            
            # 处理批量订单响应
            elif "op" in data and data["op"] == "batch-orders":
                logger.info(f"Batch order response: {data}")
                # 处理批量订单响应
                await self._handle_batch_order_response(data)
            
            # 处理撤单响应
            elif "op" in data and data["op"] == "cancel-order":
                logger.info(f"Cancel order response: {data}")
                # 处理撤单响应
                await self._handle_cancel_order_response(data)
            
            # 处理批量撤单响应
            elif "op" in data and data["op"] == "batch-cancel-orders":
                logger.info(f"Batch cancel order response: {data}")
                # 处理批量撤单响应
                await self._handle_batch_cancel_order_response(data)
            
            # 处理订阅数据
            elif "data" in data:
                channel = data.get("arg", {}).get("channel")
                if channel and channel in self.message_handlers:
                    await self.message_handlers[channel](data)
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    async def _handle_order_response(self, data: Dict[str, Any]):
        """处理订单响应，记录到数据库"""
        try:
            order_id = data.get("id")
            if not order_id:
                return
            
            # 从订单响应中提取信息
            order_data = data.get("data", [])[0]
            ord_id = order_data.get("ordId")
            ts = order_data.get("ts")
            s_code = order_data.get("sCode")
            s_msg = order_data.get("sMsg")
            
            logger.info(f"Order {ord_id} processed with status: {s_code}")
            
            # 这里可以根据需要记录成交记录
            # 由于OKX的WebSocket响应可能不包含成交明细
            # 实际应用中可能需要通过订阅订单更新来获取成交信息
            
        except Exception as e:
            logger.error(f"Error handling order response: {str(e)}")
    
    async def _handle_batch_order_response(self, data: Dict[str, Any]):
        """处理批量订单响应"""
        try:
            order_id = data.get("id")
            if not order_id:
                return
            
            # 处理每个订单响应
            order_data_list = data.get("data", [])
            for order_data in order_data_list:
                ord_id = order_data.get("ordId")
                ts = order_data.get("ts")
                s_code = order_data.get("sCode")
                s_msg = order_data.get("sMsg")
                
                logger.info(f"Batch order {ord_id} processed with status: {s_code}")
            
        except Exception as e:
            logger.error(f"Error handling batch order response: {str(e)}")
    
    async def _handle_cancel_order_response(self, data: Dict[str, Any]):
        """处理撤单响应"""
        try:
            order_id = data.get("id")
            if not order_id:
                return
            
            # 处理撤单响应
            cancel_data = data.get("data", [])[0]
            ord_id = cancel_data.get("ordId")
            ts = cancel_data.get("ts")
            s_code = cancel_data.get("sCode")
            s_msg = cancel_data.get("sMsg")
            
            logger.info(f"Cancel order {ord_id} processed with status: {s_code}")
            
        except Exception as e:
            logger.error(f"Error handling cancel order response: {str(e)}")
    
    async def _handle_batch_cancel_order_response(self, data: Dict[str, Any]):
        """处理批量撤单响应"""
        try:
            order_id = data.get("id")
            if not order_id:
                return
            
            # 处理每个撤单响应
            cancel_data_list = data.get("data", [])
            for cancel_data in cancel_data_list:
                ord_id = cancel_data.get("ordId")
                ts = cancel_data.get("ts")
                s_code = cancel_data.get("sCode")
                s_msg = cancel_data.get("sMsg")
                
                logger.info(f"Batch cancel order {ord_id} processed with status: {s_code}")
            
        except Exception as e:
            logger.error(f"Error handling batch cancel order response: {str(e)}")
    
    async def login(self, api_key: str, passphrase: str, secret_key: str):
        """登录到OKX WebSocket"""
        if not self.is_connected:
            await self.connect()
        
        timestamp = get_timestamp()
        sign = generate_sign(timestamp, secret_key)
        
        login_request = {
            "op": "login",
            "args": [{
                "apiKey": api_key,
                "passphrase": passphrase,
                "timestamp": timestamp,
                "sign": sign
            }]
        }
        
        await self.send(login_request)
    
    async def subscribe(self, channel: str, inst_id: str):
        """订阅频道"""
        subscribe_request = {
            "op": "subscribe",
            "args": [{
                "channel": channel,
                "instId": inst_id
            }]
        }
        await self.send(subscribe_request)
    
    async def unsubscribe(self, channel: str, inst_id: str):
        """取消订阅"""
        unsubscribe_request = {
            "op": "unsubscribe",
            "args": [{
                "channel": channel,
                "instId": inst_id
            }]
        }
        await self.send(unsubscribe_request)
    
    async def send_order(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """发送订单并记录到数据库"""
        order_id = str(int(time.time() * 1000))
        order_request = {
            "id": order_id,
            "op": "order",
            "args": [order_params]
        }
        
        # 记录订单到数据库
        await self._record_order_to_db(order_params, order_id)
        
        # 发送订单
        await self.send(order_request)
        logger.info(f"Placed order: {order_params}")
        
        return {"order_id": order_id}
    
    async def send_batch_orders(self, order_params_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量发送订单并记录到数据库"""
        order_id = str(int(time.time() * 1000))
        batch_order_request = {
            "id": order_id,
            "op": "batch-orders",
            "args": order_params_list
        }
        
        # 记录每个订单到数据库
        for order_params in order_params_list:
            await self._record_order_to_db(order_params, f"{order_id}_{order_params_list.index(order_params)}")
        
        # 发送批量订单
        await self.send(batch_order_request)
        logger.info(f"Placed batch orders: {order_params_list}")
        
        return {"order_id": order_id}
    
    async def cancel_order(self, cancel_params: Dict[str, Any]) -> Dict[str, Any]:
        """撤单"""
        order_id = str(int(time.time() * 1000))
        cancel_request = {
            "id": order_id,
            "op": "cancel-order",
            "args": [cancel_params]
        }
        
        # 发送撤单请求
        await self.send(cancel_request)
        logger.info(f"Canceled order: {cancel_params}")
        
        return {"order_id": order_id}
    
    async def cancel_batch_orders(self, cancel_params_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量撤单"""
        order_id = str(int(time.time() * 1000))
        batch_cancel_request = {
            "id": order_id,
            "op": "batch-cancel-orders",
            "args": cancel_params_list
        }
        
        # 发送批量撤单请求
        await self.send(batch_cancel_request)
        logger.info(f"Canceled batch orders: {cancel_params_list}")
        
        return {"order_id": order_id}
    
    async def _record_order_to_db(self, order_params: Dict[str, Any], okx_order_id: str):
        """记录订单到数据库"""
        try:
            # 转换OKX订单参数到TradingOrder模型
            order_type_map = {
                "market": OrderTypeEnum.MARKET,
                "limit": OrderTypeEnum.LIMIT,
                "stop": OrderTypeEnum.STOP
            }
            
            order_type = order_type_map.get(order_params.get("ordType"), OrderTypeEnum.MARKET)
            
            # 构建备注信息
            remark = {
                "okx_order_id": okx_order_id,
                "tdMode": order_params.get("tdMode"),
                "clOrdId": order_params.get("clOrdId"),
                "instId": order_params.get("instId")
            }
            
            # 创建订单对象
            order_create = TradingOrderCreate(
                symbol=order_params.get("instId"),
                side=order_params.get("side"),
                order_type=order_type,
                price=order_params.get("px"),
                quantity=float(order_params.get("sz")),
                remark=str(remark)
            )
            
            # 保存到数据库
            db = SessionLocal()
            try:
                db_order = create_trading_order(db, order_create)
                logger.info(f"Order recorded to database: {db_order.id}")
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Error recording order to database: {str(e)}")
    
    async def send(self, message: Dict[str, Any]):
        """发送消息"""
        if not self.is_connected or not self.websocket:
            await self.connect()
        
        try:
            await self.websocket.send(json.dumps(message))
            logger.debug(f"Sent message: {message}")
        except Exception as e:
            logger.error(f"Failed to send message: {str(e)}")
            self.is_connected = False
            await self._reconnect()
    
    async def _reconnect(self):
        """重连逻辑"""
        logger.info(f"Attempting to reconnect in {config.reconnect_interval} seconds")
        await asyncio.sleep(config.reconnect_interval)
        try:
            await self.connect()
        except Exception as e:
            logger.error(f"Reconnect failed: {str(e)}")
            await self._reconnect()
    
    def register_handler(self, channel: str, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[channel] = handler
    
    def register_order_callback(self, order_id: str, callback: Callable):
        """注册订单回调"""
        self.order_callbacks[order_id] = callback
    
    async def close(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
        self.is_connected = False
        self.is_authenticated = False
        logger.info("WebSocket connection closed")
