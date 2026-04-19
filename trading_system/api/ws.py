import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from trading_system.okx.websocket.client import OKXWebSocketClient

logger = logging.getLogger(__name__)


# 全局连接管理器，用于管理所有WebSocket连接
class ConnectionManager:
    """WebSocket连接管理器"""
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.client_connections: dict[WebSocket, OKXWebSocketClient] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.client_connections:
            del self.client_connections[websocket]
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)
    
    def register_client(self, websocket: WebSocket, client: OKXWebSocketClient):
        self.client_connections[websocket] = client
    
    def get_client(self, websocket: WebSocket) -> OKXWebSocketClient:
        return self.client_connections.get(websocket)


# 创建全局连接管理器实例
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket业务端点处理函数"""
    # 接受WebSocket连接
    await manager.connect(websocket)
    
    # 模拟的connId
    conn_id = "a4d3ae55"
    okx_client = None
    
    try:
        # 创建并连接OKX WebSocket客户端
        try:
            # 创建OKX WebSocket客户端实例，使用模拟盘业务频道
            okx_client = OKXWebSocketClient(is_simulated=True, channel_type="business")
            # 注册客户端到连接管理器
            manager.register_client(websocket, okx_client)
            # 连接到OKX WebSocket
            await okx_client.connect()
            # 更新connId
            conn_id = okx_client.conn_id or conn_id
            
            # 注册蜡烛图数据处理函数
            async def handle_candle_data(data):
                # 将OKX推送的蜡烛图数据转发给客户端
                await websocket.send_text(json.dumps(data))
            
            # 注册蜡烛图数据处理器
            okx_client.register_handler("candle1D", handle_candle_data)
            okx_client.register_handler("candle1m", handle_candle_data)
            
            logger.info(f"Connected to OKX WebSocket, connId: {conn_id}")
        except Exception as e:
            logger.warning(f"Failed to connect to OKX WebSocket: {str(e)}")
            logger.info("Using simulated data instead")
        
        # 处理客户端消息
        while True:
            # 接收客户端消息
            data = await websocket.receive_text()
            logger.info(f"Received message: {data}")
            
            try:
                # 解析客户端消息
                message = json.loads(data)
                
                # 处理订阅请求
                if message.get("op") == "subscribe":
                    await handle_subscribe_request(websocket, message, conn_id, okx_client)
                # 处理取消订阅请求
                elif message.get("op") == "unsubscribe":
                    await handle_unsubscribe_request(websocket, message, okx_client)
                else:
                    # 处理其他操作
                    await handle_other_operations(websocket, message)
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")
                # 发送错误响应
                error_response = {
                    "error": "Invalid message format",
                    "message": str(e)
                }
                await websocket.send_text(json.dumps(error_response))
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket connection disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        manager.disconnect(websocket)
    finally:
        # 关闭OKX WebSocket连接
        if okx_client:
            await okx_client.close()


async def handle_subscribe_request(websocket: WebSocket, message: dict, conn_id: str, okx_client: OKXWebSocketClient):
    """处理订阅请求"""
    args = message.get("args", [])
    for arg in args:
        channel = arg.get("channel")
        inst_id = arg.get("instId")
        if channel and inst_id:
            # 尝试订阅OKX蜡烛图数据
            if okx_client and okx_client.is_connected:
                try:
                    await okx_client.subscribe(channel, inst_id)
                except Exception as e:
                    logger.error(f"Error subscribing to {channel}: {str(e)}")
            
            # 返回订阅确认
            response = {
                "id": message.get("id"),
                "event": "subscribe",
                "arg": arg,
                "connId": conn_id
            }
            await websocket.send_text(json.dumps(response))
            logger.info(f"Subscription confirmed: {response}")
            
            # 发送模拟的蜡烛图数据
            if not okx_client or not okx_client.is_connected:
                # 模拟蜡烛图数据
                import time
                simulated_data = {
                    "arg": {
                        "channel": channel,
                        "instId": inst_id
                    },
                    "data": [
                        [
                            str(int(time.time() * 1000)),
                            "42500",
                            "48199.9",
                            "41006.1",
                            "41006.1",
                            "3587.41204591",
                            "166741046.22583129",
                            "166741046.22583129",
                            "0"
                        ]
                    ]
                }
                await websocket.send_text(json.dumps(simulated_data))
                logger.info(f"Sent simulated data: {simulated_data}")


async def handle_unsubscribe_request(websocket: WebSocket, message: dict, okx_client: OKXWebSocketClient):
    """处理取消订阅请求"""
    args = message.get("args", [])
    for arg in args:
        channel = arg.get("channel")
        inst_id = arg.get("instId")
        if channel and inst_id:
            # 尝试取消订阅OKX蜡烛图数据
            if okx_client and okx_client.is_connected:
                try:
                    await okx_client.unsubscribe(channel, inst_id)
                except Exception as e:
                    logger.error(f"Error unsubscribing from {channel}: {str(e)}")
            
            # 返回取消订阅确认
            response = {
                "id": message.get("id"),
                "event": "unsubscribe",
                "arg": arg
            }
            await websocket.send_text(json.dumps(response))
            logger.info(f"Unsubscription confirmed: {response}")


async def handle_other_operations(websocket: WebSocket, message: dict):
    """处理其他操作"""
    # 这里可以添加其他操作的处理逻辑
    response = {
        "id": message.get("id"),
        "error": "Operation not supported",
        "message": f"Operation {message.get('op')} is not supported"
    }
    await websocket.send_text(json.dumps(response))
    logger.warning(f"Unsupported operation: {message.get('op')}")
