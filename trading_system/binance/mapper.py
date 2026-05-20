import logging
from datetime import datetime
from typing import Dict, Any, Optional
from trading_system.models.trading_order import TradingOrder, OrderStatusEnum, OrderTypeEnum, SideEnum

logger = logging.getLogger(__name__)


class PositionSideEnum:
    """持仓方向枚举"""
    LONG = "long"
    SHORT = "short"


class BinanceMapper:
    """Binance数据映射器"""

    @staticmethod
    def map_order_status(status: str) -> OrderStatusEnum:
        """映射订单状态
        :param status: Binance订单状态
        :return: 映射后的状态枚举
        """
        status_mapping = {
            "NEW": OrderStatusEnum.PENDING,
            "PARTIALLY_FILLED": OrderStatusEnum.PARTIAL,
            "FILLED": OrderStatusEnum.FILLED,
            "CANCELED": OrderStatusEnum.CANCELLED,
            "REJECTED": OrderStatusEnum.CANCELLED,
            "EXPIRED": OrderStatusEnum.CANCELLED
        }
        return status_mapping.get(status.upper(), OrderStatusEnum.PENDING)

    @staticmethod
    def map_order_type(order_type: str) -> OrderTypeEnum:
        """映射订单类型
        :param order_type: Binance订单类型
        :return: 映射后的类型枚举
        """
        type_mapping = {
            "LIMIT": OrderTypeEnum.LIMIT,
            "MARKET": OrderTypeEnum.MARKET,
            "STOP": OrderTypeEnum.STOP,
            "STOP_MARKET": OrderTypeEnum.STOP,
            "TAKE_PROFIT": OrderTypeEnum.STOP,
            "TAKE_PROFIT_MARKET": OrderTypeEnum.STOP
        }
        return type_mapping.get(order_type.upper(), OrderTypeEnum.LIMIT)

    @staticmethod
    def map_order_side(side: str) -> SideEnum:
        """映射订单方向
        :param side: Binance订单方向
        :return: 映射后的方向枚举
        """
        side_mapping = {
            "BUY": SideEnum.BUY,
            "SELL": SideEnum.SELL
        }
        return side_mapping.get(side.upper(), SideEnum.BUY)

    @staticmethod
    def map_binance_order_to_trading_order(binance_order: Dict[str, Any]) -> TradingOrder:
        """将Binance订单映射到TradingOrder
        :param binance_order: Binance订单数据
        :return: TradingOrder模型
        """
        try:
            order = TradingOrder()
            order.order_id = binance_order.get("orderId")
            order.symbol = binance_order.get("symbol")
            order.side = BinanceMapper.map_order_side(binance_order.get("side", ""))
            order.order_type = BinanceMapper.map_order_type(binance_order.get("type", ""))
            order.price = float(binance_order.get("price", 0)) if binance_order.get("price") else None
            order.quantity = float(binance_order.get("origQty", 0))
            order.filled_quantity = float(binance_order.get("executedQty", 0))
            order.status = BinanceMapper.map_order_status(binance_order.get("status", ""))

            if binance_order.get("updateTime"):
                order.updated_at = datetime.fromtimestamp(binance_order["updateTime"] / 1000)

            order.remark = f"clOrdId={binance_order.get('clientOrderId', '')}, orderId={binance_order.get('orderId', '')}"

            logger.info(f"[BinanceMapper] Mapped order: {order.order_id}, symbol={order.symbol}, status={order.status}")
            return order

        except Exception as e:
            logger.error(f"[BinanceMapper] Failed to map order: {str(e)}")
            raise

    @staticmethod
    def map_trading_order_to_binance_params(order: TradingOrder) -> Dict[str, Any]:
        """将TradingOrder映射到Binance下单参数
        :param order: TradingOrder模型
        :return: Binance API参数
        """
        params = {
            "symbol": order.symbol,
            "side": order.side.value.upper() if hasattr(order.side, 'value') else order.side.upper(),
            "positionSide": "LONG" if order.side == SideEnum.BUY else "SHORT",
            "type": order.order_type.value.upper() if hasattr(order.order_type, 'value') else order.order_type.upper(),
            "quantity": order.quantity
        }

        if order.price:
            params["price"] = order.price
            params["timeInForce"] = "GTC"

        return params
