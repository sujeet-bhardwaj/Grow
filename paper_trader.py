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
        self.peak_capital = starting_capital
        self.max_drawdown = 0.0
        self.open_positions = {}  # contract_symbol -> position dict
        self.trade_history = []
        self.realized_pnl = 0.0
        self.consecutive_losses = 0
        self.max_consecutive_losses_record = 0
        self.last_loss_timestamp = 0.0
        self.last_exit_timestamp = 0.0

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
            "invested_amount": round(cost, 2),
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
        """Simulates closing an open scalping position with realistic costs, slippage and P&L ledger."""
        if contract_symbol not in self.open_positions:
            return {}

        pos = self.open_positions.pop(contract_symbol)
        qty = pos["quantity"]
        entry_premium = pos["entry_price"]

        # Realistic Slippage Buffer (PDF Section 11)
        slippage = getattr(config, "SLIPPAGE_PTS", 0.0) if getattr(config, "REALISTIC_COSTS_ENABLED", True) else 0.0
        effective_exit = max(round(exit_premium - slippage, 2), 0.5)

        gross_trade_pnl = round((effective_exit - entry_premium) * qty, 2)

        # Realistic F&O Brokerage & Regulatory Charges (PDF Section 11 & 12)
        from risk_manager import RiskManager
        charges_info = RiskManager.calculate_fno_charges(entry_premium, effective_exit, qty)
        total_charges = charges_info["total_charges"] if getattr(config, "REALISTIC_COSTS_ENABLED", True) else 0.0
        net_trade_pnl = round(gross_trade_pnl - total_charges, 2)

        pnl_pct = round(((effective_exit - entry_premium) / entry_premium) * 100, 2) if entry_premium > 0 else 0.0
        delta = getattr(config, "ESTIMATED_ATM_DELTA", 0.52)
        captured_pts = round((effective_exit - entry_premium), 2)
        idx_captured_pts = round(captured_pts / delta, 1)

        # Return capital to cash balance (after net P&L)
        return_capital = (qty * entry_premium) + net_trade_pnl
        self.cash_balance += max(return_capital, 0.0)
        self.realized_pnl += net_trade_pnl

        # Track Peak Capital & Drawdown (PDF Section 12)
        curr_val = self.cash_balance + sum(
            p["quantity"] * p.get("current_price", p["entry_price"]) for p in self.open_positions.values()
        )
        if curr_val > self.peak_capital:
            self.peak_capital = curr_val
        drawdown = self.peak_capital - curr_val
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown

        # Track consecutive loss streak (PDF Section 7 & 10)
        if net_trade_pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses > self.max_consecutive_losses_record:
                self.max_consecutive_losses_record = self.consecutive_losses
            self.last_loss_timestamp = time.time()
        else:
            self.consecutive_losses = 0

        self.last_exit_timestamp = time.time()

        record = {
            "symbol": pos["symbol"],
            "underlying": pos.get("underlying", ""),
            "lots": pos.get("lots", 1),
            "quantity": qty,
            "entry_price": entry_premium,
            "invested_amount": round(entry_premium * qty, 2),
            "raw_exit_price": exit_premium,
            "exit_price": effective_exit,
            "slippage": slippage,
            "captured_option_pts": captured_pts,
            "captured_index_pts": idx_captured_pts,
            "gross_pnl": gross_trade_pnl,
            "charges": total_charges,
            "charges_detail": charges_info,
            "pnl": net_trade_pnl,  # Net P&L after costs (Section 12)
            "net_pnl": net_trade_pnl,
            "pnl_pct": pnl_pct,
            "entry_time": pos.get("entry_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            "exit_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exit_reason": exit_reason
        }
        self.trade_history.append(record)

        color_tag = "PROFIT" if net_trade_pnl >= 0 else "LOSS"
        print(f"\n[SCALP POSITION CLOSED] {pos['symbol']} @ Rs. {effective_exit:.2f} ({exit_reason})")
        print(f"  -> Points: {captured_pts:+} Option pts (~{idx_captured_pts:+} Index pts)")
        print(f"  -> Gross PnL: Rs. {gross_trade_pnl:+,.2f} | Charges: Rs. {total_charges:.2f} | Net: {color_tag} Rs. {net_trade_pnl:+,.2f}")
        print(f"  -> Total Realized Net PnL: Rs. {self.realized_pnl:+,.2f} | Cash: Rs. {self.cash_balance:,.2f}\n")

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
        """
        Returns full portfolio performance metrics incorporating all 10 metrics
        specified in PDF Section 12 (Performance Report):
        1. Total trades
        2. Win rate
        3. Average win/loss
        4. Net P&L after costs
        5. Profit factor
        6. Maximum drawdown
        7. Consecutive losses
        8. Trades/day
        9. Monthly results
        10. Equity curve
        """
        unrealized = self.update_unrealized_pnl(current_premiums or {})
        equity_value = sum(
            pos["quantity"] * pos.get("current_price", pos["entry_price"])
            for pos in self.open_positions.values()
        )
        total_portfolio_value = self.cash_balance + equity_value

        # Update peak capital & drawdown continuously
        if total_portfolio_value > self.peak_capital:
            self.peak_capital = total_portfolio_value
        current_drawdown = self.peak_capital - total_portfolio_value
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown

        cooldown_sec = getattr(config, "CONSECUTIVE_LOSS_COOLDOWN_SECONDS", 600)
        max_consecutive = getattr(config, "MAX_CONSECUTIVE_LOSSES", 2)
        elapsed_loss = time.time() - self.last_loss_timestamp
        is_cooldown = (self.consecutive_losses >= max_consecutive) and (elapsed_loss < cooldown_sec)
        cooldown_remaining = max(0, int(cooldown_sec - elapsed_loss)) if is_cooldown else 0

        winning_trades_list = [t for t in self.trade_history if t.get("pnl", 0) > 0]
        losing_trades_list = [t for t in self.trade_history if t.get("pnl", 0) < 0]
        wins = len(winning_trades_list)
        losses = len(losing_trades_list)
        total_trades = len(self.trade_history)

        total_turnover = round(sum(t.get("invested_amount", 0) for t in self.trade_history), 2)
        currently_invested = round(sum(pos.get("invested_amount", 0) for pos in self.open_positions.values()), 2)
        total_charges_deducted = round(sum(t.get("charges", 0) for t in self.trade_history), 2)
        gross_pnl_total = round(sum(t.get("gross_pnl", t.get("pnl", 0)) for t in self.trade_history), 2)

        # 3. Average win/loss (PDF Section 12)
        avg_win = round(sum(t.get("pnl", 0) for t in winning_trades_list) / wins, 2) if wins > 0 else 0.0
        avg_loss = round(abs(sum(t.get("pnl", 0) for t in losing_trades_list)) / losses, 2) if losses > 0 else 0.0
        win_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else (round(avg_win, 2) if avg_win > 0 else 0.0)

        # 5. Profit factor (Gross Profit / Gross Loss) (PDF Section 12)
        gross_wins_sum = sum(t.get("gross_pnl", 0) for t in self.trade_history if t.get("gross_pnl", 0) > 0)
        gross_loss_sum = abs(sum(t.get("gross_pnl", 0) for t in self.trade_history if t.get("gross_pnl", 0) < 0))
        if gross_loss_sum > 0:
            profit_factor = round(gross_wins_sum / gross_loss_sum, 2)
        elif gross_wins_sum > 0:
            profit_factor = 99.0
        else:
            profit_factor = 0.0

        # 6. Maximum drawdown (PDF Section 12)
        max_dd_amount = round(self.max_drawdown, 2)
        max_dd_pct = round((self.max_drawdown / self.peak_capital) * 100, 2) if self.peak_capital > 0 else 0.0

        # 8. Trades / day (PDF Section 12)
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in self.trade_history if t.get("entry_time", "").startswith(today_str)]
        unique_days = len(set(t.get("entry_time", "")[:10] for t in self.trade_history if t.get("entry_time")))
        trades_per_day = round(total_trades / max(unique_days, 1), 1) if total_trades > 0 else 0.0

        # 9. Monthly results (PDF Section 12)
        monthly_map = {}
        for t in self.trade_history:
            m_key = t.get("entry_time", "")[:7] or today_str[:7]
            if m_key not in monthly_map:
                monthly_map[m_key] = {"month": m_key, "trades": 0, "net_pnl": 0.0, "wins": 0, "losses": 0}
            monthly_map[m_key]["trades"] += 1
            monthly_map[m_key]["net_pnl"] = round(monthly_map[m_key]["net_pnl"] + t.get("pnl", 0), 2)
            if t.get("pnl", 0) > 0:
                monthly_map[m_key]["wins"] += 1
            else:
                monthly_map[m_key]["losses"] += 1
        monthly_results = list(monthly_map.values())

        # 10. Equity curve points (PDF Section 12)
        equity_curve = [{"time": "Start", "equity": self.starting_capital}]
        running_eq = self.starting_capital
        for idx, t in enumerate(self.trade_history):
            running_eq += t.get("pnl", 0)
            equity_curve.append({
                "time": t.get("exit_time", f"Trade {idx+1}")[11:19] or f"T{idx+1}",
                "equity": round(running_eq, 2)
            })

        return {
            "starting_capital": self.starting_capital,
            "cash_balance": round(self.cash_balance, 2),
            "currently_invested": currently_invested,
            "total_turnover": total_turnover,
            "open_positions_count": len(self.open_positions),
            "realized_pnl": round(self.realized_pnl, 2),
            "unrealized_pnl": unrealized,
            "total_portfolio_value": round(total_portfolio_value, 2),
            "net_roi_pct": round(((total_portfolio_value - self.starting_capital) / self.starting_capital) * 100, 2),
            
            # PDF Section 12 Required Metrics
            "total_trades_completed": total_trades,
            "winning_trades": wins,
            "losing_trades": losses,
            "win_rate_pct": round((wins / total_trades * 100), 1) if total_trades else 0.0,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "avg_win_loss_ratio": win_loss_ratio,
            "gross_pnl_total": gross_pnl_total,
            "total_charges_deducted": total_charges_deducted,
            "net_pnl_after_costs": round(self.realized_pnl, 2),
            "profit_factor": profit_factor,
            "max_drawdown_amount": max_dd_amount,
            "max_drawdown_pct": max_dd_pct,
            "peak_capital": round(self.peak_capital, 2),
            "consecutive_losses": self.consecutive_losses,
            "max_consecutive_losses_recorded": self.max_consecutive_losses_record,
            "is_cooldown_active": is_cooldown,
            "cooldown_remaining_sec": cooldown_remaining,
            "today_trades_count": len(today_trades),
            "trades_per_day": trades_per_day,
            # Position State & Net NIFTY points (PDF Section 11 & 13)
            "position_state": "FLAT" if not self.open_positions else f"{'LONG' if next(iter(self.open_positions.values())).get('option_type') == 'CE' else 'SHORT'} ({next(iter(self.open_positions.values())).get('symbol', '')})",
            "net_nifty_points": round(sum(t.get("captured_index_pts", 0.0) for t in self.trade_history), 1),
            "last_exit_timestamp": self.last_exit_timestamp,
            "is_exit_cooldown_active": (time.time() - self.last_exit_timestamp < getattr(config, "POST_EXIT_COOLDOWN_SECONDS", 60)) if self.last_exit_timestamp > 0 else False,
            "exit_cooldown_remaining_sec": max(0, int(getattr(config, "POST_EXIT_COOLDOWN_SECONDS", 60) - (time.time() - self.last_exit_timestamp))) if (self.last_exit_timestamp > 0 and (time.time() - self.last_exit_timestamp < getattr(config, "POST_EXIT_COOLDOWN_SECONDS", 60))) else 0,
            "max_daily_trades": getattr(config, "MAX_DAILY_TRADES", 15),
            "monthly_results": monthly_results,
            "equity_curve": equity_curve[-25:]  # Recent 25 points for curve
        }

