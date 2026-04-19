import asyncio
import websockets
import json
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def test_websocket():
    """测试WebSocket蜡烛图数据订阅功能"""
    # 连接到WebSocket端点
    ws_url = "ws://localhost:8002/ws/v5/business"
    logger.info(f"Connecting to {ws_url}")
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info("WebSocket connection established")
            
            # 发送订阅请求
            subscribe_request = {
                "id": "1512",
                "op": "subscribe",
                "args": [{
                    "channel": "candle1D",
                    "instId": "BTC-USDT"
                }]
            }
            
            logger.info(f"Sending subscribe request: {subscribe_request}")
            await websocket.send(json.dumps(subscribe_request))
            
            # 接收订阅确认
            response = await websocket.recv()
            logger.info(f"Received subscribe response: {response}")
            
            # 解析响应
            response_data = json.loads(response)
            assert response_data.get("event") == "subscribe", "Expected subscribe event"
            assert response_data.get("id") == "1512", "Expected id to match"
            assert response_data.get("arg", {}).get("channel") == "candle1D", "Expected candle1D channel"
            assert response_data.get("arg", {}).get("instId") == "BTC-USDT", "Expected BTC-USDT instId"
            
            logger.info("Subscribe response validation passed")
            
            # 接收蜡烛图数据推送
            logger.info("Waiting for candle data...")
            for i in range(5):  # 尝试接收5次数据
                try:
                    data = await asyncio.wait_for(websocket.recv(), timeout=30)
                    logger.info(f"Received candle data: {data}")
                    
                    # 解析数据
                    data_json = json.loads(data)
                    assert "data" in data_json, "Expected data field in response"
                    assert "arg" in data_json, "Expected arg field in response"
                    assert data_json.get("arg", {}).get("channel") == "candle1D", "Expected candle1D channel"
                    assert data_json.get("arg", {}).get("instId") == "BTC-USDT", "Expected BTC-USDT instId"
                    
                    logger.info("Candle data validation passed")
                    break
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout waiting for candle data, attempt {i+1}/5")
                    continue
            
            logger.info("WebSocket test completed successfully")
            
    except Exception as e:
        logger.error(f"WebSocket test failed: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(test_websocket())
