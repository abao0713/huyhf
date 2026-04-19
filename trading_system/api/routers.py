import log_config
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from trading_system.core.database import get_db
from trading_system.services import crud
from trading_system.core.schemas import (
    TradingOrderCreate, TradingOrderResponse, TradingOrderUpdate,
    TradeRecordCreate, TradeRecordResponse,
    PositionCreate, PositionResponse, PositionUpdate
)
from trading_system.models.trading_order import OrderStatusEnum
from log_config import logger

router = APIRouter()


@router.post("/orders/", response_model=TradingOrderResponse)
def create_order(order: TradingOrderCreate, db: Session = Depends(get_db)):
    logger.info(f"POST /orders/ - Creating order for {order.symbol}")
    try:
        result = crud.create_trading_order(db=db, order=order)
        logger.info(f"Order created successfully: {result.id}")
        return result
    except Exception as e:
        logger.error(f"Failed to create order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create order")


@router.get("/orders/{order_id}", response_model=TradingOrderResponse)
def get_order(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_trading_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@router.get("/orders/", response_model=List[TradingOrderResponse])
def get_orders(skip: int = 0, limit: int = 100, symbol: Optional[str] = None, db: Session = Depends(get_db)):
    orders = crud.get_trading_orders(db, skip=skip, limit=limit, symbol=symbol)
    return orders


@router.put("/orders/{order_id}", response_model=TradingOrderResponse)
def update_order(order_id: int, order: TradingOrderUpdate, db: Session = Depends(get_db)):
    db_order = crud.update_trading_order(db=db, order_id=order_id, order_update=order)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order


@router.post("/trades/", response_model=TradeRecordResponse)
def create_trade(trade: TradeRecordCreate, db: Session = Depends(get_db)):
    db_trade = crud.create_trade_record(db=db, trade=trade)
    crud.update_position_on_trade(
        db=db, 
        symbol=trade.symbol, 
        side=trade.side, 
        price=trade.price, 
        quantity=trade.quantity, 
        fee=trade.fee
    )
    order = crud.get_trading_order(db, trade.order_id)
    if order:
        order.filled_quantity += trade.quantity
        order.fee += trade.fee
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatusEnum.FILLED
        else:
            order.status = OrderStatusEnum.PARTIAL
        db.commit()
    return db_trade


@router.get("/trades/{trade_id}", response_model=TradeRecordResponse)
def get_trade(trade_id: int, db: Session = Depends(get_db)):
    db_trade = crud.get_trade_record(db, trade_id=trade_id)
    if db_trade is None:
        raise HTTPException(status_code=404, detail="Trade not found")
    return db_trade


@router.get("/trades/", response_model=List[TradeRecordResponse])
def get_trades(skip: int = 0, limit: int = 100, symbol: Optional[str] = None, 
              order_id: Optional[int] = None, db: Session = Depends(get_db)):
    trades = crud.get_trade_records(db, skip=skip, limit=limit, symbol=symbol, order_id=order_id)
    return trades


@router.post("/positions/", response_model=PositionResponse)
def create_position(position: PositionCreate, db: Session = Depends(get_db)):
    return crud.create_position(db=db, position=position)


@router.get("/positions/{position_id}", response_model=PositionResponse)
def get_position(position_id: int, db: Session = Depends(get_db)):
    db_position = crud.get_position(db, position_id=position_id)
    if db_position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position


@router.get("/positions/", response_model=List[PositionResponse])
def get_positions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    positions = crud.get_positions(db, skip=skip, limit=limit)
    return positions


@router.get("/positions/symbol/{symbol}", response_model=PositionResponse)
def get_position_by_symbol(symbol: str, db: Session = Depends(get_db)):
    db_position = crud.get_position_by_symbol(db, symbol=symbol)
    if db_position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position


@router.put("/positions/{position_id}", response_model=PositionResponse)
def update_position(position_id: int, position: PositionUpdate, db: Session = Depends(get_db)):
    db_position = crud.update_position(db=db, position_id=position_id, position_update=position)
    if db_position is None:
        raise HTTPException(status_code=404, detail="Position not found")
    return db_position
