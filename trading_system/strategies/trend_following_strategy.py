import asyncio
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from trading_system.okx.api import OKXAPI

logger = logging.getLogger(__name__)


class TrendFollowingStrategy:
    """基于连续4分钟涨跌情况的趋势跟随策略"""
    
    def __init__(self, api_key: str, secret_key: str, passphrase: str, 
                 symbol: str = "BTC-USDT", amount: float = 0.001, 
                 is_simulated: bool = True):
        """
        初始化策略
        :param api_key: OKX API Key
        :param secret_key: OKX Secret Key
        :param passphrase: OKX Passphrase
        :param symbol: 交易品种，默认为BTC-USDT
        :param amount: 交易金额，默认为0.001
        :param is_simulated: 是否使用模拟盘，默认为True
        """
        self.api_key = api_key
        self.secret_key = secret_key
        self.passphrase = passphrase
        self.symbol = symbol
        self.amount = amount
        self.is_simulated = is_simulated
        
        # 初始化OKX API
        self.api = OKXAPI(
            api_key=api_key,
            secret_key=secret_key,
            passphrase=passphrase,
            is_simulated=is_simulated
        )
        
        # 存储1分钟K线数据
        self.candle_data: List[Dict[str, Any]] = []
        
        # 存储当前持仓
        self.current_position = None
        
        # 存储交易记录
        self.trade_records = []
        
        # 策略运行状态
        self.is_running = False
        
    async def start(self):
        """启动策略"""
        try:
            # 连接到OKX WebSocket
            await self.api.connect()
            logger.info("Connected to OKX WebSocket")
            
            # 登录
            await self.api.login()
            logger.info("Logged in to OKX")
            
            # 订阅1分钟K线数据
            await self.api.subscribe("candle1m", self.symbol, self._handle_candle_data)
            logger.info(f"Subscribed to 1m candle data for {self.symbol}")
            
            # 设置策略运行状态
            self.is_running = True
            logger.info("Strategy started")
            
            # 持续运行
            while self.is_running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error starting strategy: {str(e)}")
            raise
    
    async def stop(self):
        """停止策略"""
        try:
            # 设置策略运行状态
            self.is_running = False
            
            # 关闭OKX API连接
            await self.api.close()
            logger.info("Strategy stopped")
            
        except Exception as e:
            logger.error(f"Error stopping strategy: {str(e)}")
            raise
    
    async def _handle_candle_data(self, data: Dict[str, Any]):
        """处理1分钟K线数据"""
        try:
            # 提取K线数据
            candle = data.get("data", [])[0]
            timestamp = int(candle[0])
            open_price = float(candle[1])
            high_price = float(candle[2])
            low_price = float(candle[3])
            close_price = float(candle[4])
            volume = float(candle[5])
            
            # 构造K线数据字典
            candle_dict = {
                "timestamp": timestamp,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume
            }
            
            # 添加到K线数据列表
            self.candle_data.append(candle_dict)
            
            # 只保留最近5分钟的K线数据
            if len(self.candle_data) > 5:
                self.candle_data = self.candle_data[-5:]
            
            logger.debug(f"Received candle data: {candle_dict}")
            
            # 分析趋势并执行交易
            await self._analyze_trend()
            
        except Exception as e:
            logger.error(f"Error handling candle data: {str(e)}")
    
    async def _analyze_trend(self):
        """分析趋势并执行交易"""
        try:
            # 确保有足够的K线数据
            if len(self.candle_data) < 5:
                return
            
            # 分析连续4分钟的涨跌情况
            trends = []
            for i in range(1, 5):
                current_candle = self.candle_data[i]
                previous_candle = self.candle_data[i-1]
                
                # 判断涨跌
                if current_candle["close"] > previous_candle["close"]:
                    trends.append("up")
                elif current_candle["close"] < previous_candle["close"]:
                    trends.append("down")
                else:
                    trends.append("flat")
            
            logger.debug(f"Trends: {trends}")
            
            # 检查是否连续4分钟上涨
            if all(trend == "up" for trend in trends):
                logger.info("Detected 4 consecutive up minutes, preparing to buy")
                # 在第五分钟开始时做多
                await self._execute_trade("buy")
            
            # 检查是否连续4分钟下跌
            elif all(trend == "down" for trend in trends):
                logger.info("Detected 4 consecutive down minutes, preparing to sell")
                # 在第五分钟开始时做空
                await self._execute_trade("sell")
            
            # 检查是否需要平仓（第五分钟结束时）
            current_time = datetime.now()
            if current_time.second == 0 and self.current_position is not None:
                logger.info("End of 5th minute, preparing to close position")
                # 平仓
                await self._close_position()
                
        except Exception as e:
            logger.error(f"Error analyzing trend: {str(e)}")
    
    async def _execute_trade(self, side: str):
        """执行交易"""
        try:
            # 检查是否已经有持仓
            if self.current_position is not None:
                logger.info("Already have an open position, skipping trade")
                return
            
            # 执行交易
            order_result = await self.api.place_order(
                side=side,
                instId=self.symbol,
                tdMode="cash",
                ordType="market",
                sz=str(self.amount)
            )
            
            # 记录持仓
            self.current_position = {
                "side": side,
                "order_id": order_result.get("order_id"),
                "timestamp": time.time()
            }
            
            # 记录交易
            trade_record = {
                "type": "open",
                "side": side,
                "symbol": self.symbol,
                "amount": self.amount,
                "order_id": order_result.get("order_id"),
                "timestamp": time.time()
            }
            self.trade_records.append(trade_record)
            
            logger.info(f"Executed {side} trade: {trade_record}")
            
        except Exception as e:
            logger.error(f"Error executing trade: {str(e)}")
    
    async def _close_position(self):
        """平仓"""
        try:
            # 检查是否有持仓
            if self.current_position is None:
                logger.info("No open position to close")
                return
            
            # 确定平仓方向
            if self.current_position["side"] == "buy":
                close_side = "sell"
            else:
                close_side = "buy"
            
            # 执行平仓
            order_result = await self.api.place_order(
                side=close_side,
                instId=self.symbol,
                tdMode="cash",
                ordType="market",
                sz=str(self.amount)
            )
            
            # 记录交易
            trade_record = {
                "type": "close",
                "side": close_side,
                "symbol": self.symbol,
                "amount": self.amount,
                "order_id": order_result.get("order_id"),
                "timestamp": time.time()
            }
            self.trade_records.append(trade_record)
            
            logger.info(f"Closed position: {trade_record}")
            
            # 清除持仓
            self.current_position = None
            
        except Exception as e:
            logger.error(f"Error closing position: {str(e)}")
    
    def get_trade_records(self) -> List[Dict[str, Any]]:
        """获取交易记录"""
        return self.trade_records
    
    def get_current_position(self) -> Optional[Dict[str, Any]]:
        """获取当前持仓"""
        return self.current_position
    

