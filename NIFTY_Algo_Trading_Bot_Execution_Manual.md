# GROWW NIFTY ALGO TRADING BOT — OFFICIAL EXECUTION & RISK MANUAL
**Pine Script v5 15-Minute Opening Range Breakout (ORB) & 10–15 Point Scalper Engine**  
*Groww Account UCC: 6629599909 | Segment: NSE F&O (NIFTY & BANKNIFTY Options)*

---

## 📋 1. Master Quick-Reference Summary Table

| Parameter / Sawal | Bot Ka Exact Rule | Practical / Numerical Example |
| :--- | :--- | :--- |
| **1. Kab Kharidega? (Buy Timing)** | Subah **09:30 AM se 11:00 AM** ke beech sirf. | 09:15-09:30 AM ke beech koi trade nahi lega. 09:30 AM ke baad breakout par entry. |
| **2. Kya Kharidega? (Contract)** | **NIFTY ATM (At-The-Money) Option**<br>Breakout par CE | Breakdown par PE | Agar NIFTY 25,140 par chal raha hai, toh nearest 25150 Strike select karega. |
| **3. Kitne Ka Kharidega? (Capital)** | **1 se 2 Lots (25 se 50 Qty)**<br>Lagne wala paisa: **Rs. 2,500 – Rs. 7,000** | Pine Script formula: `qty = floor((capital × 0.5%) / riskPts)`. Poora account balance nahi lagta. |
| **4. Kitne Loss Pe Bechega? (Stop-Loss)** | **Option Premium se ~6 to 10 Pts**<br>Max Loss: **Rs. 600 – 1,000 / lot** | Index level risk hit hote hi turant automatic market sell karega. Daily loss Rs. 5,000 par circuit breaker lock. |
| **5. Kab Bechega? (Profit Booking)** | **1:2 Risk-to-Reward (2x Target)**<br>Gain: **+12 to 18 Pts** (~Rs. 1,500 – 2,500 / lot) | Target price hit hote hi auto profit book. Sham 03:15 PM par bachi hui position auto close. |
| **6. Din Me Kitni Trades?** | **Sirf 1 Trade Per Day** | Pine Script `tradedToday = true` rule se overtrading 100% block rehti hai. |

---

## ⏰ 2. Session Timeline (Kab Kya Hoga?)

1. **09:15 AM – 09:30 AM (Opening Range Formulation)**:
   - **NO TRADE PHASE**: Bot koi order place nahi karega.
   - NIFTY 50 ka 15-minute Highest High (`or_high`) aur Lowest Low (`or_low`) note karega.
2. **09:30 AM – 11:00 AM (Active Entry Window)**:
   - Jaise hi 15-minute range ka breakout aayega, bot automatic ATM Call ya Put buy karega.
3. **11:00 AM – 03:15 PM (Entry Window Closed)**:
   - Nayi trade lena band. Sirf open trade ke Target aur Stop-Loss ko track karega.
4. **03:15 PM (15:15 IST Mandatory Square-Off)**:
   - Bachi hui open positions automatically close (square-off) kar di jayengi.

---

## 🎯 3. Entry Setup: Breakout Par Kab Kharidega?

Bot blind entry nahi leta. Trade lene ke liye ye 4 conditions match honi zaroori hain:

### A. CALL (CE) Buy Condition:
- NIFTY Spot Price > 15-min OR High (09:15–09:30 high cross kare)
- Trend Filter: Spot Close > Intraday VWAP (Bullish)
- Volume Filter: Breakout 1-min volume > 20-candle Volume SMA
- Range Filter: 15-min range width spot ka 0.30% se 1.00% ke beech ho

### B. PUT (PE) Buy Condition:
- NIFTY Spot Price < 15-min OR Low (09:15–09:30 low break kare)
- Trend Filter: Spot Close < Intraday VWAP (Bearish)
- Volume Filter: Breakdown 1-min volume > 20-candle Volume SMA
- Range Filter: 15-min range width spot ka 0.30% se 1.00% ke beech ho

---

## 💰 4. Kitne Ka Purchase Karega? (Capital & Lot Sizing)

- **Capital Safety Rule**: Pine Script position sizing formula capital ka **sirf 0.5% risk** calculate karta hai:
  $$\text{Qty} = \lfloor \frac{\text{Initial Capital} \times 0.5\%}{\text{Risk Points}} \rfloor$$
- **Lot Size**: NIFTY me 1 Lot = 25 Shares (Bot 1 se 2 Lots lega = 25 se 50 Qty).
- **Required Capital**:
  - **1 Lot (25 Qty)** = ~Rs. 2,500 se Rs. 4,000
  - **2 Lots (50 Qty)** = ~Rs. 5,000 se Rs. 8,000
  - Aapka baki balance broker account me 100% safe rehta hai.

---

## 🛑 5. Kitne Loss Pe Automatic Bech Dega? (Stop-Loss Protection)

1. **Per-Trade Stop-Loss (Individual SL)**:
   - NIFTY Index me ~10 se 20 points ka stop-loss hota hai.
   - Option premium me ye lagbhag **6 se 10 points ka SL** banta hai.
   - **Max Loss**: 1 lot par lagbhag **Rs. 600 se Rs. 1,000** aate hi automatic market order se sell kar dega.
2. **Daily Circuit Breaker (Disaster Protection)**:
   - Agar din ka total realized nuksan **Rs. -5,000** touch ho jaye, toh bot us din ke liye **complete shutdown / lock** ho jayega.

---

## 🏆 6. Kab Bechega? (Profit Booking & Exits)

1. **Target 1:2 R:R (Double Target)**:
   - Jitna risk liya tha, uska **2x Double Gain** aate hi target book hoga.
   - Option premium me **+12 se +18 Points gain** (~Rs. 1,500 – 2,500 per lot) par auto sell.
2. **Trailing Stop-Loss to Breakeven**:
   - Jaise hi trade +7 se +8 points profit me aati hai, bot SL ko kharid rate (cost-to-cost) par move kar deta hai.
3. **Sham 03:15 PM Auto Square-Off**:
   - Sham 3:15 PM par trade automatic close ho jayegi. Koi overnight carry-forward risk nahi.

---

## 🚀 7. Kal Subah Live Trading Start Karne Ke Steps

1. **Subah Groww Token**: Groww account se fresh API Token generate karke `.env` me `GROWW_API_KEY` me paste karein.
2. **Dashboard Login**: Browser me `http://127.0.0.1:5000` kholein (username: `admin` / password: `groww123`).
3. **Switch to Live**: Dashboard par **"⚡ Switch to LIVE Groww F&O"** button dabayein.
4. **Relax & Monitor**: 09:15 se 09:30 range banegi, aur 09:30 se 11:00 AM breakout par bot automatic trade execute karega!
