import os
from dotenv import load_dotenv

load_dotenv()

# ==============================================================================
# GROWW FUTURES & OPTIONS (F&O) TRADING BOT CONFIGURATION
# ==============================================================================

BROKER = "GROWW"
SEGMENT = "FNO"  # Futures & Options

# Mode: "PAPER" (Virtual simulation with Rs. 1,00,000) or "LIVE" (Real Groww F&O orders)
TRADING_MODE = os.getenv("TRADING_MODE", "PAPER")

# ------------------------------------------------------------------------------
# Dashboard Authentication Credentials
# ------------------------------------------------------------------------------
DASHBOARD_USERNAME = os.getenv("DASHBOARD_USERNAME", "admin")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "groww123")
SECRET_KEY = os.getenv("SECRET_KEY", "groww-algo-secret-token-key-2026")

# ------------------------------------------------------------------------------
# Groww API Credentials
# ------------------------------------------------------------------------------
GROWW_API_KEY = os.getenv("GROWW_API_KEY", "")
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET", "")
GROWW_VENDOR_KEY = os.getenv("GROWW_VENDOR_KEY", "")
GROWW_USER_ACCOUNT_ID = os.getenv("GROWW_USER_ACCOUNT_ID", "")
GROWW_ACCESS_TOKEN = os.getenv("GROWW_ACCESS_TOKEN", GROWW_API_KEY)

# ------------------------------------------------------------------------------
# F&O Watchlist Indices (Underlying Assets)
# ------------------------------------------------------------------------------
WATCHLIST_INDICES = [
    {
        "symbol": "NIFTY",
        "name": "Nifty 50 Index",
        "lot_size": 25,             # 25 shares per lot
        "strike_step": 50,          # Strikes spaced by 50 points (25000, 25050, 25100)
        "base_spot": 25150.0,       # Base spot level for simulation
        "default_premium": 140.0    # Typical ATM option premium
    },
    {
        "symbol": "BANKNIFTY",
        "name": "Nifty Bank Index",
        "lot_size": 15,             # 15 shares per lot
        "strike_step": 100,         # Strikes spaced by 100 points (51400, 51500, 51600)
        "base_spot": 51600.0,       # Base spot level for simulation
        "default_premium": 280.0    # Typical ATM option premium
    }
]

# ------------------------------------------------------------------------------
# NIFTY 10–15 POINT SCALPING BOT STRATEGY PARAMETERS
# ------------------------------------------------------------------------------
TIMEFRAME_EXECUTION = "1minute"   # 1-minute chart for execution timing & triggers
TIMEFRAME_TREND = "5minute"       # 5-minute chart for higher timeframe trend bias
TIMEFRAME = TIMEFRAME_EXECUTION   # Default execution interval

# Triple Exponential Moving Averages (EMA 9 / 21 / 50)
EMA_FAST = 9
EMA_MID = 21
EMA_SLOW = 50
FAST_EMA_PERIOD = EMA_FAST
SLOW_EMA_PERIOD = EMA_MID

# Index Scalp Point Targets & Stop-Loss
SCALP_TARGET_MIN_POINTS = 10.0    # 10 index points minimum scalp target
SCALP_TARGET_MAX_POINTS = 15.0    # 15 index points maximum scalp target
SCALP_DEFAULT_TARGET_PTS = 12.5   # Default 12.5 index points scalp target
SCALP_STOP_LOSS_POINTS = 6.0      # Tight 6 index points SL (Risk:Reward ~ 1:2)
TRAIL_BREAKEVEN_POINTS = 7.0      # Move SL to Breakeven once trade gains +7 index points

# Psychological Levels (Every 50 points in NIFTY)
PSYCH_LEVEL_STEP = 50             # 25000, 25050, 25100, 25150, 25200...
PSYCH_PROXIMITY_THRESHOLD = 8.0   # Level considered in play within 8 points

# Order-Flow Imbalance & Delta
ORDER_FLOW_IMBALANCE_RATIO = 1.4  # Buy/Sell volume ratio for imbalance confirmation
ORDER_FLOW_MIN_DELTA = 1500       # Minimum positive/negative delta for momentum confirmation

# Absorption & Rejection Thresholds
REJECTION_WICK_MIN_PCT = 0.35     # Wick must be >= 35% of total candle range
ABSORPTION_MIN_VOLUME_MULT = 1.2  # Volume multiple for absorption at support/resistance

# Volume Confirmation
VOLUME_MA_PERIOD = 20             # 20-period Volume Moving Average
VOLUME_SURGE_THRESHOLD = 1.25     # Volume must be >= 1.25x of 20 VMA for confirmation

# Fallback / General Indicator Parameters
RSI_PERIOD = 14
RSI_BULLISH_MIN = 48.0
RSI_BEARISH_MAX = 52.0
SUPERTREND_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0

# ------------------------------------------------------------------------------
# Scalp Options Risk Management Rules
# ------------------------------------------------------------------------------
INITIAL_PAPER_CAPITAL = float(os.getenv("INITIAL_PAPER_CAPITAL", "100000.0"))  # Rs. 1,00,000 Virtual Funds
MAX_LOTS_PER_TRADE = 2             # Maximum lots per position (e.g., 2 lots = 50 Qty in NIFTY)
MAX_CONCURRENT_POSITIONS = 1       # Maximum simultaneous open positions
MAX_DAILY_LOSS = 5000.0            # Max daily loss circuit breaker (Rs. 5,000)
ESTIMATED_ATM_DELTA = 0.52         # Delta ~0.52 (10-15 index pts ~= 5.2 - 7.8 option pts)
OPTION_SCALP_TARGET_PTS = 7.0      # ~7 points profit target on option premium
OPTION_SCALP_SL_PTS = 3.5          # ~3.5 points stop loss on option premium
OPTION_STOP_LOSS_PCT = 20.0        # Fallback % Stop Loss
# ------------------------------------------------------------------------------
# PINE SCRIPT ORB (OPENING RANGE BREAKOUT) INTRADAY PARAMETERS
# ------------------------------------------------------------------------------
OR_MINUTES = 15                  # 15 minutes Opening Range (09:15 to 09:30 AM IST)
SESSION_START = "09:15"          # Market session start
TRADE_WINDOW_START = "09:30"     # Trade window start (09:30 AM IST)
TRADE_WINDOW_END = "11:00"       # Trade window end (11:00 AM IST)
SQUARE_OFF_TIME = "15:15"        # Auto Square-off time (03:15 PM IST)
OR_MIN_WIDTH_PCT = 0.30          # Minimum range width: 0.30% of spot
OR_MAX_WIDTH_PCT = 1.00          # Maximum range width: 1.00% of spot
OR_STOP_BUF_PCT = 0.20           # Minimum stop buffer distance: 0.20% of spot
OR_VOL_MULT = 1.0                # Volume multiplier vs 20-bar avg (1.0x)
OR_USE_VOLUME = True             # Require volume confirmation
OR_USE_TREND_FILT = True         # Require VWAP trend filter
OR_RISK_PCT = 0.5                # Risk per trade (% of equity): 0.5%
OR_INIT_CAPITAL = 200000.0       # Initial capital base: Rs. 2,00,000
COMMISSION_PER_ORDER = 20.0      # Rs. 20 per order
SLIPPAGE_POINTS = 2.0            # 2 points slippage

# Active Strategy Engine Mode: "SCALP" (NIFTY 10-15 pt Scalper per Strategy PDF), "ORB" (15-min Breakout), or "HYBRID"
ACTIVE_STRATEGY_MODE = "SCALP"

# Scanner loop interval in seconds
CYCLE_INTERVAL_SECONDS = 3.0
SCAN_INTERVAL_SECONDS = 3.0


