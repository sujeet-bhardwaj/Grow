"""
Main Trading Bot Runner - NIFTY 10–15 Point Scalping Edition
Scans NIFTY 50 (and BANKNIFTY) using:
- 1-minute execution chart
- 5-minute trend chart
- EMA 9 / 21 / 50 on both timeframes
- Previous Day High/Low (PDH / PDL)
- Pivot / R1 / S1 classical floor pivots
- Psychological round levels every 50 points
- Order-flow imbalance + delta
- Absorption / rejection wicks
- Volume confirmation
"""

import time
import sys
from datetime import datetime

# Safe UTF-8 encoding for Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import config
from auth import get_groww_session
from market_data import MarketDataEngine
from strategy import StrategyEngine
from risk_manager import RiskManager
from paper_trader import PaperTrader
from execution import ExecutionManager


def print_banner(ucc: str):
    print("""
======================================================================
     NIFTY 10–15 POINT SCALPING ALGO BOT — GROWW F&O ENGINE
======================================================================
 Broker:        GROWW TRADING API (UCC: {ucc})
 Segment:       NSE F&O Options (ATM CE / PE Scalping)
 Mode:          {mode}
 Starting Fund: Rs. {capital:,.2f}
 Watchlist:     NIFTY 50 (Primary Scalp) | BANKNIFTY
 Strategy:      Multi-Timeframe 1m/5m Scalper
                - 1m Execution Timing & 5m Trend Bias
                - Triple EMA 9 / 21 / 50
                - PDH / PDL & Pivot / R1 / S1
                - 50-Point Psychological Levels
                - Order-Flow Delta & Imbalance (1.4x+)
                - Absorption / Rejection Wicks
                - 20-period Volume Surge Confirmation
 Target / SL:   10–15 Index Points Scalp (~6-9 Option Pts) | SL: 6 Pts
======================================================================
    """.format(
        ucc=ucc,
        mode="PAPER SIMULATION (Zero Risk)" if config.TRADING_MODE == "PAPER" else "LIVE GROWW F&O (Real Money)",
        capital=config.INITIAL_PAPER_CAPITAL
    ))


def run_bot():
    token, profile = get_groww_session()
    ucc = profile.get("ucc", "6629599909")
    print_banner(ucc)

    market_data = MarketDataEngine(access_token=token)
    strategy = StrategyEngine()
    risk_manager = RiskManager(initial_capital=config.INITIAL_PAPER_CAPITAL)
    paper_trader = PaperTrader(starting_capital=config.INITIAL_PAPER_CAPITAL)
    executor = ExecutionManager(access_token=token, paper_trader=paper_trader)

    cycle = 0

    try:
        while True:
            cycle += 1
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n--- [Cycle #{cycle} @ {now_str}] NIFTY 10–15 PT SCALPING RADAR ---")

            current_premiums = {}

            for idx in config.WATCHLIST_INDICES:
                symbol = idx["symbol"]
                lot_size = idx["lot_size"]

                # 1. Fetch Index Data (Spot, ATM Strike, CE/PE Premiums, Key Levels)
                idx_data = market_data.get_index_data(symbol)
                spot = idx_data["spot"]
                atm_strike = idx_data["atm_strike"]
                ce_symbol = idx_data["ce_symbol"]
                pe_symbol = idx_data["pe_symbol"]
                ce_prem = idx_data["ce_premium"]
                pe_prem = idx_data["pe_premium"]
                levels = idx_data.get("levels", market_data.get_key_levels(symbol))

                current_premiums[ce_symbol] = ce_prem
                current_premiums[pe_symbol] = pe_prem

                # 2. Check open option positions for SL (-6 pts / trailing BE) or 10-15 pt Target
                for contract_sym in [ce_symbol, pe_symbol]:
                    if contract_sym in paper_trader.open_positions:
                        pos = paper_trader.open_positions[contract_sym]
                        curr_p = current_premiums[contract_sym]
                        exit_needed, exit_reason = risk_manager.check_position_exit(pos, curr_p)
                        if exit_needed:
                            executor.close_option_order(contract_sym, curr_p, exit_reason, pos["quantity"])

                # 3. Fetch Multi-Timeframe Candles (1m execution & 5m trend)
                df_1m = market_data.get_index_candles(symbol, interval="1minute", count=60)
                df_5m = market_data.get_index_candles_5m(symbol, count=30)

                # 4. Analyze Scalp Setup (EMA 9/21/50, PDH/PDL, Pivots, Psych 50, Delta, Absorption, Volume)
                analysis = strategy.analyze(df_1m, df_5m, levels)

                t5m = analysis["trend_5m"]
                e1m = analysis["exec_1m"]
                lvl_info = analysis["levels_analysis"]
                of = analysis["orderflow_summary"]
                signal = analysis["signal"]
                confluence = analysis["confluence_score"]
                absorption = analysis["absorption_detected"]

                trend_str = f"{t5m['bias']} [5m EMA: {t5m['ema9']}/{t5m['ema21']}/{t5m['ema50']}]"
                exec_str = f"1m EMA: {e1m['ema9']}/{e1m['ema21']}/{e1m['ema50']}"
                lvl_str = f"Nearest: {lvl_info.get('nearest_level_name', 'N/A')} ({lvl_info.get('distance', 0)} pts) | Psych 50: {levels.get('psych_nearest', 0)}"
                of_str = f"Delta: {of['delta']:+d} | Imb: {of['imbalance_ratio']}x | VolRatio: {of['vol_ratio']}x ({'CONFIRMED' if of['volume_confirmed'] else 'WAIT'})"
                absorp_str = f"Absorption: {absorption}" if absorption != "NONE" else "Rejection: None"

                print(f"\n>> [{symbol}] Spot: Rs. {spot:,.2f} | ATM Strike: {atm_strike}")
                print(f"   Trend (5m):      {trend_str}")
                print(f"   Execution (1m):  {exec_str}")
                print(f"   Key Levels:      {lvl_str}")
                print(f"   Order-Flow:      {of_str} | {absorp_str}")
                print(f"   Signal:          {signal} (Confluence: {confluence}%)")

                # 5. Handle CALL OPTION (CE) Scalp Setup
                if signal == "BUY_CE" and ce_symbol not in paper_trader.open_positions:
                    allowed, risk_reason = risk_manager.can_open_position(
                        current_open_positions_count=len(paper_trader.open_positions),
                        realized_daily_pnl=paper_trader.realized_pnl
                    )
                    if allowed:
                        lots, qty = risk_manager.calculate_lot_quantity(ce_prem, paper_trader.cash_balance, lot_size)
                        if lots > 0:
                            targets = risk_manager.calculate_option_targets(
                                ce_prem,
                                target_index_pts=analysis["target_points"],
                                sl_index_pts=analysis["stop_loss_points"]
                            )
                            executor.place_option_order(
                                contract_symbol=ce_symbol,
                                underlying=symbol,
                                strike=atm_strike,
                                option_type="CE",
                                lots=lots,
                                quantity=qty,
                                premium=ce_prem,
                                sl_premium=targets["stop_loss_premium"],
                                tp_premium=targets["target_premium"],
                                entry_spot=spot,
                                target_index_pts=analysis["target_points"],
                                sl_index_pts=analysis["stop_loss_points"],
                                breakeven_trigger=targets["breakeven_trigger_premium"],
                                confluence_score=confluence
                            )

                # 6. Handle PUT OPTION (PE) Scalp Setup
                elif signal == "BUY_PE" and pe_symbol not in paper_trader.open_positions:
                    allowed, risk_reason = risk_manager.can_open_position(
                        current_open_positions_count=len(paper_trader.open_positions),
                        realized_daily_pnl=paper_trader.realized_pnl
                    )
                    if allowed:
                        lots, qty = risk_manager.calculate_lot_quantity(pe_prem, paper_trader.cash_balance, lot_size)
                        if lots > 0:
                            targets = risk_manager.calculate_option_targets(
                                pe_prem,
                                target_index_pts=analysis["target_points"],
                                sl_index_pts=analysis["stop_loss_points"]
                            )
                            executor.place_option_order(
                                contract_symbol=pe_symbol,
                                underlying=symbol,
                                strike=atm_strike,
                                option_type="PE",
                                lots=lots,
                                quantity=qty,
                                premium=pe_prem,
                                sl_premium=targets["stop_loss_premium"],
                                tp_premium=targets["target_premium"],
                                entry_spot=spot,
                                target_index_pts=analysis["target_points"],
                                sl_index_pts=analysis["stop_loss_points"],
                                breakeven_trigger=targets["breakeven_trigger_premium"],
                                confluence_score=confluence
                            )

            # Portfolio Summary
            summary = paper_trader.get_portfolio_summary(current_premiums)
            open_count = summary["open_positions_count"]
            realized = summary["realized_pnl"]
            unrealized = summary["unrealized_pnl"]
            total_val = summary["total_portfolio_value"]
            roi = summary["net_roi_pct"]

            print("-" * 75)
            print(
                f"  SCALP PORTFOLIO: Cash: Rs. {summary['cash_balance']:,.2f} | Open Scalps: {open_count} | "
                f"Realized PnL: Rs. {realized:+,.2f} | Floating: Rs. {unrealized:+,.2f} | "
                f"Net Value: Rs. {total_val:,.2f} ({roi:+.2f}%)"
            )
            print("-" * 75)

            time.sleep(config.CYCLE_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n\n" + "=" * 75)
        print(" NIFTY SCALPING BOT STOPPED BY USER")
        print("=" * 75)
        final_summary = paper_trader.get_portfolio_summary()
        print(f"Completed Scalps:    {final_summary['total_trades_completed']}")
        print(f"Final Cash:          Rs. {final_summary['cash_balance']:,.2f}")
        print(f"Realized P&L:        Rs. {final_summary['realized_pnl']:+,.2f}")
        print(f"Net Portfolio Value: Rs. {final_summary['total_portfolio_value']:,.2f} ({final_summary['net_roi_pct']:+.2f}%)")
        print("=" * 75)
        sys.exit(0)


if __name__ == "__main__":
    run_bot()
