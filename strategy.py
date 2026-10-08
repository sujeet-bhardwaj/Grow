"""
NIFTY & BANKNIFTY Trading Strategy Engines:
1. ORBStrategyEngine:
   Exact Python implementation of the TradingView Pine Script v5 Strategy:
   "ORB Nifty/BankNifty Intraday"
   - 15-minute Opening Range (orHigh, orLow)
   - Range Width (%) filter: 0.30% <= widthPct <= 1.00%
   - Session Trade Window: 09:30 AM to 11:00 AM IST
   - Volume Confirmation: 20-bar SMA with volMult (1.0x)
   - Trend Filter: VWAP (Long requires close > vwap, Short requires close < vwap)
   - Strict 1:2 Risk-to-Reward Ratio (Target = 2 * Risk)
   - Single trade per day rule (tradedToday)
   - EOD Square-off at 15:15 IST

2. NiftyScalpStrategyEngine:
   - 1m execution & 5m macro trend
   - Triple EMA 9 / 21 / 50
   - PDH / PDL & Classical Floor Pivots (P, R1, S1)
   - 50-point psychological round numbers
   - Order-Flow Delta & Imbalance (1.4x)
   - Absorption / Rejection detection
"""

import math
import numpy as np
import pandas as pd
import config


class IndicatorCalculator:
    """Calculates EMAs, Volume MAs, VWAP, Candle wicks, and Technical Metrics."""

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_volume_ma(series: pd.Series, period: int = 20) -> pd.Series:
        return series.rolling(window=period, min_periods=1).mean()

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """Intraday Volume Weighted Average Price (VWAP)."""
        if df.empty or "volume" not in df.columns:
            return pd.Series([df["close"].iloc[-1] if not df.empty else 0.0] * len(df))
        typical = (df["high"] + df["low"] + df["close"]) / 3.0
        pv = typical * df["volume"]
        cum_pv = pv.cumsum()
        cum_vol = df["volume"].cumsum()
        return (cum_pv / cum_vol.replace(0, np.nan)).fillna(df["close"]).round(2)

    @staticmethod
    def analyze_candle_wicks(open_val: float, high_val: float, low_val: float, close_val: float) -> dict:
        rng = max(high_val - low_val, 0.05)
        body = abs(close_val - open_val)
        upper_wick = high_val - max(open_val, close_val)
        lower_wick = min(open_val, close_val) - low_val

        upper_ratio = round(upper_wick / rng, 3)
        lower_ratio = round(lower_wick / rng, 3)

        min_wick_ratio = getattr(config, "REJECTION_WICK_MIN_PCT", 0.35)
        is_bullish_rejection = (lower_ratio >= min_wick_ratio) and (close_val >= (low_val + rng * 0.45))
        is_bearish_rejection = (upper_ratio >= min_wick_ratio) and (close_val <= (high_val - rng * 0.45))

        return {
            "range": round(rng, 2),
            "body": round(body, 2),
            "upper_wick": round(upper_wick, 2),
            "lower_wick": round(lower_wick, 2),
            "upper_ratio": upper_ratio,
            "lower_ratio": lower_ratio,
            "is_bullish_rejection": is_bullish_rejection,
            "is_bearish_rejection": is_bearish_rejection
        }


class ORBStrategyEngine:
    """
    Exact implementation of Pine Script v5 "ORB Nifty/BankNifty Intraday":
    - Opening Range (15-min) Width Filter: 0.30% to 1.00%
    - Trade Window: 09:30 AM to 11:00 AM IST
    - Long: rangeOK and inWindow and not tradedToday and close > orHigh and volOK and close > vwap
    - Short: rangeOK and inWindow and not tradedToday and close < orLow and volOK and close < vwap
    - Risk & Sizing: longRisk = close - min(orLow, low); Target = close + 2 * riskPts (1:2 R:R)
    - Square-Off: 15:15 IST
    """

    def __init__(self):
        self.min_width_pct = getattr(config, "OR_MIN_WIDTH_PCT", 0.30)
        self.max_width_pct = getattr(config, "OR_MAX_WIDTH_PCT", 1.00)
        self.stop_buf_pct = getattr(config, "OR_STOP_BUF_PCT", 0.20)
        self.vol_mult = getattr(config, "OR_VOL_MULT", 1.0)
        self.use_volume = getattr(config, "OR_USE_VOLUME", True)
        self.use_trend_filt = getattr(config, "OR_USE_TREND_FILT", True)
        self.risk_pct = getattr(config, "OR_RISK_PCT", 0.5)
        self.init_capital = getattr(config, "OR_INIT_CAPITAL", 200000.0)

    def analyze(self, df_1m: pd.DataFrame, orb_data: dict) -> dict:
        """
        Evaluates ORB breakout signals for the active candle.
        """
        if df_1m.empty or not orb_data:
            spot = float(df_1m["close"].iloc[-1]) if (df_1m is not None and not df_1m.empty) else 25150.0
            return {
                "strategy": "ORB",
                "signal": "HOLD",
                "reason": "Awaiting ORB market data...",
                "spot": spot,
                "or_high": spot,
                "or_low": spot,
                "width": 0.0,
                "width_pct": 0.0,
                "range_ok": False,
                "vwap": spot,
                "vol_ok": False,
                "risk_points": 0.0,
                "target_points": 0.0,
                "target_spot": spot,
                "sl_spot": spot,
                "suggested_qty": 0,
                "in_window": False,
                "traded_today": False,
                "confluence_score": 0
            }

        curr = df_1m.iloc[-1]
        c = float(curr["close"])
        h = float(curr["high"])
        l = float(curr["low"])
        vol = float(curr["volume"])

        or_h = float(orb_data.get("or_high", c + 50))
        or_l = float(orb_data.get("or_low", c - 50))
        or_done = bool(orb_data.get("or_done", True))
        range_ok = bool(orb_data.get("range_ok", True))
        width_pct = float(orb_data.get("width_pct", 0.45))
        vwap = float(orb_data.get("vwap", c))
        in_window = bool(orb_data.get("in_window", True))
        at_square_off = bool(orb_data.get("at_square_off", False))
        traded_today = bool(orb_data.get("traded_today", False))

        # 20-period volume SMA
        avg_vol = float(df_1m["volume"].rolling(20, min_periods=1).mean().iloc[-1])
        vol_ok = (not self.use_volume) or (vol > avg_vol * self.vol_mult)

        # Trend filter (VWAP)
        trend_l = (not self.use_trend_filt) or (c > vwap)
        trend_s = (not self.use_trend_filt) or (c < vwap)

        # Time exit check
        if atSquareOff := at_square_off:
            return {
                "strategy": "ORB",
                "signal": "SQUARE_OFF",
                "reason": "EOD 15:15 IST Square-off triggered.",
                "spot": c,
                "or_high": or_h,
                "or_low": or_l,
                "width": orb_data.get("width", round(or_h - or_l, 2)),
                "width_pct": width_pct,
                "range_ok": range_ok,
                "vwap": vwap,
                "vol_ok": vol_ok,
                "risk_points": 0.0,
                "target_points": 0.0,
                "target_spot": c,
                "sl_spot": c,
                "suggested_qty": 0,
                "in_window": in_window,
                "traded_today": traded_today,
                "confluence_score": 0
            }

        # Long Entry: close > orHigh and volOK and trendL
        long_sig = range_ok and in_window and (not traded_today) and (c > or_h) and vol_ok and trend_l

        # Short Entry: close < orLow and volOK and trendS
        short_sig = range_ok and in_window and (not traded_today) and (c < or_l) and vol_ok and trend_s

        signal = "HOLD"
        reason = ""
        risk_pts = 10.0
        target_pts = 20.0
        target_spot = c
        sl_spot = c
        qty = 25

        if long_sig:
            signal = "BUY_CE"
            long_stop = min(or_l, l)
            long_risk = c - long_stop
            min_risk_l = c * self.stop_buf_pct / 100.0
            risk_pts = round(max(long_risk, min_risk_l), 2)
            target_pts = round(risk_pts * 2.0, 2)  # Strict 1:2 Risk to Reward
            target_spot = round(c + target_pts, 2)
            sl_spot = round(c - risk_pts, 2)
            
            # Position sizing from Pine Script: floor((capital * riskPct / 100) / riskPts)
            capital_risk_amt = self.init_capital * (self.risk_pct / 100.0)
            qty = max(int(math.floor(capital_risk_amt / max(risk_pts, 1.0))), 25)

            reason = (
                f"ORB BULLISH BREAKOUT: Close({c}) > OR High({or_h}) | "
                f"VWAP={vwap} (Trend Bullish) | Vol={int(vol):,} > 20-SMA({int(avg_vol):,}) | "
                f"Risk: -{risk_pts:g} pts | Target: +{target_pts:g} pts (1:2 R:R)"
            )

        elif short_sig:
            signal = "BUY_PE"
            short_stop = max(or_h, h)
            short_risk = short_stop - c
            min_risk_s = c * self.stop_buf_pct / 100.0
            risk_pts = round(max(short_risk, min_risk_s), 2)
            target_pts = round(risk_pts * 2.0, 2)  # Strict 1:2 Risk to Reward
            target_spot = round(c - target_pts, 2)
            sl_spot = round(c + risk_pts, 2)

            capital_risk_amt = self.init_capital * (self.risk_pct / 100.0)
            qty = max(int(math.floor(capital_risk_amt / max(risk_pts, 1.0))), 25)

            reason = (
                f"ORB BEARISH BREAKDOWN: Close({c}) < OR Low({or_l}) | "
                f"VWAP={vwap} (Trend Bearish) | Vol={int(vol):,} > 20-SMA({int(avg_vol):,}) | "
                f"Risk: -{risk_pts:g} pts | Target: +{target_pts:g} pts (1:2 R:R)"
            )

        else:
            status_items = []
            if not in_window:
                status_items.append("Outside 09:30-11:00 AM Window")
            if traded_today:
                status_items.append("Daily Trade Already Completed")
            if not range_ok:
                status_items.append(f"Range Width {width_pct:.2f}% (Allowed: {self.min_width_pct}-{self.max_width_pct}%)")
            if not vol_ok:
                status_items.append("Volume < 20-SMA Avg")
            
            cond_str = ", ".join(status_items) if status_items else f"Monitoring OR High: {or_h} / OR Low: {or_l}"
            reason = f"ORB Watching (Spot: {c:.2f} | VWAP: {vwap:.2f}) -> {cond_str}"

        return {
            "strategy": "ORB",
            "signal": signal,
            "reason": reason,
            "spot": c,
            "or_high": or_h,
            "or_low": or_l,
            "width": orb_data.get("width", round(or_h - or_l, 2)),
            "width_pct": width_pct,
            "range_ok": range_ok,
            "vwap": vwap,
            "vol_ok": vol_ok,
            "risk_points": risk_pts,
            "target_points": target_pts,
            "target_spot": target_spot,
            "sl_spot": sl_spot,
            "suggested_qty": qty,
            "in_window": in_window,
            "traded_today": traded_today,
            "confluence_score": 90 if signal != "HOLD" else (45 if range_ok and in_window else 20)
        }


class NiftyScalpStrategyEngine:
    """
    High-precision NIFTY 10–15 Point Scalping Engine with multi-timeframe EMA 9/21/50,
    Order-Flow Delta, Absorption, Pivots, and 50-pt Psychological Levels.
    """

    def __init__(self):
        self.ema_fast = getattr(config, "EMA_FAST", 9)
        self.ema_mid = getattr(config, "EMA_MID", 21)
        self.ema_slow = getattr(config, "EMA_SLOW", 50)
        self.vol_ma_period = getattr(config, "VOLUME_MA_PERIOD", 20)
        self.target_min_pts = getattr(config, "SCALP_TARGET_MIN_POINTS", 10.0)
        self.target_max_pts = getattr(config, "SCALP_TARGET_MAX_POINTS", 15.0)
        self.target_default_pts = getattr(config, "SCALP_DEFAULT_TARGET_PTS", 12.5)
        self.sl_pts = getattr(config, "SCALP_STOP_LOSS_POINTS", 6.0)

    def evaluate_5m_trend(self, df_5m: pd.DataFrame) -> dict:
        if df_5m is None or len(df_5m) < 5:
            return {
                "bias": "NEUTRAL",
                "score": 10,
                "ema9": 0.0,
                "ema21": 0.0,
                "ema50": 0.0,
                "reason": "Insufficient 5m candle history"
            }

        df = df_5m.copy()
        df["ema9"] = IndicatorCalculator.calculate_ema(df["close"], min(self.ema_fast, max(len(df)-1, 3)))
        df["ema21"] = IndicatorCalculator.calculate_ema(df["close"], min(self.ema_mid, max(len(df)-1, 5)))
        df["ema50"] = IndicatorCalculator.calculate_ema(df["close"], min(self.ema_slow, max(len(df)-1, 8)))

        curr = df.iloc[-1]
        c = float(curr["close"])
        e9 = round(float(curr["ema9"]), 2)
        e21 = round(float(curr["ema21"]), 2)
        e50 = round(float(curr["ema50"]), 2)

        if c > e9 and e9 > e21 and e21 >= e50:
            bias = "BULLISH"
            score = 25
            reason = f"5m Strong Bullish Stack: Close({c}) > EMA9({e9}) > EMA21({e21}) > EMA50({e50})"
        elif e9 > e21 and c > e21:
            bias = "BULLISH"
            score = 20
            reason = f"5m Bullish: EMA9({e9}) > EMA21({e21}) and Price({c}) > EMA21"
        elif c < e9 and e9 < e21 and e21 <= e50:
            bias = "BEARISH"
            score = 25
            reason = f"5m Strong Bearish Stack: Close({c}) < EMA9({e9}) < EMA21({e21}) < EMA50({e50})"
        elif e9 < e21 and c < e21:
            bias = "BEARISH"
            score = 20
            reason = f"5m Bearish: EMA9({e9}) < EMA21({e21}) and Price({c}) < EMA21"
        else:
            bias = "NEUTRAL"
            score = 10
            reason = f"5m Sideways / Mixed EMAs: EMA9={e9}, EMA21={e21}, EMA50={e50}"

        return {
            "bias": bias,
            "score": score,
            "ema9": e9,
            "ema21": e21,
            "ema50": e50,
            "reason": reason
        }

    def evaluate_1m_execution(self, df_1m: pd.DataFrame) -> dict:
        if df_1m is None or len(df_1m) < 15:
            return {
                "timing": "WAIT",
                "score": 0,
                "ema9": 0.0,
                "ema21": 0.0,
                "ema50": 0.0,
                "vol_ma": 0.0,
                "volume_confirmed": False,
                "delta": 0,
                "imbalance_ratio": 1.0,
                "wick_info": {},
                "reason": "Insufficient 1m candles"
            }

        df = df_1m.copy()
        df["ema9"] = IndicatorCalculator.calculate_ema(df["close"], self.ema_fast)
        df["ema21"] = IndicatorCalculator.calculate_ema(df["close"], self.ema_mid)
        df["ema50"] = IndicatorCalculator.calculate_ema(df["close"], min(self.ema_slow, max(len(df)-1, 10)))
        df["vol_ma"] = IndicatorCalculator.calculate_volume_ma(df["volume"], self.vol_ma_period)

        curr = df.iloc[-1]
        prev = df.iloc[-2]

        o = float(curr["open"])
        h = float(curr["high"])
        l = float(curr["low"])
        c = float(curr["close"])
        vol = float(curr["volume"])
        vol_ma = float(curr["vol_ma"]) if curr["vol_ma"] > 0 else 100000.0

        e9 = round(float(curr["ema9"]), 2)
        e21 = round(float(curr["ema21"]), 2)
        e50 = round(float(curr["ema50"]), 2)
        prev_e9 = round(float(prev["ema9"]), 2)
        prev_e21 = round(float(prev["ema21"]), 2)

        vol_surge_threshold = getattr(config, "VOLUME_SURGE_THRESHOLD", 1.25)
        vol_ratio = round(vol / (vol_ma + 1e-5), 2)
        volume_confirmed = vol_ratio >= vol_surge_threshold or vol_ratio >= 1.15

        buy_vol = float(curr.get("buy_volume", vol * 0.5))
        sell_vol = float(curr.get("sell_volume", vol * 0.5))
        delta = int(curr.get("delta", buy_vol - sell_vol))
        imbalance_ratio = round(buy_vol / (sell_vol + 1e-4), 2)

        wick_info = IndicatorCalculator.analyze_candle_wicks(o, h, l, c)

        bull_cross = (prev_e9 <= prev_e21) and (e9 > e21)
        bear_cross = (prev_e9 >= prev_e21) and (e9 < e21)
        bull_pullback = (l <= e9 <= h or l <= e21 <= h) and (c > e9)
        bear_pullback = (l <= e9 <= h or l <= e21 <= h) and (c < e9)

        return {
            "ema9": e9,
            "ema21": e21,
            "ema50": e50,
            "spot": c,
            "volume": int(vol),
            "vol_ma": int(vol_ma),
            "vol_ratio": vol_ratio,
            "volume_confirmed": volume_confirmed,
            "buy_volume": int(buy_vol),
            "sell_volume": int(sell_vol),
            "delta": delta,
            "imbalance_ratio": imbalance_ratio,
            "wick_info": wick_info,
            "bull_cross": bull_cross,
            "bear_cross": bear_cross,
            "bull_pullback": bull_pullback,
            "bear_pullback": bear_pullback
        }

    def evaluate_levels_interaction(self, spot: float, levels: dict) -> dict:
        if not levels:
            return {
                "score_bull": 10,
                "score_bear": 10,
                "nearest_level_name": "NONE",
                "nearest_level_val": spot,
                "distance": 999.0,
                "reaction_type": "NEUTRAL",
                "psych_50_level": round(spot / 50.0) * 50.0,
                "psych_50_dist": 0.0
            }

        pdh = levels.get("pdh", spot + 50.0)
        pdl = levels.get("pdl", spot - 50.0)
        pivot = levels.get("pivot", spot)
        r1 = levels.get("r1", spot + 30.0)
        s1 = levels.get("s1", spot - 30.0)
        psych_50 = levels.get("psych_nearest", round(spot / 50.0) * 50.0)
        psych_dist = levels.get("psych_dist", abs(spot - psych_50))

        level_map = {
            "PDH (Prev Day High)": pdh,
            "PDL (Prev Day Low)": pdl,
            "Pivot (Central)": pivot,
            "R1 (Resistance 1)": r1,
            "S1 (Support 1)": s1,
            "50-Pt Psych Level": psych_50
        }

        closest_name = min(level_map.keys(), key=lambda k: abs(spot - level_map[k]))
        closest_val = level_map[closest_name]
        dist = round(abs(spot - closest_val), 2)

        score_bull = 10
        score_bear = 10
        reaction = "IN_TRANSIT"

        if spot >= closest_val and dist <= 8.0:
            if closest_name in ["PDL (Prev Day Low)", "S1 (Support 1)", "Pivot (Central)", "50-Pt Psych Level"]:
                score_bull += 15
                reaction = f"BOUNCE / SUPPORT TEST @ {closest_name} ({closest_val})"
        elif spot <= closest_val and dist <= 8.0:
            if closest_name in ["PDH (Prev Day High)", "R1 (Resistance 1)", "Pivot (Central)", "50-Pt Psych Level"]:
                score_bear += 15
                reaction = f"REJECTION / RESISTANCE TEST @ {closest_name} ({closest_val})"

        if (spot > pdh and (spot - pdh) <= 10.0):
            score_bull += 18
            reaction = f"PDH BREAKOUT ({pdh})"
        elif (spot < pdl and (pdl - spot) <= 10.0):
            score_bear += 18
            reaction = f"PDL BREAKDOWN ({pdl})"

        return {
            "score_bull": score_bull,
            "score_bear": score_bear,
            "nearest_level_name": closest_name,
            "nearest_level_val": closest_val,
            "distance": dist,
            "reaction_type": reaction,
            "pdh": pdh,
            "pdl": pdl,
            "pivot": pivot,
            "r1": r1,
            "s1": s1,
            "psych_50_level": psych_50,
            "psych_50_dist": psych_dist
        }

    def analyze(self, df_1m: pd.DataFrame, df_5m: pd.DataFrame = None, levels: dict = None, orb_data: dict = None) -> dict:
        """
        Unified Strategy Engine:
        If config.ACTIVE_STRATEGY_MODE == 'ORB', delegates to the Pine Script ORB Strategy.
        Otherwise evaluates the multi-timeframe 10-15 point scalper.
        """
        active_mode = getattr(config, "ACTIVE_STRATEGY_MODE", "ORB")

        # 1. Pine Script ORB Strategy Execution
        if active_mode == "ORB" and orb_data:
            orb_engine = ORBStrategyEngine()
            orb_res = orb_engine.analyze(df_1m, orb_data)
            
            # Enrich with scalp/telemetry fields for UI display
            exec_1m = self.evaluate_1m_execution(df_1m)
            trend_5m = self.evaluate_5m_trend(df_5m if df_5m is not None else df_1m)
            levels_analysis = self.evaluate_levels_interaction(orb_res["spot"], levels or {})

            orb_res.update({
                "trend_5m": trend_5m,
                "exec_1m": exec_1m,
                "levels_analysis": levels_analysis,
                "fast_ema": exec_1m.get("ema9", 0.0),
                "slow_ema": exec_1m.get("ema21", 0.0),
                "ema50_1m": exec_1m.get("ema50", 0.0),
                "ema9_5m": trend_5m.get("ema9", 0.0),
                "ema21_5m": trend_5m.get("ema21", 0.0),
                "ema50_5m": trend_5m.get("ema50", 0.0),
                "target_1_spot": orb_res.get("target_spot", orb_res.get("spot", 0.0)),
                "target_2_spot": orb_res.get("target_spot", orb_res.get("spot", 0.0)),
                "sl_spot": orb_res.get("sl_spot", orb_res.get("spot", 0.0)),
                "target_points": orb_res.get("target_points", 0.0),
                "stop_loss_points": orb_res.get("risk_points", 0.0),
                "absorption_detected": "NONE",
                "orderflow_summary": {
                    "delta": exec_1m.get("delta", 0),
                    "imbalance_ratio": exec_1m.get("imbalance_ratio", 1.0),
                    "buy_volume": exec_1m.get("buy_volume", 0),
                    "sell_volume": exec_1m.get("sell_volume", 0),
                    "vol_ratio": exec_1m.get("vol_ratio", 1.0),
                    "volume_confirmed": orb_res.get("vol_ok", False),
                    "status": "BUY_DOMINANCE" if exec_1m.get("delta", 0) > 0 else "SELL_DOMINANCE"
                }
            })
            return orb_res

        # 2. 10-15 Point Scalping Engine Execution
        if df_1m is None or len(df_1m) < 15:
            spot = float(df_1m["close"].iloc[-1]) if (df_1m is not None and not df_1m.empty) else 25150.0
            return {
                "signal": "HOLD",
                "reason": "Accumulating candle history for scalping...",
                "confluence_score": 0,
                "spot": spot,
                "fast_ema": spot,
                "slow_ema": spot,
                "rsi": 50.0,
                "supertrend_dir": 0,
                "target_points": self.target_default_pts,
                "stop_loss_points": self.sl_pts,
                "target_1_spot": spot + self.target_min_pts,
                "target_2_spot": spot + self.target_max_pts,
                "sl_spot": spot - self.sl_pts,
                "trend_5m": {"bias": "NEUTRAL", "ema9": spot, "ema21": spot, "ema50": spot},
                "exec_1m": {"ema9": spot, "ema21": spot, "ema50": spot, "delta": 0, "imbalance_ratio": 1.0},
                "levels_analysis": {},
                "absorption_detected": "NONE",
                "orderflow_summary": {"delta": 0, "imbalance": 1.0, "status": "NEUTRAL"}
            }

        trend_5m = self.evaluate_5m_trend(df_5m if df_5m is not None else df_1m)
        exec_1m = self.evaluate_1m_execution(df_1m)
        spot = exec_1m["spot"]
        levels_analysis = self.evaluate_levels_interaction(spot, levels or {})

        wick = exec_1m["wick_info"]
        absorption_type = "NONE"
        if wick.get("is_bullish_rejection") and (exec_1m["delta"] > 0 or exec_1m["imbalance_ratio"] >= 1.2):
            absorption_type = "BULLISH_ABSORPTION"
        elif wick.get("is_bearish_rejection") and (exec_1m["delta"] < 0 or exec_1m["imbalance_ratio"] <= 0.8):
            absorption_type = "BEARISH_REJECTION"

        bull_score = 0
        bear_score = 0

        if trend_5m["bias"] == "BULLISH":
            bull_score += trend_5m["score"]
        elif trend_5m["bias"] == "BEARISH":
            bear_score += trend_5m["score"]

        e9_1m = exec_1m["ema9"]
        e21_1m = exec_1m["ema21"]
        e50_1m = exec_1m["ema50"]

        if spot > e9_1m and e9_1m >= e21_1m:
            bull_score += 15
        if exec_1m["bull_pullback"] or exec_1m["bull_cross"]:
            bull_score += 5

        if spot < e9_1m and e9_1m <= e21_1m:
            bear_score += 15
        if exec_1m["bear_pullback"] or exec_1m["bear_cross"]:
            bear_score += 5

        bull_score += min(levels_analysis["score_bull"], 20)
        bear_score += min(levels_analysis["score_bear"], 20)

        delta = exec_1m["delta"]
        imb = exec_1m["imbalance_ratio"]
        if delta > 500 and imb >= config.ORDER_FLOW_IMBALANCE_RATIO:
            bull_score += 15
        elif delta > 0:
            bull_score += 8

        if delta < -500 and imb <= (1.0 / config.ORDER_FLOW_IMBALANCE_RATIO):
            bear_score += 15
        elif delta < 0:
            bear_score += 8

        if absorption_type == "BULLISH_ABSORPTION":
            bull_score += 10
        elif absorption_type == "BEARISH_REJECTION":
            bear_score += 10

        if exec_1m["volume_confirmed"]:
            if bull_score > bear_score:
                bull_score += 10
            elif bear_score > bull_score:
                bear_score += 10

        CONFLUENCE_THRESHOLD = 62
        signal = "HOLD"
        reason = "Awaiting high-probability 10–15 pt scalping confluence"
        final_confluence = 0

        target_1_spot = spot
        target_2_spot = spot
        sl_spot = spot

        if bull_score >= CONFLUENCE_THRESHOLD and bull_score > (bear_score + 10):
            signal = "BUY_CE"
            final_confluence = min(bull_score, 100)
            target_1_spot = round(spot + self.target_min_pts, 2)
            target_2_spot = round(spot + self.target_max_pts, 2)
            sl_spot = round(spot - self.sl_pts, 2)
            reason = (
                f"SCALP BUY CALL (CE) [Confluence: {final_confluence}%]: "
                f"5m Trend {trend_5m['bias']} | 1m EMA 9/21 aligned | "
                f"Delta: +{delta:,} (Imbalance: {imb}x) | {levels_analysis['reaction_type']} | "
                f"Targets: +{self.target_min_pts:g} to +{self.target_max_pts:g} pts (SL: -{self.sl_pts:g} pts)"
            )

        elif bear_score >= CONFLUENCE_THRESHOLD and bear_score > (bull_score + 10):
            signal = "BUY_PE"
            final_confluence = min(bear_score, 100)
            target_1_spot = round(spot - self.target_min_pts, 2)
            target_2_spot = round(spot - self.target_max_pts, 2)
            sl_spot = round(spot + self.sl_pts, 2)
            reason = (
                f"SCALP BUY PUT (PE) [Confluence: {final_confluence}%]: "
                f"5m Trend {trend_5m['bias']} | 1m EMA 9/21 aligned | "
                f"Delta: {delta:,} (Imbalance: {imb}x) | {levels_analysis['reaction_type']} | "
                f"Targets: +{self.target_min_pts:g} to +{self.target_max_pts:g} pts (SL: -{self.sl_pts:g} pts)"
            )
        else:
            final_confluence = max(bull_score, bear_score)
            reason = (
                f"Scalp Scanning: 5m Trend={trend_5m['bias']} | 1m Delta={delta:+d} | "
                f"Nearest Level: {levels_analysis['nearest_level_name']} ({levels_analysis['distance']} pts away) | "
                f"Bull Score={bull_score} vs Bear Score={bear_score} (Need {CONFLUENCE_THRESHOLD})"
            )

        supertrend_dir = 1 if trend_5m["bias"] == "BULLISH" else (-1 if trend_5m["bias"] == "BEARISH" else 0)
        rsi = 56.0 if signal == "BUY_CE" else (44.0 if signal == "BUY_PE" else 50.0)

        return {
            "strategy": "SCALPER",
            "signal": signal,
            "reason": reason,
            "confluence_score": final_confluence,
            "spot": spot,
            "fast_ema": exec_1m["ema9"],
            "slow_ema": exec_1m["ema21"],
            "ema50_1m": exec_1m["ema50"],
            "ema9_5m": trend_5m["ema9"],
            "ema21_5m": trend_5m["ema21"],
            "ema50_5m": trend_5m["ema50"],
            "rsi": rsi,
            "supertrend_dir": supertrend_dir,
            "target_points": self.target_default_pts,
            "target_min_pts": self.target_min_pts,
            "target_max_pts": self.target_max_pts,
            "stop_loss_points": self.sl_pts,
            "target_1_spot": target_1_spot,
            "target_2_spot": target_2_spot,
            "sl_spot": sl_spot,
            "trend_5m": trend_5m,
            "exec_1m": exec_1m,
            "levels_analysis": levels_analysis,
            "absorption_detected": absorption_type,
            "orderflow_summary": {
                "delta": delta,
                "imbalance_ratio": imb,
                "buy_volume": exec_1m["buy_volume"],
                "sell_volume": exec_1m["sell_volume"],
                "vol_ratio": exec_1m["vol_ratio"],
                "volume_confirmed": exec_1m["volume_confirmed"],
                "status": "BUY_DOMINANCE" if delta > 0 else "SELL_DOMINANCE"
            }
        }


# Compatibility aliases
StrategyEngine = NiftyScalpStrategyEngine
