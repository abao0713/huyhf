import log_config
from sqlalchemy.orm import Session
from trading_system.models import TradingOrder, TradeRecord, Position
from trading_system.core.schemas import TradingOrderCreate, TradingOrderUpdate, TradeRecordCreate, PositionCreate, PositionUpdate
from typing import Optional, List
from log_config import logger


def create_trading_order(db: Session, order: TradingOrderCreate) -> TradingOrder:
    logger.debug(f"Creating trading order for {order.symbol}, side: {order.side}")
    db_order = TradingOrder(**order.model_dump())
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    logger.info(f"Trading order created: ID {db_order.id}")
    return db_order


def get_trading_order(db: Session, order_id: int) -> Optional[TradingOrder]:
    """获取单个交易订单"""
    return db.query(TradingOrder).filter(TradingOrder.id == order_id).first()


def get_trading_orders(
    db: Session, 
    skip: int = 0, 
    limit: int = 100, 
    symbol: Optional[str] = None
) -> List[TradingOrder]:
    """获取交易订单列表"""
    query = db.query(TradingOrder)
    if symbol:
        query = query.filter(TradingOrder.symbol == symbol)
    return query.offset(skip).limit(limit).all()


def update_trading_order(db: Session, order_id: int, order_update: TradingOrderUpdate) -> Optional[TradingOrder]:
    db_order = get_trading_order(db, order_id)
    if not db_order:
        return None
    for key, value in order_update.model_dump(exclude_unset=True).items():
        setattr(db_order, key, value)
    db.commit()
    db.refresh(db_order)
    return db_order


def create_trade_record(db: Session, trade: TradeRecordCreate) -> TradeRecord:
    logger.debug(f"Creating trade record for order {trade.order_id}, symbol: {trade.symbol}")
    db_trade = TradeRecord(**trade.model_dump())
    db.add(db_trade)
    db.commit()
    db.refresh(db_trade)
    logger.info(f"Trade record created: ID {db_trade.id}")
    return db_trade


def get_trade_record(db: Session, trade_id: int) -> Optional[TradeRecord]:
    return db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()


def get_trade_records(db: Session, skip: int = 0, limit: int = 100, 
                      symbol: Optional[str] = None, order_id: Optional[int] = None) -> List[TradeRecord]:
    query = db.query(TradeRecord)
    if symbol:
        query = query.filter(TradeRecord.symbol == symbol)
    if order_id:
        query = query.filter(TradeRecord.order_id == order_id)
    return query.offset(skip).limit(limit).all()


def create_position(db: Session, position: PositionCreate) -> Position:
    db_position = Position(**position.model_dump())
    db.add(db_position)
    db.commit()
    db.refresh(db_position)
    return db_position


def get_position(db: Session, position_id: int) -> Optional[Position]:
    return db.query(Position).filter(Position.id == position_id).first()


def get_position_by_symbol(db: Session, symbol: str) -> Optional[Position]:
    return db.query(Position).filter(Position.symbol == symbol).first()


def get_positions(db: Session, skip: int = 0, limit: int = 100) -> List[Position]:
    return db.query(Position).offset(skip).limit(limit).all()


def update_position(db: Session, position_id: int, position_update: PositionUpdate) -> Optional[Position]:
    db_position = get_position(db, position_id)
    if not db_position:
        return None
    for key, value in position_update.model_dump(exclude_unset=True).items():
        setattr(db_position, key, value)
    db.commit()
    db.refresh(db_position)
    return db_position


def update_position_on_trade(db: Session, symbol: str, side: str, price: float, quantity: float, fee: float) -> Optional[Position]:
    position = get_position_by_symbol(db, symbol)
    if not position:
        if side == "buy":
            position = Position(
                symbol=symbol,
                quantity=quantity,
                avg_cost=price,
                total_fee=fee
            )
            db.add(position)
        else:
            return None
    else:
        if side == "buy":
            old_quantity = position.quantity
            old_cost = position.avg_cost
            new_quantity = old_quantity + quantity
            if new_quantity > 0:
                new_avg_cost = (old_quantity * old_cost + quantity * price) / new_quantity
                position.avg_cost = new_avg_cost
            position.quantity = new_quantity
            position.total_fee += fee
        elif side == "sell":
            if position.quantity >= quantity:
                position.quantity -= quantity
                position.total_fee += fee
                profit = (price - position.avg_cost) * quantity
                position.realized_profit += profit
                if position.quantity == 0:
                    position.avg_cost = 0.0
    db.commit()
    db.refresh(position)
    return position
