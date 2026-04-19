from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from trading_system.models.trading_order import OrderTypeEnum, SideEnum, OrderStatusEnum


class TradingOrderBase(BaseModel):
    symbol: str
    side: SideEnum
    order_type: OrderTypeEnum
    price: Optional[float] = None
    quantity: float
    remark: Optional[str] = None


class TradingOrderCreate(TradingOrderBase):
    pass


class TradingOrderUpdate(BaseModel):
    status: Optional[OrderStatusEnum] = None
    filled_quantity: Optional[float] = None
    fee: Optional[float] = None


class TradingOrderResponse(TradingOrderBase):
    id: int
    filled_quantity: float
    status: OrderStatusEnum
    fee: float
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TradeRecordBase(BaseModel):
    order_id: int
    symbol: str
    side: SideEnum
    price: float
    quantity: float
    fee: float = 0.0
    fee_currency: Optional[str] = None


class TradeRecordCreate(TradeRecordBase):
    pass


class TradeRecordResponse(TradeRecordBase):
    id: int
    trade_time: datetime

    class Config:
        from_attributes = True


class PositionBase(BaseModel):
    symbol: str
    quantity: float = 0.0
    avg_cost: float = 0.0
    realized_profit: float = 0.0
    unrealized_profit: float = 0.0
    total_fee: float = 0.0


class PositionCreate(PositionBase):
    pass


class PositionUpdate(BaseModel):
    quantity: Optional[float] = None
    avg_cost: Optional[float] = None
    realized_profit: Optional[float] = None
    unrealized_profit: Optional[float] = None
    total_fee: Optional[float] = None


class PositionResponse(PositionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
