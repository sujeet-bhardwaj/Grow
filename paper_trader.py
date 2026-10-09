"""
Paper Trading Virtual Portfolio Simulator for NIFTY 10–15 Point Scalping
Tracks simulated scalp option orders, lots, premiums, stop loss, targets,
trailing stop to breakeven, index point capture, and P&L ledger.
"""

import time
from datetime import datetime
import config


class PaperTrader:
    def __init__(self, starting_capital: float = config.INITIAL_PAPER_CAPITAL):
        self.starting_capital = starting_capital
        self.cash_balance = starting_capital
        self.open_positions = {}  # contract_symbol -> position dict
        self.trade_history = []
        self.realized_pnl = 0.0
        self.consecutive_losses = 0
        self.last_loss_timestamp = 0.0

    def open_trade(
        self,
        contract_symbol: str,
        underlying: str,
        strike: int,
        option_type: str,
        lots: int,
        quantity: int,
        premium: float,
        sl_premium: float,
        tp_premium: float,
        entry_spot: float = 0.0,
        target_index_pts: float = 12.5,
        sl_index_pts: float = 6.0,
        breakeven_trigger: float = 0.0,
        confluence_score: int = 0
    ) -> bool:
        """Simulates opening a new NIFTY 10–15 Point Scalp Option position."""
        cost = quantity * premium
        if cost > self.cash_balance:
            print(f"[SCALP BROKER] Insufficient funds: Required Rs. {cost:,.2f}, Available Rs. {self.cash_balance:,.2f}")
            return False

        self.cash_balance -= cost
        be_trig = breakeven_trigger if breakeven_trigger > 0 else round(premium + 3.6, 2)

        self.open_positions[contract_symbol] = {
            "symbol": contract_symbol,
            "underlying": underlying,
            "strike": strike,
            "option_type": option_type,
            "lots": lots,
            "quantity": quantity,
            "entry_price": premium,
            "current_price": premium,
            "stop_loss_price": sl_premium,
            "target_price": tp_premium,
            "entry_spot": entry_spot,
            "target_index_pts": target_index_pts,
            "sl_index_pts": sl_index_pts,
            "breakeven_trigger": be_trig,
            "is_trailed_to_be": False,
            "confluence_score": confluence_score,
            "entry_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "entry_timestamp": time.time()
        }

        print(f"\n[SCALP ORDER FILLED] BUY {lots} Lots ({quantity} Qty) of {contract_symbol} @ Rs. {premium:.2f}")
        print(f"  -> Scalp Target: Rs. {tp_premium:.2f} (+{target_index_pts} Index Pts) | SL: Rs. {sl_premium:.2f} (-{sl_index_pts} Pts)")
        print(f"  -> Trailing BE Trigger @ Rs. {be_trig:.2f} | Remaining Cash: Rs. {self.cash_balance:,.2f}\n")
        return True

    def close_trade(self, contract_symbol: str, exit_premium: float, exit_reason: str) -> dict:
        """Simulates closing an open scalping position and records P&L and point metrics."""
        if contract_symbol not in self.open_positions:
            return {}

        pos = self.open_positions.pop(contract_symbol)
        qty = pos["quantity"]
        entry_premium = pos["entry_price"]

        trade_pnl = (exit_premium - entry_premium) * qty
        pnl_pct = ((exit_premium - entry_premium) / entry_premium) * 100 if entry_premium > 0 else 0.0
        delta = getattr(config, "ESTIMATED_ATM_DELTA", 0.52)
        captured_pts = round((exit_premium - entry_premium), 2)
        idx_captured_pts = round(captured_pts / delta, 1)

        # Return capital to cash balance
        return_capital = (qty * entry_premium) + trade_pnl
        self.cash_balance += max(return_capital, 0.0)
        self.realized_pnl += trade_pnl

        # Track consecutive loss streak (Point 10 Rule)
        if trade_pnl < 0:
            self.consecutive_losses += 1
            self.last_loss_timestamp = time.time()
        else:
            self.consecutive_losses = 0

        record = {
            "symbol": pos["symbol"],
            "underlying": pos.get("underlying", ""),
            "lots": pos.get("lots", 1),
            "quantity": qty,
            "entry_price": entry_premium,
            "exit_price": exit_premium,
            "captured_option_pts": captured_pts,
            "captured_index_pts": idx_captured_pts,
            "pnl": round(trade_pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
            "entry_time": pos["entry_time"],
            "exit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exit_reason": exit_reason
        }
        self.trade_history.append(record)

        color_tag = "PROFIT" if trade_pnl >= 0 else "LOSS"
        print(f"\n[SCALP POSITION CLOSED] {pos['symbol']} @ Rs. {exit_premium:.2f} ({exit_reason})")
        print(f"  -> Points: {captured_pts:+} Option pts (~{idx_captured_pts:+} Index pts)")
        print(f"  -> Result: {color_tag} Rs. {trade_pnl:+,.2f} ({pnl_pct:+.2f}%) | Total Realized PnL: Rs. {self.realized_pnl:+,.2f}\n")

        return record

    def update_unrealized_pnl(self, current_premiums: dict) -> float:
        """Updates open position prices and calculates total unrealized P&L."""
        total_unrealized = 0.0
        for contract, pos in self.open_positions.items():
            curr_prem = current_premiums.get(contract, pos["entry_price"])
            pos["current_price"] = curr_prem
            unrealized = (curr_prem - pos["entry_price"]) * pos["quantity"]
            pos["unrealized_pnl"] = round(unrealized, 2)
            total_unrealized += unrealized
        return round(total_unrealized, 2)

    def get_portfolio_summary(self, current_premiums: dict = None) -> dict:
        """Returns portfolio performance metrics."""
        unrealized = self.update_unrealized_pnl(current_premiums or {})
        equity_value = sum(
            pos["quantity"] * pos.get("current_price", pos["entry_price"])
            for pos in self.open_positions.values()
        )
        total_portfolio_value = self.cash_balance + equity_value

        cooldown_sec = getattr(config, "CONSECUTIVE_LOSS_COOLDOWN_SECONDS", 600)
        max_consecutive = getattr(config, "MAX_CONSECUTIVE_LOSSES", 2)
        elapsed_loss = time.time() - self.last_loss_timestamp
        is_cooldown = (self.consecutive_losses >= max_consecutive) and (elapsed_loss < cooldown_sec)
        cooldown_remaining = max(0, int(cooldown_sec - elapsed_loss)) if is_cooldown else 0

        return {
            "starting_capital": self.starting_capital,
            "cash_balance": round(self.cash_balance, 2),
            "open_positions_count": len(self.open_positions),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": unrealized,
            "total_portfolio_value": round(total_portfolio_value, 2),
            "net_roi_pct": round(((total_portfolio_value - self.starting_capital) / self.starting_capital) * 100, 2),
            "total_trades_completed": len(self.trade_history),
            "consecutive_losses": self.consecutive_losses,
            "is_cooldown_active": is_cooldown,
            "cooldown_remaining_sec": cooldown_remaining,
            "max_daily_trades": getattr(config, "MAX_DAILY_TRADES", 15)
        }
