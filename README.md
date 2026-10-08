# Groww NIFTY 10–15 Point Scalping Bot (F&O Edition)

An automated, institutional-grade algorithmic scalping bot integrated with the **Groww Trading API (`growwapi`)** specifically engineered for **NIFTY 10–15 point scalping** (and BANKNIFTY) on NSE Futures & Options (F&O).

---

## ⚡ NIFTY 10–15 Point Scalp Entry Setup

The engine implements a multi-factor institutional confluence framework:

1. **Multi-Timeframe Architecture:**
   - **5-Minute Chart for Macro Trend:** Evaluates higher timeframe direction using **Triple EMA 9 / 21 / 50** alignment and market structure.
   - **1-Minute Chart for Micro Timing:** Determines exact execution entry timing, pullbacks to EMA 9/21, and rejection triggers.

2. **Moving Averages (EMA 9 / 21 / 50):**
   - **Bullish Confluence:** Close > EMA 9 > EMA 21 > EMA 50 on 5-minute chart with 1-minute EMA 9/21 pullback or bounce.
   - **Bearish Confluence:** Close < EMA 9 < EMA 21 < EMA 50 on 5-minute chart with 1-minute EMA 9/21 pullback or rejection.

3. **Key Price Levels:**
   - **Previous Day High / Low (PDH / PDL):** Critical institutional breakout and bounce levels.
   - **Floor Pivots (Pivot / R1 / S1):** Standard classical pivot points computed dynamically for intraday support/resistance confluence.

4. **Psychological Round Levels (Every 50 Points):**
   - In NIFTY, every 50 points (e.g. 25000, 25050, 25100, 25150, 25200) represents key institutional open interest clusters and round-number liquidity magnets.
   - The bot measures real-time distance and detects bounces or breakouts through round levels.

5. **Order-Flow Imbalance + Volume Delta:**
   - Real-time candle **Volume Delta** ($\Delta = \text{Aggressive Buys} - \text{Aggressive Sells}$).
   - **Order-Flow Imbalance Ratio:** Triggers only when aggressive buyers or sellers outnumber the other side by $\ge 1.4\times$.

6. **Absorption / Rejection Detection:**
   - **Bullish Absorption at Support:** Long lower wick ($\ge 35\%$ of candle range) at PDL, S1, Pivot, or 50-pt round level with positive delta absorption.
   - **Bearish Rejection at Resistance:** Long upper wick ($\ge 35\%$ of candle range) at PDH, R1, Pivot, or 50-pt round level with negative delta rejection.

7. **Volume Confirmation:**
   - Compares 1-minute volume against a **20-period Volume Moving Average (VMA)**.
   - Confirms institutional participation when volume exceeds $\ge 1.25\times$ of the 20 VMA.

8. **Scalp Profit Targets & Risk Management:**
   - **Scalp Target:** **10 to 15 Index Points** (~6 to 9 Option Premium Points on ATM strikes with Delta ~0.52).
   - **Scalp Stop-Loss:** **6 Index Points** (~3 Option Premium Points).
   - **Trailing Breakeven Stop:** Once trade gains $+7$ index points, Stop-Loss is automatically moved to Breakeven for a risk-free scalp.

---

## 🌅 Pine Script v5 Opening Range Breakout (ORB) Strategy

The system natively runs the **TradingView Pine Script v5 ORB Intraday Strategy**:

1. **15-Minute Opening Range (09:15 to 09:30 AM IST):**
   - Automatically tracks the highest high (`orHigh`) and lowest low (`orLow`) of the opening 15-minute candle.
2. **Range Width Filter:**
   - Validates that the 15-minute range width is healthy: `0.30% <= widthPct <= 1.00%`.
3. **Execution Trade Window:**
   - Orders are restricted strictly to **09:30 AM to 11:00 AM IST**.
4. **Intraday Trend & Volume Confirmation:**
   - **Trend Filter:** Price must be above Intraday VWAP for Longs (`close > vwap`), and below VWAP for Shorts (`close < vwap`).
   - **Volume Filter:** Breakout candle volume must exceed the 20-period Volume SMA (`volume > avgVol * 1.0`).
5. **Exact 1:2 Risk-to-Reward Ratio:**
   - **Stop-Loss:** Anchored to the opposite side of the Opening Range (`orLow` for Long, `orHigh` for Short).
   - **Target:** Automatically set to **2x Risk** (`limit = close + 2 * riskPts`).
6. **Strict 1 Trade Per Day & EOD Square-Off:**
   - Single trade execution per day (`tradedToday = true`) to prevent overtrading.
   - Mandatory Auto Square-Off at **03:15 PM (15:15 IST)**.

---

## 🌐 Launch the Scalping Terminal in Google Chrome

### Method 1: Double-click Launcher
Double-click [run_chrome_dashboard.bat](file:///c:/Users/Dell/Desktop/Grow/run_chrome_dashboard.bat).

### Method 2: From Terminal
```powershell
py -3.11 app.py
```
> Chrome will automatically open to: **`http://127.0.0.1:5000`**

---

## 🔐 Web Terminal Login Credentials

- **URL:** `http://127.0.0.1:5000/login`
- **Username:** `admin` (or configured via `DASHBOARD_USERNAME`)
- **Password:** `groww123` (or configured via `DASHBOARD_PASSWORD`)
- *Feature:* Quick 1-click **"⚡ Quick Auto-Login"** button is also available on the login page!

---

## 📁 Project Architecture

```
Grow/
├── app.py                   # Live Scalping Web Server, Auth, & Scanner Loop
├── templates/
│   ├── index.html           # NIFTY 10–15 Pt Scalping Dashboard (Telemetry, Levels & Delta)
│   └── login.html           # Dark-Mode Terminal Login Screen
├── config.py                # Scalp settings (10-15 pt targets, 50-pt psych step, EMAs)
├── auth.py                  # Groww API token manager & session authenticator
├── market_data.py           # 1m/5m candles, Order-Flow Delta, PDH/PDL, Pivots, Psych levels
├── strategy.py              # NiftyScalpStrategyEngine (Multi-TF, EMAs, Order Flow, Absorption)
├── risk_manager.py          # 10–15 pt targets, Delta calculation, Trailing SL to Breakeven
├── execution.py             # Order router (Paper simulator vs. Groww Live F&O API)
├── paper_trader.py          # Virtual option trading ledger & points capture recorder
├── main.py                  # Direct terminal/console scalper runner
├── run_chrome_dashboard.bat # 1-click launcher for Google Chrome Dashboard
├── run_bot.bat              # 1-click launcher for Terminal mode
├── requirements.txt         # Project Python dependencies
├── .env                     # Secure Groww API credentials
└── .groww_token.json        # Active Groww session token cache
```
