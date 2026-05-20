import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from trading_system.core.database import SessionLocal
from trading_system.models.trading_order import TradingOrder, OrderStatusEnum
from trading_system.models.trade_record import TradeRecord
from trading_system.models.position import Position
from .mapper import BinanceMapper

logger = logging.getLogger(__name__)


class BinanceDatabaseAdapter:
    """Binance数据库适配器"""

    def __init__(self):
        self.db: Session = None

    def __enter__(self):
        self.db = SessionLocal()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            if exc_type is not None:
                self.db.rollback()
                logger.error(f"[BinanceDatabaseAdapter] Transaction rolled back: {exc_val}")
            self.db.close()

    def save_order(self, binance_order: Dict[str, Any]) -> Optional[TradingOrder]:
        """保存订单到数据库
        :param binance_order: Binance订单数据
        :return: 保存的订单对象
        """
        try:
            order = BinanceMapper.map_binance_order_to_trading_order(binance_order)

            existing_order = self.db.query(TradingOrder).filter(
                TradingOrder.order_id == order.order_id
            ).first()

            if existing_order:
                existing_order.status = order.status
                existing_order.filled_quantity = order.filled_quantity
                existing_order.updated_at = datetime.utcnow()
                existing_order.remark = order.remark
                self.db.commit()
                logger.info(f"[BinanceDatabaseAdapter] Updated order: {order.order_id}")
                return existing_order
            else:
                self.db.add(order)
                self.db.commit()
                self.db.refresh(order)
                logger.info(f"[BinanceDatabaseAdapter] Saved new order: {order.order_id}")
                return order

        except Exception as e:
            self.db.rollback()
            logger.error(f"[BinanceDatabaseAdapter] Failed to save order: {str(e)}")
            return None

    def get_order_by_id(self, order_id: int) -> Optional[TradingOrder]:
        """根据订单ID查询订单
        :param order_id: 订单ID
        :return: 订单对象
        """
        try:
            return self.db.query(TradingOrder).filter(
                TradingOrder.order_id == order_id
            ).first()
        except Exception as e:
            logger.error(f"[BinanceDatabaseAdapter] Failed to get order: {str(e)}")
            return None

    def update_order_status(self, order_id: int, status: OrderStatusEnum, filled_quantity: float = None) -> bool:
        """更新订单状态
        :param order_id: 订单ID
        :param status: 新状态
        :param filled_quantity: 已成交数量
        :return: 是否成功
        """
        try:
            order = self.get_order_by_id(order_id)
            if order:
                order.status = status
                if filled_quantity is not None:
                    order.filled_quantity = filled_quantity
                order.updated_at = datetime.utcnow()
                self.db.commit()
                logger.info(f"[BinanceDatabaseAdapter] Updated order status: {order_id} -> {status}")
                return True
            return False
        except Exception as e:
            self.db.rollback()
            logger.error(f"[BinanceDatabaseAdapter] Failed to update order status: {str(e)}")
            return False

    def save_trade_record(self, binance_trade: Dict[str, Any], order_id: int) -> Optional[TradeRecord]:
        """保存成交记录
        :param binance_trade: Binance成交数据
        :param order_id: 订单ID
        :return: 成交记录对象
        """
        try:
            trade = TradeRecord()
            trade.order_id = order_id
            trade.trade_id = binance_trade.get("tradeId")
            trade.symbol = binance_trade.get("symbol")
            trade.price = float(binance_trade.get("price", 0))
            trade.quantity = float(binance_trade.get("qty", 0))
            trade.side = binance_trade.get("side", "")
            trade.fee = float(binance_trade.get("commission", 0))
            trade.trade_time = datetime.fromtimestamp(binance_trade.get("time", 0) / 1000)

            self.db.add(trade)
            self.db.commit()
            self.db.refresh(trade)

            logger.info(f"[BinanceDatabaseAdapter] Saved trade record: {trade.trade_id}")
            return trade

        except Exception as e:
            self.db.rollback()
            logger.error(f"[BinanceDatabaseAdapter] Failed to save trade record: {str(e)}")
            return None

    def update_position(self, symbol: str, side: str, quantity: float, entry_price: float) -> bool:
        """更新持仓
        :param symbol: 交易对
        :param side: 方向
        :param quantity: 数量
        :param entry_price: 开仓价格
        :return: 是否成功
        """
        try:
            position = self.db.query(Position).filter(
                Position.symbol == symbol,
                Position.side == side
            ).first()

            if position:
                position.quantity = quantity
                position.entry_price = entry_price
                position.updated_at = datetime.utcnow()
            else:
                position = Position()
                position.symbol = symbol
                position.side = side
                position.quantity = quantity
                position.entry_price = entry_price
                self.db.add(position)

            self.db.commit()
            logger.info(f"[BinanceDatabaseAdapter] Updated position: {symbol} {side} {quantity}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"[BinanceDatabaseAdapter] Failed to update position: {str(e)}")
            return False

    def get_position(self, symbol: str, side: str) -> Optional[Position]:
        """获取持仓
        :param symbol: 交易对
        :param side: 方向
        :return: 持仓对象
        """
        try:
            return self.db.query(Position).filter(
                Position.symbol == symbol,
                Position.side == side
            ).first()
        except Exception as e:
            logger.error(f"[BinanceDatabaseAdapter] Failed to get position: {str(e)}")
            return None

    def get_all_positions(self) -> list:
        """获取所有持仓
        :return: 持仓列表
        """
        try:
            return self.db.query(Position).filter(
                Position.quantity > 0
            ).all()
        except Exception as e:
            logger.error(f"[BinanceDatabaseAdapter] Failed to get all positions: {str(e)}")
            return []
