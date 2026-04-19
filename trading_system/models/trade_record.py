from sqlalchemy import Column, Integer, String, Float, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from trading_system.models import Base
from trading_system.models.trading_order import SideEnum


class TradeRecord(Base):
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("trading_orders.id"), nullable=False)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(Enum(SideEnum), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    fee = Column(Float, default=0.0)
    fee_currency = Column(String(10), nullable=True)
    trade_time = Column(DateTime, default=datetime.utcnow)

    order = relationship("TradingOrder", back_populates="trades")
