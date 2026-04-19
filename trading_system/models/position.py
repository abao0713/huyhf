from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from trading_system.models import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    quantity = Column(Float, default=0.0)
    avg_cost = Column(Float, default=0.0)
    realized_profit = Column(Float, default=0.0)
    unrealized_profit = Column(Float, default=0.0)
    total_fee = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
