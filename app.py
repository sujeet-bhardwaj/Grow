"""
Groww Futures & Options (F&O) Trading Bot - Live Web Dashboard & Server
Scans NIFTY 50 and BANKNIFTY, dynamically selects ATM Call (CE) and Put (PE) options, and executes trades.
"""

import sys
import time
import threading
import webbrowser
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

# Ensure safe UTF-8 output
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

app = Flask(__name__)
app.secret_key = getattr(config, "SECRET_KEY", "groww-algo-secret-token-key-2026")

# Obtain Groww session & profile
token, groww_profile = get_groww_session()

paper_trader = PaperTrader(starting_capital=config.INITIAL_PAPER_CAPITAL)
executor = ExecutionManager(access_token=token, paper_trader=paper_trader)
risk_manager = RiskManager(initial_capital=config.INITIAL_PAPER_CAPITAL)
market_data = MarketDataEngine(access_token=token)
strategy = StrategyEngine()


_live_cache_lock = threading.Lock()
_last_live_fetch_time = 0.0
_cached_live_portfolio = {
    "starting_capital": 0.0,
    "cash_balance": 0.0,
    "open_positions_count": 0,
    "realized_pnl": 0.0,
    "unrealized_pnl": 0.0,
    "total_portfolio_value": 0.0,
    "net_roi_pct": 0.0,
    "total_trades_completed": 0,
    "is_live": True
}
_cached_live_positions = {}
LIVE_CACHE_TTL = 15.0  # seconds
_has_warned_live = False


def fetch_groww_live_data_now(current_premiums: dict = None) -> tuple[dict, dict]:
    """Hits Groww API to fetch real F&O margin and open positions (only in LIVE mode)."""
    global _last_live_fetch_time, _cached_live_portfolio, _cached_live_positions, _has_warned_live
    current_premiums = current_premiums or {}

    # Never query live broker if in Paper trading or if token is simulated
    if config.TRADING_MODE != "LIVE" or not token or token == "SIMULATED_GROWW_TOKEN":
        return _cached_live_portfolio, _cached_live_positions

    if not executor.groww_client and token and token != "SIMULATED_GROWW_TOKEN":
        executor._init_client()

    if not executor.groww_client:
        return _cached_live_portfolio, _cached_live_positions

    try:
        live_cash = 0.0
        fno_margin = 0.0
        live_positions_dict = {}
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0

        margin_res = executor.groww_client.get_available_margin_details()
        if isinstance(margin_res, dict):
            live_cash = float(margin_res.get("clear_cash", 0.0) or 0.0)
            fno_details = margin_res.get("fno_margin_details", {})
            fno_margin = float(
                fno_details.get("option_buy_balance_available", 0.0)
                or fno_details.get("future_balance_available", 0.0)
                or live_cash
            )

        pos_res = executor.groww_client.get_positions_for_user()
        if isinstance(pos_res, dict):
            raw_positions = pos_res.get("positions", [])
            for p in raw_positions:
                sym = p.get("trading_symbol", "")
                net_qty = int(p.get("net_quantity", 0) or 0)
                if net_qty != 0:
                    buy_avg = float(p.get("buy_price", 0.0) or 0.0)
                    curr_p = current_premiums.get(sym, buy_avg)
                    unrealized = (curr_p - buy_avg) * net_qty if net_qty > 0 else (buy_avg - curr_p) * abs(net_qty)
                    total_unrealized_pnl += unrealized
                    total_realized_pnl += float(p.get("realised_pnl", 0.0) or 0.0)
                    live_positions_dict[sym] = {
                        "symbol": sym,
                        "underlying": "NIFTY" if "NIFTY" in sym else "BANKNIFTY",
                        "side": "BUY" if net_qty > 0 else "SELL",
                        "quantity": abs(net_qty),
                        "lots": abs(net_qty) // 25 if "NIFTY" in sym else abs(net_qty) // 15,
                        "entry_price": buy_avg,
                        "current_price": curr_p,
                        "stop_loss_price": round(buy_avg * 0.80, 2),
                        "target_price": round(buy_avg * 1.40, 2),
                        "unrealized_pnl": round(unrealized, 2)
                    }

        total_portfolio_value = round(fno_margin + total_unrealized_pnl, 2)
        portfolio = {
            "starting_capital": fno_margin,
            "cash_balance": round(fno_margin, 2),
            "open_positions_count": len(live_positions_dict),
            "realized_pnl": round(total_realized_pnl, 2),
            "unrealized_pnl": round(total_unrealized_pnl, 2),
            "total_portfolio_value": total_portfolio_value,
            "net_roi_pct": round((total_realized_pnl / fno_margin * 100), 2) if fno_margin > 0 else 0.0,
            "total_trades_completed": len(live_positions_dict),
            "is_live": True
        }

        with _live_cache_lock:
            _cached_live_portfolio = portfolio
            _cached_live_positions = live_positions_dict

    except Exception as e:
        if not _has_warned_live:
            print(f"[GROWW API NOTICE] Live margin request: {e}. (Ensure GROWW_ACCESS_TOKEN in .env is updated for live trading. Paper trading remains active.)")
            _has_warned_live = True
    finally:
        _last_live_fetch_time = time.time()

    return _cached_live_portfolio, _cached_live_positions


_is_fetching_live = False
_live_fetch_lock = threading.Lock()


def _background_live_updater(premiums: dict = None):
    """Worker function that runs in background thread to refresh Groww API margin and positions."""
    global _is_fetching_live
    if config.TRADING_MODE != "LIVE":
        return

    with _live_fetch_lock:
        if _is_fetching_live:
            return
        _is_fetching_live = True

    try:
        p, pos = fetch_groww_live_data_now(premiums)
        with state_lock:
            if config.TRADING_MODE == "LIVE":
                shared_state["portfolio"] = p
                shared_state["open_positions"] = pos
    except Exception as e:
        pass
    finally:
        _is_fetching_live = False


def trigger_async_live_update(premiums: dict = None):
    """Non-blocking: kicks off background live margin update only in LIVE mode."""
    if config.TRADING_MODE == "LIVE" and token and token != "SIMULATED_GROWW_TOKEN":
        threading.Thread(target=_background_live_updater, args=(premiums,), daemon=True).start()


def get_live_groww_portfolio(current_premiums: dict = None) -> tuple[dict, dict]:
    """
    ALWAYS returns immediately from in-memory cache (< 0.1ms).
    If cache is older than TTL and in LIVE mode, triggers non-blocking background refresh.
    """
    global _last_live_fetch_time
    now = time.time()
    if config.TRADING_MODE == "LIVE" and (now - _last_live_fetch_time > LIVE_CACHE_TTL):
        trigger_async_live_update(current_premiums)

    with _live_cache_lock:
        port = _cached_live_portfolio.copy()
        pos = _cached_live_positions.copy()

    if current_premiums:
        total_unrealized = 0.0
        for sym, p in pos.items():
            curr_p = current_premiums.get(sym, p["entry_price"])
            p["current_price"] = curr_p
            net_qty = p["quantity"]
            unreal = (curr_p - p["entry_price"]) * net_qty if p.get("side") == "BUY" else (p["entry_price"] - curr_p) * net_qty
            p["unrealized_pnl"] = round(unreal, 2)
            total_unrealized += unreal
        port["unrealized_pnl"] = round(total_unrealized, 2)
        port["total_portfolio_value"] = round(port["cash_balance"] + total_unrealized, 2)

    return port, pos


# Pre-fetch live data once on server start only if in LIVE mode
if config.TRADING_MODE == "LIVE":
    trigger_async_live_update()

initial_portfolio = (
    _cached_live_portfolio
    if config.TRADING_MODE == "LIVE"
    else paper_trader.get_portfolio_summary()
)

shared_state = {
    "broker": "GROWW F&O API",
    "mode": config.TRADING_MODE,
    "segment": "NIFTY 10–15 PT SCALPER (1m/5m F&O Options)",
    "strategy_name": "NIFTY 10–15 Point Scalper (EMA 9/21/50 + PDH/PDL + Pivots + 50-Pt Psych + Order-Flow Delta + Absorption)",
    "groww_profile": groww_profile or {
        "ucc": "6629599909",
        "active_segments": ["CASH", "FNO"]
    },
    "scan_cycle": 0,
    "portfolio": initial_portfolio,
    "indices": [],
    "open_positions": {},
    "activity_logs": [
        {
            "title": "SCALPER READY",
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": f"Connected to Groww Account UCC: {groww_profile.get('ucc', '6629599909')}. NIFTY 10–15 Point Scalper initialized.",
            "type": "SYSTEM"
        }
    ]
}
state_lock = threading.Lock()


def add_log(title: str, message: str, log_type: str = "INFO"):
    with state_lock:
        shared_state["activity_logs"].append({
            "title": title,
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": message,
            "type": log_type
        })
        if len(shared_state["activity_logs"]) > 60:
            shared_state["activity_logs"].pop(0)


def bot_worker_loop():
    """Continuous NIFTY 10–15 Point Scalping Engine & Scanner Loop."""
    print("[SCALP ENGINE] Starting background NIFTY / BANKNIFTY Scalping Loop (1m/5m, EMA 9/21/50, Levels, Delta, Absorption)...")

    cycle = 0

    while True:
        try:
            cycle += 1
            indices_data = []
            current_premiums = {}

            for idx in config.WATCHLIST_INDICES:
                symbol = idx["symbol"]

                # 1. Fetch Index Data (Spot, ATM Strike, CE/PE Premiums, Key Levels, ORB Data)
                idx_data = market_data.get_index_data(symbol)
                spot = idx_data["spot"]
                atm_strike = idx_data["atm_strike"]
                ce_symbol = idx_data["ce_symbol"]
                pe_symbol = idx_data["pe_symbol"]
                ce_prem = idx_data["ce_premium"]
                pe_prem = idx_data["pe_premium"]
                lot_size = idx_data["lot_size"]
                levels = idx_data.get("levels", market_data.get_key_levels(symbol))
                orb_data = idx_data.get("orb", market_data.get_orb_data(symbol))

                current_premiums[ce_symbol] = ce_prem
                current_premiums[pe_symbol] = pe_prem

                # 2. Check Open Positions for this contract (SL / trailing BE / Target)
                if config.TRADING_MODE == "PAPER":
                    for contract_sym in [ce_symbol, pe_symbol]:
                        if contract_sym in paper_trader.open_positions:
                            pos = paper_trader.open_positions[contract_sym]
                            curr_p = current_premiums[contract_sym]
                            exit_needed, exit_reason = risk_manager.check_position_exit(pos, curr_p)
                            if exit_needed:
                                executor.close_option_order(contract_sym, curr_p, exit_reason, pos["quantity"])
                                add_log("EXIT FILLED", f"{contract_sym} closed @ Rs. {curr_p:.2f} ({exit_reason})", "SELL")

                # 3. Multi-Timeframe Candles (1m execution & 5m trend)
                df_1m = market_data.get_index_candles(symbol, interval="1minute", count=60)
                df_5m = market_data.get_index_candles_5m(symbol, count=30)

                # 4. Analyze Strategy (ORB Pine Script v5 / 10-15 pt Scalper)
                analysis = strategy.analyze(df_1m, df_5m, levels, orb_data=orb_data)

                signal = analysis["signal"]
                confluence = analysis.get("confluence_score", 0)
                trend_5m = analysis.get("trend_5m", {})
                exec_1m = analysis.get("exec_1m", {})
                lvl_analysis = analysis.get("levels_analysis", {})
                orderflow = analysis.get("orderflow_summary", {})
                absorption = analysis.get("absorption_detected", "NONE")

                # Handle EOD Square-off (at 15:15 IST)
                if signal == "SQUARE_OFF":
                    for contract_sym in list(paper_trader.open_positions.keys()):
                        curr_p = current_premiums.get(contract_sym, 100.0)
                        executor.close_option_order(contract_sym, curr_p, "EOD Square-Off (15:15 IST)")
                        add_log("EOD EXIT", f"{contract_sym} closed at 15:15 IST Market Square-off", "SELL")

                indices_data.append({
                    "symbol": symbol,
                    "name": idx_data["name"],
                    "spot": spot,
                    "spot_delta": idx_data.get("spot_delta", 0.0),
                    "atm_strike": atm_strike,
                    "ce_symbol": ce_symbol,
                    "pe_symbol": pe_symbol,
                    "ce_premium": ce_prem,
                    "pe_premium": pe_prem,
                    "lot_size": lot_size,
                    "iv": idx_data["iv"],
                    "strategy": analysis.get("strategy", "ORB"),
                    "signal": signal,
                    "reason": analysis["reason"],
                    "confluence_score": confluence,
                    "trend_5m": trend_5m,
                    "exec_1m": exec_1m,
                    "levels": lvl_analysis,
                    "orderflow": orderflow,
                    "absorption": absorption,
                    "orb": orb_data,
                    "target_1_spot": analysis.get("target_1_spot", spot + 20),
                    "target_2_spot": analysis.get("target_2_spot", spot + 30),
                    "sl_spot": analysis.get("sl_spot", spot - 10),
                    "target_points": analysis.get("target_points", 20.0),
                    "stop_loss_points": analysis.get("stop_loss_points", 10.0),
                    "fast_ema": exec_1m.get("ema9", spot),
                    "slow_ema": exec_1m.get("ema21", spot),
                    "rsi": analysis.get("rsi", 50.0),
                    "supertrend_dir": analysis.get("supertrend_dir", 0)
                })

                # Check if position is already active
                is_ce_active = ce_symbol in paper_trader.open_positions
                is_pe_active = pe_symbol in paper_trader.open_positions

                # 5. Handle CALL OPTION (CE) Setup
                if signal == "BUY_CE" and not is_ce_active:
                    allowed, risk_reason = risk_manager.can_open_position(
                        current_open_positions_count=len(paper_trader.open_positions),
                        realized_daily_pnl=paper_trader.realized_pnl
                    )
                    if allowed:
                        avail_funds = paper_trader.cash_balance if config.TRADING_MODE == "PAPER" else shared_state["portfolio"].get("cash_balance", 0.0)
                        
                        # Size by Pine Script formula for ORB, or lot sizing for scalper
                        if analysis.get("strategy") == "ORB":
                            lots, qty = risk_manager.calculate_orb_position_sizing(avail_funds, analysis["stop_loss_points"], lot_size)
                        else:
                            lots, qty = risk_manager.calculate_lot_quantity(ce_prem, avail_funds, lot_size)

                        if lots > 0:
                            targets = risk_manager.calculate_option_targets(
                                ce_prem,
                                target_index_pts=analysis["target_points"],
                                sl_index_pts=analysis["stop_loss_points"]
                            )
                            placed = executor.place_option_order(
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
                            if placed:
                                market_data.set_traded_today(symbol, True)
                                add_log(
                                    f"BUY CALL (CE) — {analysis.get('strategy', 'ORB')}",
                                    f"Bought {lots} Lots ({qty} Qty) of {ce_symbol} @ Rs. {ce_prem:.2f} | Target: Rs. {targets['target_premium']:.2f} (+{analysis['target_points']} Index pts) | SL: Rs. {targets['stop_loss_premium']:.2f} (-{analysis['stop_loss_points']} pts)",
                                    "BUY"
                                )
                    else:
                        add_log("RISK FILTER", f"Call Buy skipped for {ce_symbol}: {risk_reason}", "INFO")

                # 6. Handle PUT OPTION (PE) Setup
                elif signal == "BUY_PE" and not is_pe_active:
                    allowed, risk_reason = risk_manager.can_open_position(
                        current_open_positions_count=len(paper_trader.open_positions),
                        realized_daily_pnl=paper_trader.realized_pnl
                    )
                    if allowed:
                        avail_funds = paper_trader.cash_balance if config.TRADING_MODE == "PAPER" else shared_state["portfolio"].get("cash_balance", 0.0)
                        
                        if analysis.get("strategy") == "ORB":
                            lots, qty = risk_manager.calculate_orb_position_sizing(avail_funds, analysis["stop_loss_points"], lot_size)
                        else:
                            lots, qty = risk_manager.calculate_lot_quantity(pe_prem, avail_funds, lot_size)

                        if lots > 0:
                            targets = risk_manager.calculate_option_targets(
                                pe_prem,
                                target_index_pts=analysis["target_points"],
                                sl_index_pts=analysis["stop_loss_points"]
                            )
                            placed = executor.place_option_order(
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
                            if placed:
                                market_data.set_traded_today(symbol, True)
                                add_log(
                                    f"BUY PUT (PE) — {analysis.get('strategy', 'ORB')}",
                                    f"Bought {lots} Lots ({qty} Qty) of {pe_symbol} @ Rs. {pe_prem:.2f} | Target: Rs. {targets['target_premium']:.2f} (+{analysis['target_points']} Index pts) | SL: Rs. {targets['stop_loss_premium']:.2f} (-{analysis['stop_loss_points']} pts)",
                                    "BUY"
                                )
                    else:
                        add_log("RISK FILTER", f"Put Buy skipped for {pe_symbol}: {risk_reason}", "INFO")

            # Update shared state
            if config.TRADING_MODE == "LIVE":
                portfolio_summary, live_positions = get_live_groww_portfolio(current_premiums)
                open_positions_data = live_positions
            else:
                portfolio_summary = paper_trader.get_portfolio_summary(current_premiums)
                open_positions_data = paper_trader.open_positions.copy()

            with state_lock:
                shared_state["scan_cycle"] = cycle
                shared_state["portfolio"] = portfolio_summary
                shared_state["indices"] = indices_data
                shared_state["open_positions"] = open_positions_data

        except Exception as e:
            print(f"[SCALP LOOP ERROR] {e}")

        time.sleep(getattr(config, "CYCLE_INTERVAL_SECONDS", 3.0))


@app.route("/")
def index():
    if not session.get("logged_in"):
        return redirect("/login")
    return render_template("index.html", user=session.get("username", "admin"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        valid_user = getattr(config, "DASHBOARD_USERNAME", "admin")
        valid_pwd = getattr(config, "DASHBOARD_PASSWORD", "groww123")

        if username == valid_user and password == valid_pwd:
            session["logged_in"] = True
            session["username"] = username
            add_log("AUTH", f"User '{username}' logged in successfully.", "SYSTEM")
            return redirect("/")
        else:
            error = "Invalid username or password. Default is admin / groww123."

    return render_template(
        "login.html",
        error=error,
        is_logged_in=bool(session.get("logged_in")),
        default_user=session.get("username", getattr(config, "DASHBOARD_USERNAME", "admin")),
        ucc=groww_profile.get("ucc", "6629599909")
    )


@app.route("/logout")
def logout():
    username = session.get("username", "admin")
    session.clear()
    add_log("AUTH", f"User '{username}' logged out.", "SYSTEM")
    return redirect("/login")


@app.route("/api/state")
def get_state():
    with state_lock:
        data = shared_state.copy()
        data["logged_in"] = bool(session.get("logged_in"))
        data["username"] = session.get("username", "admin")
        return jsonify(data)


@app.route("/api/reset_paper_funds", methods=["POST"])
def reset_paper_funds():
    global paper_trader
    paper_trader = PaperTrader(starting_capital=100000.0)
    add_log("RESET", "Paper trading portfolio reset to Rs. 1,00,000.00.", "SYSTEM")
    return jsonify({"status": "success", "balance": 100000.0})


@app.route("/api/toggle_mode", methods=["POST"])
def toggle_mode():
    data = request.get_json(silent=True) or {}
    requested_mode = data.get("mode", "").upper()
    if requested_mode in ("PAPER", "LIVE"):
        config.TRADING_MODE = requested_mode

        if requested_mode == "LIVE":
            # Instantly return cached live portfolio (< 1ms)
            live_port, live_pos = get_live_groww_portfolio()
            with state_lock:
                shared_state["mode"] = requested_mode
                shared_state["portfolio"] = live_port
                shared_state["open_positions"] = live_pos
            msg = f"LIVE GROWW F&O ENABLED! Real market orders will now be placed on account UCC: {groww_profile.get('ucc', '6629599909')}."
            trigger_async_live_update()

        else:
            paper_port = paper_trader.get_portfolio_summary()
            with state_lock:
                shared_state["mode"] = requested_mode
                shared_state["portfolio"] = paper_port
                shared_state["open_positions"] = paper_trader.open_positions.copy()
            msg = "Switched to Paper Trading (Rs. 1,00,000 Virtual Funds). Real broker capital is 100% protected."

        add_log("MODE CHANGE", msg, "SELL" if requested_mode == "LIVE" else "INFO")
        return jsonify({
            "status": "success",
            "mode": requested_mode,
            "message": msg,
            "portfolio": shared_state["portfolio"]
        })
    return jsonify({"status": "error", "message": "Invalid mode"}), 400


def open_browser():
    """Opens Google Chrome after 1.5 seconds."""
    time.sleep(1.5)
    print("\n[CHROME LAUNCHER] Opening F&O Chrome Login Terminal at: http://127.0.0.1:5000/login\n")
    try:
        webbrowser.open("http://127.0.0.1:5000/login")
    except Exception as e:
        print(f"[CHROME LAUNCHER] Error opening browser: {e}")


if __name__ == "__main__":
    print("=" * 65)
    print("   GROWW FUTURES & OPTIONS (F&O) TRADING BOT - CHROME TERMINAL")
    print(f"   Groww Account: UCC {groww_profile.get('ucc', '6629599909')}")
    print(f"   Segment: NSE F&O (NIFTY & BANKNIFTY Options)")
    print(f"   Mode: {config.TRADING_MODE}")
    print("   Login URL: http://127.0.0.1:5000/login")
    print("   Default Credentials: admin / groww123")
    print("=" * 65)

    bot_thread = threading.Thread(target=bot_worker_loop, daemon=True)
    bot_thread.start()

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    app.run(host="127.0.0.1", port=5000, debug=False)
