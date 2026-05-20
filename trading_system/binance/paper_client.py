"""
本地纸交易客户端（Paper Trading）

在本地模拟所有交易操作（余额、持仓、订单、手续费、盈亏），
K线数据从Binance API获取，不向交易所发送任何真实订单。

与 BinanceRestClient 保持完全一致的公开接口，确保
MultiTFFractalStrategyExecutor 无需任何修改即可使用。
"""

import logging
import time
from typing import Any, Dict, List, Optional

from trading_system.binance.client import BinanceRestClient

logger = logging.getLogger(__name__)


class PaperTradingClient:

    def __init__(
        self,
        initial_balance: float = 10000.0,
        commission_rate: float = 0.0004,
        api_key: str = None,
        secret_key: str = None,
        is_simulated: bool = True,
    ):
        self.api_key = api_key
        self.secret_key = secret_key
        self.is_simulated = is_simulated

        self._initial_balance = initial_balance
        self._balance = initial_balance
        self._commission_rate = commission_rate
        self._positions: List[Dict[str, Any]] = []
        self._orders: List[Dict[str, Any]] = []
        self._trades: List[Dict[str, Any]] = []
        self._order_counter = 1000000
        self._current_price: Dict[str, float] = {}
        self._last_kline_price: Dict[str, float] = {}

    async def initialize(self):
        try:
            account = await self._get_kline_client().get_account()
            balance_str = account.get("availableBalance", "0")
            balance = float(balance_str)
            if balance > 0:
                self._balance = balance
                self._initial_balance = balance
                logger.info(f"[Paper] 查询到账户余额: ${balance:,.2f}")
                return
        except Exception as e:
            logger.warning(f"[Paper] 查询余额失败: {e}, 使用默认 $10,000")
        self._balance = 10000.0
        self._initial_balance = 10000.0

    async def get_account(self) -> Dict[str, Any]:
        unrealized = 0.0
        for p in self._positions:
            qty = abs(float(p.get("positionAmt", 0)))
            entry = float(p.get("entryPrice", 0))
            side = p.get("positionSide", "LONG")
            current = self._current_price.get(p.get("symbol", ""), entry)
            if side == "LONG":
                unrealized += (current - entry) * qty
            else:
                unrealized += (entry - current) * qty

        equity = self._balance + unrealized
        return {
            "availableBalance": f"{self._balance:.8f}",
            "totalMarginBalance": f"{equity:.8f}",
            "totalWalletBalance": f"{self._balance:.8f}",
            "totalUnrealizedProfit": f"{unrealized:.8f}",
            "totalCrossUnPnl": f"{unrealized:.8f}",
            "totalInitialMargin": "0",
            "totalMaintMargin": "0",
            "balance": f"{self._balance:.8f}",
        }

    async def place_order(
        self,
        symbol: str,
        side: str,
        position_side: str,
        order_type: str,
        quantity: float,
        price: float = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        fill_price = price or self._resolve_fill_price(symbol)
        if fill_price <= 0:
            return {"error": "无法获取成交价", "msg": "Price unavailable", "code": -1}

        notional = quantity * fill_price
        commission = notional * self._commission_rate

        is_opening = (position_side == "LONG" and side == "BUY") or (position_side == "SHORT" and side == "SELL")

        if is_opening:
            cost = notional + commission
            if self._balance < cost:
                return {"error": "余额不足", "msg": f"Need {cost:.2f}, have {self._balance:.2f}", "code": -1}
            self._balance -= cost

            existing = self._find_position(symbol, position_side)
            if existing:
                old_qty = abs(float(existing["positionAmt"]))
                old_price = float(existing["entryPrice"])
                new_qty = old_qty + quantity
                new_entry = (old_qty * old_price + quantity * fill_price) / new_qty
                existing["positionAmt"] = f"{new_qty:.8f}" if position_side == "LONG" else f"{-new_qty:.8f}"
                existing["entryPrice"] = f"{new_entry:.2f}"
            else:
                self._positions.append({
                    "symbol": symbol,
                    "positionAmt": f"{quantity:.8f}" if position_side == "LONG" else f"{-quantity:.8f}",
                    "positionSide": position_side,
                    "entryPrice": f"{fill_price:.2f}",
                    "unrealizedProfit": "0",
                    "leverage": "20",
                    "markPrice": f"{fill_price:.2f}",
                })
        else:
            existing = self._find_position(symbol, position_side)
            if not existing:
                return {"error": "无可平持仓", "msg": f"No {position_side} position for {symbol}", "code": -1}

            old_qty = abs(float(existing["positionAmt"]))
            old_price = float(existing["entryPrice"])
            old_side = existing["positionSide"]
            close_qty = min(quantity, old_qty)

            if old_side == "LONG":
                pnl = (fill_price - old_price) * close_qty
            else:
                pnl = (old_price - fill_price) * close_qty

            total_commission = notional * self._commission_rate
            net_pnl = pnl - total_commission
            self._balance += notional + net_pnl

            remaining = old_qty - close_qty
            if remaining > 0.0001:
                existing["positionAmt"] = f"{remaining:.8f}" if old_side == "LONG" else f"{-remaining:.8f}"
            else:
                self._positions.remove(existing)

            self._trades.append({
                "symbol": symbol,
                "side": side,
                "position_side": position_side,
                "qty": close_qty,
                "entry_price": old_price,
                "exit_price": fill_price,
                "pnl": net_pnl,
                "commission": total_commission,
                "timestamp": time.time(),
            })

            logger.info(
                f"[Paper] 平仓: {position_side} {close_qty:.4f}@{fill_price:.2f} "
                f"P&L=${net_pnl:+.2f} | 余额=${self._balance:.2f}"
            )

        self._current_price[symbol] = fill_price

        self._order_counter += 1
        order_result = {
            "orderId": self._order_counter,
            "clientOrderId": f"paper_{self._order_counter}",
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "origQty": str(quantity),
            "executedQty": str(quantity),
            "cumQuote": str(notional),
            "avgPrice": str(fill_price),
            "status": "FILLED",
            "timeInForce": time_in_force,
            "msg": "Success",
            "code": 0,
        }
        self._orders.append(order_result)
        return order_result

    async def get_order(
        self,
        symbol: str,
        order_id: int = None,
        orig_client_order_id: str = None,
    ) -> Dict[str, Any]:
        for o in reversed(self._orders):
            if order_id and o.get("orderId") == order_id:
                return o
            if orig_client_order_id and o.get("clientOrderId") == orig_client_order_id:
                return o
        return {}

    async def cancel_order(
        self,
        symbol: str,
        order_id: int = None,
        orig_client_order_id: str = None,
    ) -> Dict[str, Any]:
        return {"msg": "No open orders to cancel (paper trading fills instantly)", "code": 0}

    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        if symbol:
            return [p for p in self._positions if p.get("symbol") == symbol]
        return list(self._positions)

    async def get_exchange_info(self) -> Dict[str, Any]:
        return {"serverTime": int(time.time() * 1000), "timezone": "UTC"}

    async def get_continuous_klines(
        self,
        pair: str = None,
        symbol: str = None,
        contractType: str = "PERPETUAL",
        interval: str = "30m",
        startTime: int = None,
        endTime: int = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        pair = pair or symbol
        if not pair:
            return []

        logger.info(f"[Paper Kline] 获取 {pair} {interval} K线, limit={limit}")
        result = await self._get_kline_client().get_continuous_klines(
            pair=pair,
            contractType=contractType,
            interval=interval,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
        )

        if isinstance(result, list) and result:
            last_candle = result[-1]
            if isinstance(last_candle, list) and len(last_candle) >= 5:
                self._last_kline_price[pair] = float(last_candle[4])
                self._current_price[pair] = float(last_candle[4])

        return result

    async def get_spot_klines(
        self,
        symbol: str = None,
        pair: str = None,
        contractType: str = "PERPETUAL",
        interval: str = "30m",
        startTime: int = None,
        endTime: int = None,
        limit: int = 500,
    ) -> List[List[Any]]:
        symbol = symbol or pair
        if not symbol:
            return []

        result = await self._get_kline_client().get_spot_klines(
            symbol=symbol,
            contractType=contractType,
            interval=interval,
            startTime=startTime,
            endTime=endTime,
            limit=limit,
        )
        return result

    async def close(self):
        self._print_report()

    def _find_position(self, symbol: str, position_side: str) -> Optional[Dict[str, Any]]:
        for p in self._positions:
            if p.get("symbol") == symbol and p.get("positionSide") == position_side:
                return p
        return None

    def _resolve_fill_price(self, symbol: str) -> float:
        if symbol in self._current_price and self._current_price[symbol] > 0:
            return self._current_price[symbol]
        if symbol in self._last_kline_price and self._last_kline_price[symbol] > 0:
            return self._last_kline_price[symbol]
        return 0.0

    def _get_kline_client(self):
        if not hasattr(self, "_kline_client") or self._kline_client is None:
            self._kline_client = BinanceRestClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                is_simulated=self.is_simulated,
            )
        return self._kline_client

    def _print_report(self):
        total_pnl = self._balance - self._initial_balance
        pnl_pct = (total_pnl / self._initial_balance) * 100 if self._initial_balance > 0 else 0

        winning_trades = [t for t in self._trades if t["pnl"] > 0]
        losing_trades = [t for t in self._trades if t["pnl"] <= 0]
        win_rate = (len(winning_trades) / len(self._trades) * 100) if self._trades else 0

        total_commission = sum(t["commission"] for t in self._trades)

        logger.info("=" * 60)
        logger.info("  纸交易结束 — 最终报告")
        logger.info("=" * 60)
        logger.info(f"  初始资金:       ${self._initial_balance:,.2f}")
        logger.info(f"  最终余额:       ${self._balance:,.2f}")
        logger.info(f"  总盈亏:         ${total_pnl:+,.2f}  ({pnl_pct:+.2f}%)")
        logger.info(f"  手续费合计:     ${total_commission:,.2f}")
        logger.info(f"  交易次数:       {len(self._trades)}")
        logger.info(f"  盈利次数:       {len(winning_trades)}")
        logger.info(f"  亏损次数:       {len(losing_trades)}")
        logger.info(f"  胜率:           {win_rate:.2f}%")
        if winning_trades:
            logger.info(f"  平均盈利:       ${sum(t['pnl'] for t in winning_trades)/len(winning_trades):+,.2f}")
        if losing_trades:
            logger.info(f"  平均亏损:       ${sum(t['pnl'] for t in losing_trades)/len(losing_trades):+,.2f}")
        if self._trades:
            avg_pnl = total_pnl / len(self._trades)
            logger.info(f"  平均每笔盈亏:   ${avg_pnl:+,.2f}")
        logger.info("=" * 60)