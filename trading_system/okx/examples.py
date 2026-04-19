"""OKX API使用示例"""
import log_config
from trading_system.okx.api import OKXAPI, OKXSyncAPI
import asyncio
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)


async def async_example():
    """异步API使用示例"""
    print("=== 异步API示例 ===")
    
    # 初始化API (使用模拟盘)
    api = OKXAPI(
        api_key="your_api_key",
        secret_key="your_secret_key",
        passphrase="your_passphrase",
        is_simulated=True
    )
    
    try:
        # 连接到服务器
        await api.connect()
        print("Connected to OKX WebSocket")
        
        # 登录
        await api.login()
        print("Logged in successfully")
        
        # 定义回调函数
        async def ticker_callback(data):
            print(f"Received ticker data: {data['data'][0]['last']}")
        
        # 订阅tickers频道
        await api.subscribe("tickers", "BTC-USDT", ticker_callback)
        print("Subscribed to tickers channel")
        
        # 等待一段时间接收数据
        await asyncio.sleep(5)
        
        # 下单示例
        print("Placing order...")
        order_result = await api.place_order(
            side="buy",
            instId="BTC-USDT",
            tdMode="cash",
            ordType="market",
            sz="0.001"
        )
        print(f"Order placed successfully, order_id: {order_result['order_id']}")
        
        # 批量下单示例
        print("\nPlacing batch orders...")
        batch_order_result = await api.place_batch_orders([
            {
                "side": "buy",
                "instId": "BTC-USDT",
                "tdMode": "cash",
                "ordType": "market",
                "sz": "0.001"
            },
            {
                "side": "buy",
                "instId": "ETH-USDT",
                "tdMode": "cash",
                "ordType": "market",
                "sz": "0.01"
            }
        ])
        print(f"Batch orders placed successfully, order_id: {batch_order_result['order_id']}")
        
        # 等待一段时间
        await asyncio.sleep(5)
        
        # 订单查询示例
        print("\nQuerying order...")
        try:
            # 这里使用示例订单ID，实际使用时需要替换为真实的订单ID
            order_result = await api.get_order(
                ord_id="1753197687182819328",
                inst_id="BTC-USDT"
            )
            print(f"Order query result: {order_result}")
        except Exception as e:
            print(f"Order query failed: {str(e)}")
        
        # 取消订阅
        await api.unsubscribe("tickers", "BTC-USDT")
        print("Unsubscribed from tickers channel")
        
    finally:
        # 关闭连接
        await api.close()
        print("Connection closed")


def sync_example():
    """同步API使用示例"""
    print("\n=== 同步API示例 ===")
    
    # 初始化API (使用模拟盘)
    api = OKXSyncAPI(
        api_key="your_api_key",
        secret_key="your_secret_key",
        passphrase="your_passphrase",
        is_simulated=True
    )
    
    try:
        # 连接到服务器
        api.connect()
        print("Connected to OKX WebSocket")
        
        # 登录
        api.login()
        print("Logged in successfully")
        
        # 下单示例
        print("Placing order...")
        order_result = api.place_order(
            side="buy",
            instId="BTC-USDT",
            tdMode="cash",
            ordType="market",
            sz="0.001"
        )
        print(f"Order placed successfully, order_id: {order_result['order_id']}")
        
        # 批量下单示例
        print("\nPlacing batch orders...")
        batch_order_result = api.place_batch_orders([
            {
                "side": "buy",
                "instId": "BTC-USDT",
                "tdMode": "cash",
                "ordType": "market",
                "sz": "0.001"
            },
            {
                "side": "buy",
                "instId": "ETH-USDT",
                "tdMode": "cash",
                "ordType": "market",
                "sz": "0.01"
            }
        ])
        print(f"Batch orders placed successfully, order_id: {batch_order_result['order_id']}")
        
        # 等待一段时间
        import time
        time.sleep(5)
        
        # 订单查询示例
        print("\nQuerying order...")
        try:
            # 这里使用示例订单ID，实际使用时需要替换为真实的订单ID
            order_result = api.get_order(
                ord_id="1753197687182819328",
                inst_id="BTC-USDT"
            )
            print(f"Order query result: {order_result}")
        except Exception as e:
            print(f"Order query failed: {str(e)}")
        
    finally:
        # 关闭连接
        api.close()
        print("Connection closed")


if __name__ == "__main__":
    # 运行异步示例
    asyncio.run(async_example())
    
    # 运行同步示例
    sync_example()
