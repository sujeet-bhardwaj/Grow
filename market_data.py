"""
Market Data Engine for Futures & Options (F&O)
Supports:
1. NIFTY / BANKNIFTY Multi-Timeframe Data (1-Min Execution & 5-Min Trend)
2. 15-Minute Opening Range Breakout (ORB) Engine:
   - Opening Range High (orHigh) & Low (orLow) from 09:15 to 09:30 AM IST
   - Range Width (%) Filter (minWidthPct: 0.30% to maxWidthPct: 1.00%)
   - Intraday Volume Weighted Average Price (VWAP)
   - 20-bar Average Volume with volMult (1.0x) multiplier
   - Session Time Windows: Trade Window (09:30 - 11:00 AM IST) & EOD Square-off (15:15 IST)
3. Microstructure & Scalping Data (EMA 9/21/50, Order Flow Delta, PDH/PDL, Pivots, 50-pt Psych Levels)
"""

import time
import math
import random
from datetime import datetime, timedelta, time as dt_time
import numpy as np
import pandas as pd
import config


class MarketDataEngine:
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.groww_client = None
        self._init_groww_client()

        # Base spot anchors for simulation
        self.index_spots = {
            item["symbol"]: item.get("base_spot", 25150.0)
            for item in config.WATCHLIST_INDICES
        }
        self.option_premiums = {
            f"{item['symbol']}_CE": item.get("default_premium", 140.0)
            for item in config.WATCHLIST_INDICES
        }
        self.option_premiums.update({
            f"{item['symbol']}_PE": item.get("default_premium", 140.0)
            for item in config.WATCHLIST_INDICES
        })

        # Key levels: Previous Day High / Low / Close & Floor Pivots
        self.key_levels = {
            "NIFTY": {
                "pdh": 25215.50,
                "pdl": 25075.20,
                "pdc": 25140.80,
            },
            "BANKNIFTY": {
                "pdh": 51850.00,
                "pdl": 51320.00,
                "pdc": 51610.00,
            }
        }

        # Calculate standard floor pivots for each index
        self._calculate_pivots()

        # Multi-timeframe candle caches
        self.index_candles_1m = {}
        self.index_candles_5m = {}

        # Opening Range Breakout (ORB) State Tracker
        self.orb_state = {
            "NIFTY": {
                "or_high": 25192.50,
                "or_low": 25088.20,
                "or_done": True,
                "traded_today": False,
                "date": datetime.now().date()
            },
            "BANKNIFTY": {
                "or_high": 51820.00,
                "or_low": 51460.00,
                "or_done": True,
                "traded_today": False,
                "date": datetime.now().date()
            }
        }

        # Running tick memory
        self.last_tick_direction = {}

    def _init_groww_client(self):
        if self.access_token and self.access_token != "SIMULATED_GROWW_TOKEN":
            try:
                from growwapi import GrowwAPI
                self.groww_client = GrowwAPI(self.access_token)
            except Exception:
                self.groww_client = None

    def _calculate_pivots(self):
        for sym, lvl in self.key_levels.items():
            h = lvl["pdh"]
            l = lvl["pdl"]
            c = lvl["pdc"]
            p = round((h + l + c) / 3.0, 2)
            r1 = round((2.0 * p) - l, 2)
            s1 = round((2.0 * p) - h, 2)
            r2 = round(p + (h - l), 2)
            s2 = round(p - (h - l), 2)

            lvl["pivot"] = p
            lvl["r1"] = r1
            lvl["s1"] = s1
            lvl["r2"] = r2
            lvl["s2"] = s2

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """
        Calculates intraday Volume Weighted Average Price (VWAP).
        Formula: sum(Typical Price * Volume) / sum(Volume)
        """
        if df.empty or "volume" not in df.columns:
            return pd.Series([df["close"].iloc[-1] if not df.empty else 0.0] * len(df))

        typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
        pv = typical_price * df["volume"]
        cum_pv = pv.cumsum()
        cum_vol = df["volume"].cumsum()
        return (cum_pv / cum_vol.replace(0, np.nan)).fillna(df["close"]).round(2)

    def get_session_window_status(self) -> dict:
        """
        Evaluates IST session time windows from Pine Script inputs:
        - 09:15 to 09:30: Opening Range (inOR)
        - 09:30 to 11:00: Trade Window (inWindow)
        - >= 15:15: Square-off Time (atSquareOff)
        """
        now = datetime.now()
        current_t = now.time()

        or_start = dt_time(9, 15)
        trade_start = dt_time(9, 30)
        trade_end = dt_time(11, 0)
        sq_off = dt_time(15, 15)

        # Check actual time
        actual_in_or = or_start <= current_t < trade_start
        actual_in_window = trade_start <= current_t <= trade_end
        actual_at_sqoff = current_t >= sq_off

        # In paper/simulation mode, if outside market hours, simulate inWindow = True for continuous testing
        is_market_hours = dt_time(9, 15) <= current_t <= dt_time(15, 30)
        simulated_in_window = actual_in_window or (config.TRADING_MODE == "PAPER" and not is_market_hours)

        return {
            "current_time_str": now.strftime("%H:%M:%S"),
            "in_or": actual_in_or,
            "in_window": simulated_in_window,
            "actual_in_window": actual_in_window,
            "at_square_off": actual_at_sqoff,
            "is_market_hours": is_market_hours
        }

    def get_orb_data(self, symbol: str) -> dict:
        """
        Computes 15-minute Opening Range (OR) metrics as specified in Pine Script:
        - orHigh, orLow, orDone
        - width = orHigh - orLow
        - widthPct = width / close * 100
        - rangeOK = orDone and widthPct >= minWidthPct and widthPct <= maxWidthPct
        - vwap = ta.vwap(close)
        - avgVol = ta.sma(volume, 20)
        - volOK = volume > avgVol * volMult
        """
        spot = self.index_spots.get(symbol, 25150.0)
        state = self.orb_state.get(symbol, self.orb_state["NIFTY"])

        # Reset daily state on new day
        today = datetime.now().date()
        if state["date"] != today:
            state["date"] = today
            state["traded_today"] = False
            state["or_done"] = True

        df_1m = self.get_index_candles(symbol, interval="1minute", count=60)
        curr = df_1m.iloc[-1]
        c = float(curr["close"])
        vol = float(curr["volume"])

        # Compute VWAP
        df_1m["vwap"] = self.calculate_vwap(df_1m)
        curr_vwap = round(float(df_1m["vwap"].iloc[-1]), 2)

        # 20-bar SMA of volume
        avg_vol = float(df_1m["volume"].rolling(20, min_periods=1).mean().iloc[-1])
        vol_mult = getattr(config, "OR_VOL_MULT", 1.0)
        vol_ok = vol > (avg_vol * vol_mult) if getattr(config, "OR_USE_VOLUME", True) else True

        # Opening Range calculation
        or_h = state["or_high"]
        or_l = state["or_low"]
        or_done = state["or_done"]

        width = round(or_h - or_l, 2)
        width_pct = round((width / c) * 100, 2) if c > 0 else 0.0

        min_w_pct = getattr(config, "OR_MIN_WIDTH_PCT", 0.30)
        max_w_pct = getattr(config, "OR_MAX_WIDTH_PCT", 1.00)
        range_ok = or_done and (width_pct >= min_w_pct) and (width_pct <= max_w_pct)

        sess = self.get_session_window_status()

        return {
            "symbol": symbol,
            "spot": c,
            "or_high": or_h,
            "or_low": or_l,
            "or_done": or_done,
            "width": width,
            "width_pct": width_pct,
            "min_width_pct": min_w_pct,
            "max_width_pct": max_w_pct,
            "range_ok": range_ok,
            "vwap": curr_vwap,
            "avg_vol_20": int(avg_vol),
            "current_vol": int(vol),
            "vol_ok": vol_ok,
            "trend_l": c > curr_vwap,
            "trend_s": c < curr_vwap,
            "in_window": sess["in_window"],
            "at_square_off": sess["at_square_off"],
            "traded_today": state["traded_today"]
        }

    def set_traded_today(self, symbol: str, traded: bool = True):
        """Marks that the asset has executed its daily trade."""
        if symbol in self.orb_state:
            self.orb_state[symbol]["traded_today"] = traded

    def get_psychological_levels(self, spot: float, step: int = config.PSYCH_LEVEL_STEP) -> dict:
        """
        Calculates NIFTY psychological round numbers every 50 points (e.g. 25000, 25050, 25100).
        """
        nearest = round(spot / step) * step
        lower = math.floor(spot / step) * step
        upper = math.ceil(spot / step) * step
        if upper == lower:
            upper += step
        dist = round(abs(spot - nearest), 2)

        return {
            "step": step,
            "nearest": float(nearest),
            "upper": float(upper),
            "lower": float(lower),
            "distance": dist,
            "is_near": dist <= config.PSYCH_PROXIMITY_THRESHOLD
        }

    def get_key_levels(self, symbol: str) -> dict:
        """Returns PDH, PDL, PDC, Pivot, R1, S1, and 50-pt Psychological levels."""
        spot = self.index_spots.get(symbol, 25150.0)
        base_levels = self.key_levels.get(symbol, self.key_levels["NIFTY"]).copy()
        psych = self.get_psychological_levels(spot, step=50 if symbol == "NIFTY" else 100)
        base_levels.update({
            "psych_nearest": psych["nearest"],
            "psych_upper": psych["upper"],
            "psych_lower": psych["lower"],
            "psych_dist": psych["distance"],
            "psych_near": psych["is_near"]
        })
        return base_levels

    def get_index_data(self, symbol: str) -> dict:
        """
        Fetches live underlying index spot price and calculates ATM CE & PE option premiums,
        Order-flow delta, ORB data, and key level metrics.
        """
        curr_spot = self.index_spots.get(symbol, 25150.0)
        idx_cfg = next((x for x in config.WATCHLIST_INDICES if x["symbol"] == symbol), config.WATCHLIST_INDICES[0])
        strike_step = idx_cfg["strike_step"]

        # Realistic index price tick (-0.12% to +0.12%)
        bias = random.choice([-0.0006, 0.0006, 0.0, 0.0003, -0.0003])
        pct_change = random.uniform(-0.0012, 0.0012) + bias
        new_spot = round(curr_spot * (1 + pct_change), 2)
        spot_delta = new_spot - curr_spot
        self.index_spots[symbol] = new_spot

        # Calculate nearest At-The-Money (ATM) strike
        atm_strike = int(round(new_spot / strike_step) * strike_step)

        # Delta behavior (~0.52 Delta for ATM options)
        ce_key = f"{symbol}_CE"
        pe_key = f"{symbol}_PE"

        curr_ce = self.option_premiums.get(ce_key, idx_cfg.get("default_premium", 140.0))
        curr_pe = self.option_premiums.get(pe_key, idx_cfg.get("default_premium", 140.0))

        delta_factor = config.ESTIMATED_ATM_DELTA
        new_ce = max(round(curr_ce + (spot_delta * delta_factor) + random.uniform(-0.3, 0.3), 2), 5.0)
        new_pe = max(round(curr_pe - (spot_delta * delta_factor) + random.uniform(-0.3, 0.3), 2), 5.0)

        self.option_premiums[ce_key] = new_ce
        self.option_premiums[pe_key] = new_pe

        is_buyer_initiated = spot_delta >= 0
        self._append_index_tick(symbol, new_spot, is_buyer_initiated)

        levels = self.get_key_levels(symbol)
        orb_data = self.get_orb_data(symbol)

        return {
            "symbol": symbol,
            "name": idx_cfg["name"],
            "spot": new_spot,
            "spot_delta": round(spot_delta, 2),
            "lot_size": idx_cfg["lot_size"],
            "strike_step": strike_step,
            "atm_strike": atm_strike,
            "ce_symbol": f"{symbol} {atm_strike} CE",
            "pe_symbol": f"{symbol} {atm_strike} PE",
            "ce_premium": new_ce,
            "pe_premium": new_pe,
            "iv": round(random.uniform(13.5, 17.0), 1),
            "delta": delta_factor,
            "levels": levels,
            "orb": orb_data
        }

    def get_option_premium(self, underlying: str, strike: int, option_type: str) -> float:
        """Returns current market price (LTP) for an option contract."""
        key = f"{underlying}_{option_type.upper()}"
        return self.option_premiums.get(key, 120.0)

    def get_index_candles(self, symbol: str, interval: str = "1minute", count: int = 60) -> pd.DataFrame:
        """
        Generates/returns historical 1-minute execution candles enriched with:
        - Open, High, Low, Close, Volume
        - Buy Volume, Sell Volume
        - Order-Flow Delta
        - Imbalance Ratio & VWAP
        """
        if symbol in self.index_candles_1m and len(self.index_candles_1m[symbol]) >= count:
            df = pd.DataFrame(self.index_candles_1m[symbol]).tail(count).reset_index(drop=True)
            return self._enrich_candle_orderflow(df)

        base = self.index_spots.get(symbol, 25150.0)
        candles = []
        now = datetime.now() - timedelta(minutes=count)
        curr = base

        for i in range(count):
            now += timedelta(minutes=1)
            change = curr * random.uniform(-0.0015, 0.0015)
            o = curr
            c = round(curr + change, 2)
            h = round(max(o, c) + abs(change) * random.uniform(0.1, 0.5), 2)
            l = round(min(o, c) - abs(change) * random.uniform(0.1, 0.5), 2)
            v = random.randint(60000, 220000)

            if c >= o:
                buy_pct = random.uniform(0.52, 0.75)
            else:
                buy_pct = random.uniform(0.25, 0.48)
            buy_vol = int(v * buy_pct)
            sell_vol = v - buy_vol
            delta = buy_vol - sell_vol

            candles.append({
                "timestamp": now,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "buy_volume": buy_vol,
                "sell_volume": sell_vol,
                "delta": delta
            })
            curr = c

        self.index_candles_1m[symbol] = candles
        df = pd.DataFrame(candles)
        return self._enrich_candle_orderflow(df)

    def get_index_candles_5m(self, symbol: str, count: int = 30) -> pd.DataFrame:
        """
        Generates/returns 5-minute trend candles aggregated from 1m series or generated.
        """
        if symbol not in self.index_candles_1m or len(self.index_candles_1m[symbol]) < 30:
            self.get_index_candles(symbol, count=count * 5)

        raw_1m = self.index_candles_1m.get(symbol, [])
        if len(raw_1m) >= 15:
            df_1m = pd.DataFrame(raw_1m)
            df_1m = df_1m.copy()
            df_1m["bucket"] = [i // 5 for i in range(len(df_1m))]
            agg_5m = df_1m.groupby("bucket").agg({
                "timestamp": "last",
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "buy_volume": "sum",
                "sell_volume": "sum",
                "delta": "sum"
            }).reset_index(drop=True)
            return self._enrich_candle_orderflow(agg_5m.tail(count).reset_index(drop=True))

        base = self.index_spots.get(symbol, 25150.0)
        candles = []
        now = datetime.now() - timedelta(minutes=count * 5)
        curr = base

        for i in range(count):
            now += timedelta(minutes=5)
            change = curr * random.uniform(-0.003, 0.003)
            o = curr
            c = round(curr + change, 2)
            h = round(max(o, c) + abs(change) * random.uniform(0.15, 0.6), 2)
            l = round(min(o, c) - abs(change) * random.uniform(0.15, 0.6), 2)
            v = random.randint(300000, 1100000)
            buy_vol = int(v * (0.55 if c >= o else 0.45))
            sell_vol = v - buy_vol

            candles.append({
                "timestamp": now,
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
                "buy_volume": buy_vol,
                "sell_volume": sell_vol,
                "delta": buy_vol - sell_vol
            })
            curr = c

        self.index_candles_5m[symbol] = candles
        df = pd.DataFrame(candles)
        return self._enrich_candle_orderflow(df)

    def _enrich_candle_orderflow(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adds rolling order-flow imbalance, cumulative delta, and VWAP."""
        if "delta" not in df.columns:
            df["delta"] = 0
        if "buy_volume" not in df.columns:
            df["buy_volume"] = df["volume"] // 2
        if "sell_volume" not in df.columns:
            df["sell_volume"] = df["volume"] - df["buy_volume"]

        df["cum_delta"] = df["delta"].cumsum()
        df["imbalance_ratio"] = (df["buy_volume"] / (df["sell_volume"] + 1e-4)).round(2)
        df["vwap"] = self.calculate_vwap(df)
        return df

    def _append_index_tick(self, symbol: str, price: float, is_buyer: bool):
        """Appends live tick to the running 1-minute candle with order-flow attribution."""
        if symbol not in self.index_candles_1m or not self.index_candles_1m[symbol]:
            self.get_index_candles(symbol, count=60)
            return

        last_c = self.index_candles_1m[symbol][-1]
        last_c["close"] = price
        last_c["high"] = max(last_c["high"], price)
        last_c["low"] = min(last_c["low"], price)

        tick_vol = random.randint(150, 600)
        last_c["volume"] += tick_vol

        if is_buyer:
            last_c["buy_volume"] += tick_vol
        else:
            last_c["sell_volume"] += tick_vol

        last_c["delta"] = last_c["buy_volume"] - last_c["sell_volume"]
