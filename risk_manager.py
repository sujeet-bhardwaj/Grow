import time
import config


class RiskManager:
    def __init__(self, initial_capital: float = getattr(config, "INITIAL_PAPER_CAPITAL", 100000.0)):
        self.initial_capital = initial_capital
        self.max_daily_loss = getattr(config, "MAX_DAILY_LOSS", 5000.0)
        self.max_lots = getattr(config, "MAX_LOTS_PER_TRADE", 2)
        self.max_positions = getattr(config, "MAX_CONCURRENT_POSITIONS", 1)
        self.delta = getattr(config, "ESTIMATED_ATM_DELTA", 0.52)
        self.scalp_target_pts = getattr(config, "SCALP_DEFAULT_TARGET_PTS", 12.5)
        self.scalp_sl_pts = getattr(config, "SCALP_STOP_LOSS_POINTS", 6.0)
        self.trail_breakeven_pts = getattr(config, "TRAIL_BREAKEVEN_POINTS", 7.0)

        # Points 9 & 10 Scalping Engine Rules
        self.max_daily_trades = getattr(config, "MAX_DAILY_TRADES", 15)
        self.max_consecutive_losses = getattr(config, "MAX_CONSECUTIVE_LOSSES", 2)
        self.consecutive_loss_cooldown = getattr(config, "CONSECUTIVE_LOSS_COOLDOWN_SECONDS", 600)
        self.max_holding_seconds = getattr(config, "SCALP_MAX_HOLDING_SECONDS", 180)
        self.enable_runner_trailing = getattr(config, "ENABLE_RUNNER_TRAILING", True)
        self.momentum_trail_gap = getattr(config, "MOMENTUM_TRAIL_GAP_PTS", 2.5)
        self.starting_capital_model = getattr(config, "STARTING_CAPITAL_MODEL", 20000.0)

    @staticmethod
    def calculate_atm_strike(spot_price: float, strike_step: int) -> int:
        """Finds the nearest At-The-Money (ATM) strike for the index."""
        return int(round(spot_price / strike_step) * strike_step)

    @staticmethod
    def build_option_symbol(underlying: str, strike: int, option_type: str) -> str:
        """Builds clean contract display symbol (e.g. NIFTY 25150 CE)."""
        return f"{underlying} {strike} {option_type.upper()}"

    def can_open_position(
        self,
        current_open_positions_count: int,
        realized_daily_pnl: float,
        total_daily_trades: int = 0,
        consecutive_losses: int = 0,
        last_loss_timestamp: float = 0.0
    ) -> tuple[bool, str]:
        """
        Validates if risk limits permit entering a new scalping trade.
        Enforces Point 10 rules:
        - Max 15 trades per day hard ceiling (overtrading circuit breaker)
        - Consecutive-loss protection / cooldown pause
        - Max daily loss circuit breaker
        - Single open position limit
        """
        # 1. Daily Loss Circuit Breaker
        if realized_daily_pnl <= -abs(self.max_daily_loss):
            return False, f"CIRCUIT BREAKER: Daily loss limit (Rs. {abs(self.max_daily_loss):,.2f}) hit!"

        # 2. Point 10: 15 Trades Per Day Hard Maximum Rule
        if total_daily_trades >= self.max_daily_trades:
            return False, f"CIRCUIT BREAKER: 15 Trades per day maximum limit reached ({self.max_daily_trades}). Overtrading prevention active."

        # 3. Point 10: Consecutive Loss Protection Pause
        if consecutive_losses >= self.max_consecutive_losses and last_loss_timestamp > 0:
            elapsed = time.time() - last_loss_timestamp
            if elapsed < self.consecutive_loss_cooldown:
                remaining = int(self.consecutive_loss_cooldown - elapsed)
                return False, f"CONSECUTIVE LOSS PAUSE: {consecutive_losses} consecutive losses. Cooldown active for {remaining}s to protect capital."

        # 4. Max Concurrent Scalping Positions
        if current_open_positions_count >= self.max_positions:
            return False, f"Max concurrent scalping positions limit ({self.max_positions}) reached."

        return True, "Risk checks passed."

    def calculate_lot_quantity(self, premium: float, available_capital: float, lot_size: int) -> tuple[int, int]:
        """
        Calculates allowed number of lots and total quantity.
        Returns: (num_lots, total_shares_quantity)
        """
        if premium <= 0 or available_capital <= 0:
            return 0, 0

        # Cost of 1 lot = premium * lot_size
        cost_per_lot = premium * lot_size
        affordable_lots = int(available_capital // cost_per_lot)
        allowed_lots = min(affordable_lots, self.max_lots)

        if allowed_lots <= 0:
            return 0, 0

        return allowed_lots, allowed_lots * lot_size

    def calculate_orb_position_sizing(self, available_capital: float, risk_pts: float, lot_size: int = 25) -> tuple[int, int]:
        """
        Position sizing formula directly from Pine Script:
        qty = math.floor((initCapital * riskPct / 100) / riskPts)
        Converts to standard exchange lots.
        """
        risk_pct = getattr(config, "OR_RISK_PCT", 0.5)
        capital_risk_budget = available_capital * (risk_pct / 100.0)
        raw_qty = int(available_capital * (risk_pct / 100.0) // max(risk_pts, 1.0))
        calculated_lots = max(raw_qty // lot_size, 1)
        allowed_lots = min(calculated_lots, self.max_lots)
        return allowed_lots, allowed_lots * lot_size

    def calculate_option_targets(self, entry_premium: float, target_index_pts: float = None, sl_index_pts: float = None) -> dict:
        """
        Calculates 10–15 Point Scalp Target and 5–7 Point Stop-Loss for Option Premium:
        Option Move = Index Points * Delta (~0.52).
        For 12.5 index pts target -> ~6.5 option pts profit!
        For 6.0 index pts SL -> ~3.1 option pts risk (1:2 R:R).
        """
        t_pts = target_index_pts if target_index_pts is not None else self.scalp_target_pts
        s_pts = sl_index_pts if sl_index_pts is not None else self.scalp_sl_pts

        option_target_delta = round(t_pts * self.delta, 2)
        option_sl_delta = round(s_pts * self.delta, 2)

        tp_price = round(entry_premium + option_target_delta, 2)
        sl_price = max(round(entry_premium - option_sl_delta, 2), 1.0)
        be_trigger = round(entry_premium + (self.trail_breakeven_pts * self.delta), 2)

        return {
            "entry_premium": entry_premium,
            "target_index_pts": t_pts,
            "sl_index_pts": s_pts,
            "option_target_pts": option_target_delta,
            "option_sl_pts": option_sl_delta,
            "stop_loss_premium": sl_price,
            "target_premium": tp_price,
            "breakeven_trigger_premium": be_trigger,
            "sl_pct": round((option_sl_delta / entry_premium) * 100, 1),
            "tp_pct": round((option_target_delta / entry_premium) * 100, 1)
        }

    def check_position_exit(
        self,
        position: dict,
        current_premium: float,
        confluence_score: int = 0
    ) -> tuple[bool, str]:
        """
        Evaluates if a scalping position has hit:
        - Point 9: Trailing Stop to Breakeven (0-Risk lock)
        - Point 9: 1–3 Minute Time-based Exit (Time stop if trade fails to develop promptly)
        - Point 9: Predefined Target or Extended Momentum Runner Trailing
        - Structural Stop-Loss level
        """
        sl = position.get("stop_loss_price", 0.0)
        tp = position.get("target_price", 999999.0)
        entry = position.get("entry_price", current_premium)
        be_trigger = position.get("breakeven_trigger", entry + 3.5)
        is_trailed = position.get("is_trailed_to_be", False)
        entry_ts = position.get("entry_timestamp", 0.0)
        holding_sec = (time.time() - entry_ts) if entry_ts > 0 else 0.0

        # 1. Trailing Stop to Breakeven check
        if not is_trailed and current_premium >= be_trigger:
            position["stop_loss_price"] = entry  # Move SL to Entry
            position["is_trailed_to_be"] = True
            sl = entry
            print(f"[SCALP TRAILING SL] Trade up +{round(current_premium - entry, 2)} pts -> SL moved to Breakeven (Rs. {entry:.2f})!")

        # 2. Stop Loss Hit
        if current_premium <= sl:
            reason = "SCALP STOP-LOSS HIT" if not is_trailed else "SCALP BREAKEVEN STOP HIT"
            return True, f"{reason} at Rs. {current_premium:.2f} (SL: Rs. {sl:.2f})"

        # 3. Scalp Target Hit / Strong Momentum Runner Trailing (Point 9 Rule)
        if current_premium >= tp:
            # Strong trend persists (confluence >= 80): trail rather than exiting mechanically
            if self.enable_runner_trailing and confluence_score >= 80:
                trail_sl = round(current_premium - self.momentum_trail_gap, 2)
                current_runner_sl = position.get("runner_trail_sl", 0.0)
                if trail_sl > current_runner_sl:
                    position["runner_trail_sl"] = trail_sl
                    position["is_runner_active"] = True

                if current_premium <= position.get("runner_trail_sl", 0.0):
                    gain_pts = round(current_premium - entry, 2)
                    idx_equiv = round(gain_pts / self.delta, 1)
                    return True, f"10–15 PT MOMENTUM RUNNER EXIT at Rs. {current_premium:.2f} (+{gain_pts} Option pts / ~+{idx_equiv} Index pts)"
            else:
                gain_pts = round(current_premium - entry, 2)
                idx_equiv = round(gain_pts / self.delta, 1)
                return True, f"10–15 PT SCALP TARGET HIT at Rs. {current_premium:.2f} (+{gain_pts} Option pts / ~+{idx_equiv} Index pts)"

        # 4. Point 9: 1–3 Minute Trade Management Time Stop
        # If trade fails to develop promptly within 180 seconds (3m), exit to prevent prolonged decay
        if holding_sec >= self.max_holding_seconds:
            pts = round(current_premium - entry, 2)
            idx_equiv = round(pts / self.delta, 1)
            return True, f"1–3 MIN TIME STOP EXIT at Rs. {current_premium:.2f} ({pts:+} Option pts / ~{idx_equiv:+} Index pts | Held {int(holding_sec)}s reached 3m window)"

        return False, ""
