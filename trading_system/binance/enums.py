from enum import Enum


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """订单类型枚举"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class PositionSide(Enum):
    """持仓方向枚举"""
    LONG = "LONG"
    SHORT = "SHORT"


class TimeInForce(Enum):
    """订单有效期枚举"""
    GTC = "GTC"  # Good Till Canceled
    IOC = "IOC"  # Immediate Or Cancel
    FOK = "FOK"  # Fill Or Kill


class OrderStatus(Enum):
    """订单状态枚举"""
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
