"""
Script to generate the complete Executive User Manual & Strategy Rules PDF
for the Groww Futures & Options (F&O) Algorithmic Trading Bot.
Covers Buy Timing, Investment/Capital Sizing, Stop-Loss Limits, and 1:2 R:R Profit Exits.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

PDF_FILENAME = "NIFTY_Algo_Trading_Bot_Execution_Manual.pdf"


class NumberedCanvas(canvas.Canvas):
    """Adds professional header and footer with dynamic page count."""
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 11 * inch - 36, "GROWW NIFTY ALGO TRADING BOT — OFFICIAL STRATEGY & RISK EXECUTION MANUAL")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 11 * inch - 42, 8.5 * inch - 54, 11 * inch - 42)

        # Footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(54, 42, 8.5 * inch - 54, 42)
        self.setFont("Helvetica", 8)
        self.drawString(54, 28, "Confidential • Groww Trading API Bridge • Account UCC: 6629599909 • Mode: PAPER / LIVE")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 54, 28, page_text)

        self.restoreState()


def build_pdf(filename=PDF_FILENAME):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=50,
        bottomMargin=50
    )

    styles = getSampleStyleSheet()

    # Color Palette
    PRIMARY = colors.HexColor("#0F172A")        # Slate Navy
    ACCENT_GREEN = colors.HexColor("#059669")   # Emerald Green
    ACCENT_BLUE = colors.HexColor("#2563EB")    # Royal Blue
    ACCENT_RED = colors.HexColor("#DC2626")     # Crimson Red
    ACCENT_AMBER = colors.HexColor("#D97706")   # Amber Gold
    BG_LIGHT = colors.HexColor("#F8FAFC")       # Light Slate
    BORDER_COLOR = colors.HexColor("#CBD5E1")

    # Typography
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=ACCENT_GREEN,
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=PRIMARY,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=ACCENT_BLUE,
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor("#334155"),
        leftIndent=10,
        spaceAfter=2.5
    )

    callout_style = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=PRIMARY
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white
    )

    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=PRIMARY
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=PRIMARY
    )

    story = []

    # =========================================================================
    # PAGE 1: TITLE, EXECUTIVE SUMMARY & QUICK REFERENCE MATRIX
    # =========================================================================
    story.append(Paragraph("GROWW NIFTY ALGO TRADING BOT", title_style))
    story.append(Paragraph("Complete Trading Rules, Capital Sizing, Stop-Loss &amp; Exit Manual • Pine Script v5 ORB", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=ACCENT_GREEN, spaceAfter=8))

    # Executive Summary Callout
    summary_html = """
    <b>EXECUTIVE SUMMARY (BOT KA COMPLETE KARYAKRAM):</b> Yeh manual Groww F&amp;O Trading Bot ke 
    tamam trading niyam (kab kharidega, kitne ka kharidega, kab bechega, aur kitne loss par automatic exit karega) 
    ki poori detail faraham karta hai. Bot <b>Pine Script v5 15-Minute Opening Range Breakout (ORB)</b> aur 
    <b>10–15 Point Scalper Engine</b> ke zariye At-The-Money (ATM) Options par anushasit (disciplined) tarike se kaam karta hai.
    """
    summary_table = Table([[Paragraph(summary_html, callout_style)]], colWidths=[504])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDF4")),
        ('BOX', (0,0), (-1,-1), 1, ACCENT_GREEN),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # MASTER SUMMARY TABLE (Quick Reference Matrix)
    story.append(Paragraph("Master Quick-Reference Matrix (Ek Nazar Me Bot Ka Rule)", h1_style))
    summary_data = [
        [Paragraph("Parameter / Sawal", table_header_style), Paragraph("Bot Ka Exact Rule", table_header_style), Paragraph("Concrete Example / Mathematical Details", table_header_style)],
        [
            Paragraph("<b>1. Kab Kharidega? (Buy Timing)</b>", table_cell_bold),
            Paragraph("Subah <b>09:30 AM se 11:00 AM</b> ke beech sirf.", table_cell_style),
            Paragraph("09:15-09:30 AM ke beech koi trade nahi lega. Range bante hi breakout par entry.", table_cell_style)
        ],
        [
            Paragraph("<b>2. Kya Kharidega? (Contract)</b>", table_cell_bold),
            Paragraph("<b>NIFTY ATM (At-The-Money) Option</b><br/>Breakout par CE | Breakdown par PE", table_cell_style),
            Paragraph("Agar Nifty 25,140 par hai, toh 25150 Strike (50-point step) select karega.", table_cell_style)
        ],
        [
            Paragraph("<b>3. Kitne Ka Kharidega? (Capital)</b>", table_cell_bold),
            Paragraph("<b>1 se 2 Lots (25 se 50 Qty)</b><br/>Lagne wala paisa: <b>Rs. 2,500 – 7,000</b>", table_cell_style),
            Paragraph("Pine Script formula: <code>qty = floor((capital × 0.5%) / riskPts)</code>. Poora account balance nahi lagta.", table_cell_style)
        ],
        [
            Paragraph("<b>4. Kitne Loss Pe Bechega? (Stop-Loss)</b>", table_cell_bold),
            Paragraph("<b>Option Premium se ~6 to 10 Pts</b><br/>Max Loss: ~<b>Rs. 600 – 1,000 / lot</b>", table_cell_style),
            Paragraph("Index risk hit hote hi turant automatic market sell karega. Daily loss Rs. 5,000 pe circuit breaker lock.", table_cell_style)
        ],
        [
            Paragraph("<b>5. Kab Bechega? (Profit Booking)</b>", table_cell_bold),
            Paragraph("<b>1:2 Risk-Reward (2x Target)</b><br/>Gain: <b>+12 to 18 Pts</b> (~Rs. 1,500 – 2,500 / lot)", table_cell_style),
            Paragraph("Target price hit hote hi auto profit book. Sham 03:15 PM par bachi position close.", table_cell_style)
        ],
        [
            Paragraph("<b>6. Din Me Kitni Trades?</b>", table_cell_bold),
            Paragraph("<b>Sirf 1 Trade Per Day</b>", table_cell_style),
            Paragraph("Pine Script <code>tradedToday = true</code> rule se overtrading 100% block rehti hai.", table_cell_style)
        ]
    ]
    t_summary = Table(summary_data, colWidths=[130, 160, 214])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,1), (-1,1), colors.white),
        ('BACKGROUND', (0,2), (-1,2), BG_LIGHT),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#EFF6FF")),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#FEF2F2")),
        ('BACKGROUND', (0,5), (-1,5), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (0,6), (-1,6), colors.white),
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 8))

    # SECTION 1: INTRADAY TIMELINE
    story.append(Paragraph("1. Detailed Session Timeline (Kab Kya Karta Hai Bot?)", h1_style))
    timeline_data = [
        [Paragraph("Time Window (IST)", table_header_style), Paragraph("Bot Ki Activity", table_header_style), Paragraph("Trading Rule &amp; Action", table_header_style)],
        [
            Paragraph("<b>09:15 AM – 09:30 AM</b>", table_cell_bold),
            Paragraph("Opening Range Recording (15 Min)", table_cell_style),
            Paragraph("<b>KOI TRADE NAHI LEGA.</b> NIFTY ka 15-minute Highest High (OR High) aur Lowest Low (OR Low) note karega.", table_cell_style)
        ],
        [
            Paragraph("<b>09:30 AM – 11:00 AM</b>", table_cell_bold),
            Paragraph("<b>ACTIVE TRADE ENTRY WINDOW</b>", table_cell_style),
            Paragraph("Agar Nifty OR High break kare toh <b>BUY CALL (CE)</b>, agar OR Low break kare toh <b>BUY PUT (PE)</b> kharidega.", table_cell_style)
        ],
        [
            Paragraph("<b>11:00 AM – 03:15 PM</b>", table_cell_bold),
            Paragraph("No Fresh Entry (Window Closed)", table_cell_style),
            Paragraph("11:00 AM ke baad koi naya order nahi dalega. Sirf subah ki active trade ka Target/SL monitor karega.", table_cell_style)
        ],
        [
            Paragraph("<b>03:15 PM (15:15 IST)</b>", table_cell_bold),
            Paragraph("<b>EOD MANDATORY SQUARE-OFF</b>", table_cell_style),
            Paragraph("Agar Target ya SL hit nahi hua, toh sham 3:15 PM par automatic sabhi open positions close kar dega.", table_cell_style)
        ]
    ]
    t_timeline = Table(timeline_data, colWidths=[110, 150, 244])
    t_timeline.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,1), (-1,1), BG_LIGHT),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (0,3), (-1,3), colors.white),
        ('BACKGROUND', (0,4), (-1,4), colors.HexColor("#FEF2F2")),
    ]))
    story.append(t_timeline)

    # PAGE BREAK TO PAGE 2
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: ENTRY CONDITIONS, CAPITAL SIZING & STOP-LOSS FORMULAS
    # =========================================================================
    story.append(Paragraph("2. Entry Setup: Breakout Par Kab Kharidega?", h1_style))
    story.append(Paragraph(
        "Bot blind entry nahi leta. Trade lene ke liye TradingView Pine Script v5 ke mutabiq ye <b>4 conditions ek sath poori honi zaroori hain</b>:",
        body_style
    ))

    entry_data = [
        [Paragraph("Setup Type", table_header_style), Paragraph("Zaroori Conditions (Sabhi Match Honi Chahiye)", table_header_style), Paragraph("Action &amp; Contract", table_header_style)],
        [
            Paragraph("<b>CALL (CE) BUY</b><br/>(Bullish Breakout)", table_cell_bold),
            Paragraph("1. NIFTY Close &gt; 15-min OR High (09:15-09:30 high se upar)<br/>"
                      "2. Trend Filter: NIFTY Close &gt; VWAP (Intraday Bullish)<br/>"
                      "3. Volume Filter: 1m Candle Volume &gt; 20-SMA Avg Volume<br/>"
                      "4. Range Width: 15-min width spot ka 0.30% se 1.00% ke beech ho", table_cell_style),
            Paragraph("Kharidega: <b>ATM Call Option (CE)</b><br/>"
                      "<i>Ex: NIFTY 25150 CE @ Rs. 130</i>", table_cell_style)
        ],
        [
            Paragraph("<b>PUT (PE) BUY</b><br/>(Bearish Breakdown)", table_cell_bold),
            Paragraph("1. NIFTY Close &lt; 15-min OR Low (09:15-09:30 low se niche)<br/>"
                      "2. Trend Filter: NIFTY Close &lt; VWAP (Intraday Bearish)<br/>"
                      "3. Volume Filter: 1m Candle Volume &gt; 20-SMA Avg Volume<br/>"
                      "4. Range Width: 15-min width spot ka 0.30% se 1.00% ke beech ho", table_cell_style),
            Paragraph("Kharidega: <b>ATM Put Option (PE)</b><br/>"
                      "<i>Ex: NIFTY 25150 PE @ Rs. 125</i>", table_cell_style)
        ]
    ]
    t_entry = Table(entry_data, colWidths=[110, 250, 144])
    t_entry.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (0,2), (-1,2), colors.HexColor("#FEF2F2")),
    ]))
    story.append(t_entry)
    story.append(Spacer(1, 8))

    # SECTION 3: HOW MUCH WILL IT PURCHASE?
    story.append(Paragraph("3. Kitne Ka Purchase Karega? (Capital &amp; Lot Sizing)", h1_style))
    story.append(Paragraph(
        "Aapke account me kitna bhi balance ho, bot <b>kabhi bhi poora capital use nahi karega</b>. "
        "Pine Script position sizing formula capital ka <b>sirf 0.5% risk</b> calculate karta hai:",
        body_style
    ))
    story.append(Paragraph("• <b>Position Sizing Formula:</b> <code>Qty = floor((Initial Capital × Risk%) / Risk_Points)</code>", bullet_style))
    story.append(Paragraph("• <b>NIFTY Lot Size:</b> 1 Lot = 25 Shares (Max 1 se 2 Lots lega = 25 se 50 Qty).", bullet_style))
    story.append(Paragraph("• <b>ATM Option Premium:</b> NIFTY ka ATM option rate aam taur par <b>Rs. 100 se Rs. 160</b> ke beech hota hai.", bullet_style))
    story.append(Spacer(1, 4))

    sizing_data = [
        [Paragraph("Trade Scenario", table_header_style), Paragraph("Capital Deployed (Paisa)", table_header_style), Paragraph("Max Risk on Trade", table_header_style), Paragraph("Account Safety Factor", table_header_style)],
        [
            Paragraph("<b>1 Lot (25 Qty) Purchase</b>", table_cell_bold),
            Paragraph("Rs. 2,500 – Rs. 4,000 approx", table_cell_style),
            Paragraph("Rs. 600 – Rs. 800 (Max loss)", table_cell_style),
            Paragraph("Aapka 95%+ capital account me safe rehta hai.", table_cell_style)
        ],
        [
            Paragraph("<b>2 Lots (50 Qty) Purchase</b>", table_cell_bold),
            Paragraph("Rs. 5,000 – Rs. 8,000 approx", table_cell_style),
            Paragraph("Rs. 1,000 – Rs. 1,500 (Max loss)", table_cell_style),
            Paragraph("Account par kabhi bada drawdown nahi lagta.", table_cell_style)
        ]
    ]
    t_sizing = Table(sizing_data, colWidths=[120, 130, 114, 140])
    t_sizing.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,1), (-1,1), colors.white),
    ]))
    story.append(t_sizing)
    story.append(Spacer(1, 8))

    # SECTION 4: STOP-LOSS FORMULA
    story.append(Paragraph("4. Kitne Loss Pe Automatic Bech Dega? (Stop-Loss Protection)", h1_style))
    story.append(Paragraph(
        "Bot jaise hi order place karta hai, uske sath hi system me strict <b>Stop-Loss Order</b> active ho jata hai:",
        body_style
    ))

    sl_data = [
        [Paragraph("Risk Layer", table_header_style), Paragraph("Trigger Point / Formula", table_header_style), Paragraph("Automatic Action", table_header_style)],
        [
            Paragraph("<b>Per-Trade Stop-Loss</b><br/>(Individual Trade SL)", table_cell_bold),
            Paragraph("NIFTY Index me ~10 to 20 pts SL.<br/>"
                      "Option Premium me: <b>-6 to -10 Points</b>", table_cell_style),
            Paragraph("Jaise hi premium SL point par pahuchega, bot bina ruke <b>Market Order se sell karke exit</b> kar dega. Max loss Rs. 800-1,000 per lot par cut.", table_cell_style)
        ],
        [
            Paragraph("<b>Daily Circuit Breaker</b><br/>(Account Lock Protection)", table_cell_bold),
            Paragraph("<b>Rs. -5,000.00</b> Cumulative Day Loss", table_cell_style),
            Paragraph("Agar din ka realized nuksan Rs. 5,000 touch karega, toh bot <b>Emergency Shutdown</b> ho jayega aur pure din naya order block kar dega.", table_cell_style)
        ]
    ]
    t_sl = Table(sl_data, colWidths=[130, 160, 214])
    t_sl.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 4.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4.5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#FEF2F2")),
        ('BACKGROUND', (0,2), (-1,2), colors.white),
    ]))
    story.append(t_sl)

    # PAGE BREAK TO PAGE 3
    story.append(PageBreak())

    # =========================================================================
    # PAGE 3: PROFIT BOOKING (1:2 R:R), HOW TO RUN & LIVE SWITCH CHECKLIST
    # =========================================================================
    story.append(Paragraph("5. Kab Bechega? (1:2 Risk-to-Reward Profit Booking &amp; Exits)", h1_style))
    story.append(Paragraph(
        "Bot me 3 tareeqon se position bechi (exit ki) jati hai:",
        body_style
    ))

    exit_data = [
        [Paragraph("Exit Type", table_header_style), Paragraph("Trigger Rule", table_header_style), Paragraph("Profit / Rupee Outcome", table_header_style)],
        [
            Paragraph("<b>1. Target Hit (1:2 R:R)</b><br/>(Primary Profit Target)", table_cell_bold),
            Paragraph("Risk Points ka exact <b>2x Double Gain</b>.<br/>"
                      "<code>Target = Entry + (2 × Risk_Pts)</code>", table_cell_style),
            Paragraph("Option premium me <b>+12 se +18 Points gain</b>. 1 lot me approx <b>+Rs. 1,500 se Rs. 2,500 profit</b> aate hi auto sell.", table_cell_style)
        ],
        [
            Paragraph("<b>2. Trailing to Breakeven</b><br/>(Capital Shield)", table_cell_bold),
            Paragraph("Jab trade <b>+7 se +8 points</b> munafa (profit) me aa jati hai.", table_cell_style),
            Paragraph("Bot Stop-Loss ko utha kar entry rate (cost-to-cost) par le aata hai taaki jeeti hui trade kabhi loss me na jaye.", table_cell_style)
        ],
        [
            Paragraph("<b>3. Sham 3:15 PM Exit</b><br/>(EOD Square-Off)", table_cell_bold),
            Paragraph("Time <b>15:15 IST (03:15 PM)</b> sharp.", table_cell_style),
            Paragraph("Agar na target aaya na SL, toh 3:15 PM par trade automatic close ho jayegi. Koi trade overnight carry nahi hoti.", table_cell_style)
        ]
    ]
    t_exit = Table(exit_data, colWidths=[120, 160, 224])
    t_exit.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), PRIMARY),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#F0FDF4")),
        ('BACKGROUND', (0,2), (-1,2), BG_LIGHT),
        ('BACKGROUND', (0,3), (-1,3), colors.HexColor("#FEF2F2")),
    ]))
    story.append(t_exit)
    story.append(Spacer(1, 10))

    # SECTION 6: LIVE DEPLOYMENT GUIDE
    story.append(Paragraph("6. Kal Subah Live Trading Start Karne Ke Simple Steps", h1_style))
    steps = [
        "<b>Step 1 (Subah API Token):</b> Groww account me login karke fresh API Token generate karein aur <code>.env</code> file me <code>GROWW_API_KEY</code> me paste karein.",
        "<b>Step 2 (Dashboard Open):</b> Chrome browser me <code>http://127.0.0.1:5000</code> kholein. Login karein: username <code>admin</code> / password <code>groww123</code>.",
        "<b>Step 3 (Live Mode Switch):</b> Dashboard par <b>'⚡ Switch to LIVE Groww F&amp;O'</b> button dabayein. Bot real broker bridge se connect ho jayega.",
        "<b>Step 4 (Relax &amp; Monitor):</b> Subah 09:15 se 09:30 AM bot range track karega, aur 09:30 se 11:00 AM ke beech condition match hone par automatic trade place karega."
    ]
    for s in steps:
        story.append(Paragraph(s, bullet_style))

    story.append(Spacer(1, 8))
    signoff = """
    <b>ZARURI SUJHAW:</b> Pehle 1 din bot ko <b>Paper Mode (Virtual Funds)</b> me 09:30 AM breakout execute karte hue dekhein. 
    Jab aapko strategy ka execution aur stop-loss discipline pasand aaye, tabhi Live button switch karein.
    """
    t_signoff = Table([[Paragraph(signoff, ParagraphStyle('Signoff', parent=body_style, fontSize=7.5, leading=10, textColor=colors.HexColor("#64748B")))]], colWidths=[504])
    t_signoff.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
        ('BOX', (0,0), (-1,-1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_signoff)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF generated successfully at: {os.path.abspath(filename)}")


if __name__ == "__main__":
    build_pdf()
