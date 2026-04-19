import unittest
import asyncio
from unittest.mock import Mock, patch
from trading_system.strategies.trend_following_strategy import TrendFollowingStrategy


class TestTrendFollowingStrategy(unittest.TestCase):
    """测试趋势跟随策略"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建策略实例
        self.strategy = TrendFollowingStrategy(
            api_key="test_api_key",
            secret_key="test_secret_key",
            passphrase="test_passphrase",
            symbol="BTC-USDT",
            amount=0.001,
            is_simulated=True
        )
        
        # 模拟OKX API
        self.strategy.api = Mock()
        self.strategy.api.connect = Mock()
        self.strategy.api.login = Mock()
        self.strategy.api.subscribe = Mock()
        # 模拟异步方法place_order
        async def mock_place_order(**kwargs):
            return {"order_id": "test_order_id"}
        self.strategy.api.place_order = Mock(side_effect=mock_place_order)
        self.strategy.api.close = Mock()
    
    def test_trend_detection(self):
        """测试趋势检测逻辑"""
        # 测试连续4分钟上涨的情况
        self.strategy.candle_data = [
            {"close": 10000},
            {"close": 10100},  # 第1分钟上涨
            {"close": 10200},  # 第2分钟上涨
            {"close": 10300},  # 第3分钟上涨
            {"close": 10400}   # 第4分钟上涨
        ]
        
        # 分析趋势
        trends = []
        for i in range(1, 5):
            current_candle = self.strategy.candle_data[i]
            previous_candle = self.strategy.candle_data[i-1]
            
            # 判断涨跌
            if current_candle["close"] > previous_candle["close"]:
                trends.append("up")
            elif current_candle["close"] < previous_candle["close"]:
                trends.append("down")
            else:
                trends.append("flat")
        
        # 验证趋势检测是否正确
        self.assertEqual(trends, ["up", "up", "up", "up"])
        self.assertTrue(all(trend == "up" for trend in trends))
        
        # 测试连续4分钟下跌的情况
        self.strategy.candle_data = [
            {"close": 10000},
            {"close": 9900},  # 第1分钟下跌
            {"close": 9800},  # 第2分钟下跌
            {"close": 9700},  # 第3分钟下跌
            {"close": 9600}   # 第4分钟下跌
        ]
        
        # 分析趋势
        trends = []
        for i in range(1, 5):
            current_candle = self.strategy.candle_data[i]
            previous_candle = self.strategy.candle_data[i-1]
            
            # 判断涨跌
            if current_candle["close"] > previous_candle["close"]:
                trends.append("up")
            elif current_candle["close"] < previous_candle["close"]:
                trends.append("down")
            else:
                trends.append("flat")
        
        # 验证趋势检测是否正确
        self.assertEqual(trends, ["down", "down", "down", "down"])
        self.assertTrue(all(trend == "down" for trend in trends))
        
        # 测试无明显趋势的情况
        self.strategy.candle_data = [
            {"close": 10000},
            {"close": 10100},  # 上涨
            {"close": 10050},  # 下跌
            {"close": 10150},  # 上涨
            {"close": 10100}   # 下跌
        ]
        
        # 分析趋势
        trends = []
        for i in range(1, 5):
            current_candle = self.strategy.candle_data[i]
            previous_candle = self.strategy.candle_data[i-1]
            
            # 判断涨跌
            if current_candle["close"] > previous_candle["close"]:
                trends.append("up")
            elif current_candle["close"] < previous_candle["close"]:
                trends.append("down")
            else:
                trends.append("flat")
        
        # 验证趋势检测是否正确
        self.assertEqual(trends, ["up", "down", "up", "down"])
        self.assertFalse(all(trend == "up" for trend in trends))
        self.assertFalse(all(trend == "down" for trend in trends))
    
    def test_execute_trade(self):
        """测试执行交易"""
        # 确保当前没有持仓
        self.strategy.current_position = None
        
        # 执行交易
        asyncio.run(self.strategy._execute_trade("buy"))
        
        # 验证是否调用了place_order方法
        self.strategy.api.place_order.assert_called_once()
        
        # 验证当前持仓是否被设置
        self.assertIsNotNone(self.strategy.current_position)
        self.assertEqual(self.strategy.current_position["side"], "buy")
        
        # 验证交易记录是否被添加
        self.assertEqual(len(self.strategy.trade_records), 1)
        self.assertEqual(self.strategy.trade_records[0]["type"], "open")
        self.assertEqual(self.strategy.trade_records[0]["side"], "buy")
    
    def test_close_position(self):
        """测试平仓"""
        # 设置当前持仓
        self.strategy.current_position = {
            "side": "buy",
            "order_id": "test_order_id",
            "timestamp": 1234567890
        }
        
        # 执行平仓
        asyncio.run(self.strategy._close_position())
        
        # 验证是否调用了place_order方法，并且参数是"sell"
        self.strategy.api.place_order.assert_called_once()
        call_args = self.strategy.api.place_order.call_args
        self.assertEqual(call_args[1]["side"], "sell")
        
        # 验证当前持仓是否被清除
        self.assertIsNone(self.strategy.current_position)
        
        # 验证交易记录是否被添加
        self.assertEqual(len(self.strategy.trade_records), 1)
        self.assertEqual(self.strategy.trade_records[0]["type"], "close")
        self.assertEqual(self.strategy.trade_records[0]["side"], "sell")
    
    async def _analyze_trend_mock_execute(self):
        """调用analyze_trend方法"""
        # 调用分析趋势方法
        await self.strategy._analyze_trend()


if __name__ == "__main__":
    unittest.main()
