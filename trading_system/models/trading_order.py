from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from trading_system.models import Base
import enum


class OrderTypeEnum(enum.Enum):
    MARKET = "1"
    LIMIT = "2"
    STOP = "3"


class SideEnum(enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatusEnum(enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


class TradingOrder(Base):
    __tablename__ = "trading_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(SideEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    order_type = Column(Enum(OrderTypeEnum, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    filled_quantity = Column(Float, default=0.0)
    status = Column(Enum(OrderStatusEnum, values_callable=lambda obj: [e.value for e in obj]), default=OrderStatusEnum.PENDING)
    fee = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    remark = Column(Text, nullable=True)

    trades = relationship("TradeRecord", back_populates="order")
