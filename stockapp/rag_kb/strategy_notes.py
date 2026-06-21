RSI_BASICS = """
What is RSI (Relative Strength Index)?
RSI is a momentum oscillator developed by J. Welles Wilder that measures the speed and
magnitude of recent price changes to evaluate overbought or oversold conditions.
It is calculated on a scale of 0 to 100. The standard look-back period is 14 candles
(RSI-14), typically using daily closing prices for swing trading.

RSI formula:
RSI = 100 - (100 / (1 + RS))
RS = Average Gain over N periods / Average Loss over N periods
Wilder's smoothing (an exponential moving average with alpha = 1/N) is used to average
gains and losses, which is why RSI values are smoother than a simple moving average
would produce.
"""

RSI_INTERPRETATION = """
How to interpret RSI(14) values:
- RSI above 70 is traditionally considered "overbought" - the stock may be due for a
  pullback or consolidation.
- RSI below 30 is traditionally considered "oversold" - the stock may be due for a
  bounce.
- RSI between 40 and 60 is often considered neutral territory.
- In a strong uptrend, RSI often oscillates between 40 and 90, rarely dropping below 40.
  A pullback to the 40-50 zone during an uptrend is often viewed by swing traders as a
  "buy the dip" zone rather than a reversal signal.
- In a strong downtrend, RSI often oscillates between 10 and 60, rarely climbing above 60.
"""

SWING_TRADING_RSI_STRATEGY = """
Swing trading strategy: Buy when RSI(14) < 40
This is a momentum dip-buying strategy. The logic is that RSI dropping below 40 signals
short-term weakness or a pullback, which can offer a better entry price than buying at
RSI 60-70 (where the move may already be extended). It is commonly combined with:
1. Confirming the overall trend is still up (e.g. price above the 50-day or 200-day
   moving average) so you are buying a dip in an uptrend, not catching a falling knife
   in a downtrend.
2. Setting a defined buy price range rather than a single price, to average into a
   position as the price drops toward support.
3. Using a stop-loss below recent swing lows to manage risk, since RSI < 40 alone does
   not guarantee a bounce - the stock could continue falling.
4. Watching for RSI to curl back upward (bottoming) as an additional confirmation signal
   before entering, rather than buying purely on RSI crossing under 40.

Risk management notes:
- RSI is a momentum indicator, not a guarantee of reversal. Combine it with price action,
  support/resistance levels, and volume for higher-conviction entries.
- Avoid using RSI in isolation during strong trending or news-driven moves (e.g. earnings,
  major announcements) since RSI can stay "oversold" for extended periods in a real
  downtrend.
- Position sizing and a maximum portfolio allocation per stock are important regardless
  of the entry signal used.
"""

BUY_PRICE_RANGE_CONCEPT = """
Why use a buying price range instead of a single target price?
Markets rarely hit an exact price. Defining a buy price range (e.g. buy between 2,400 and
2,450) lets a swing trader:
- Place a limit order anywhere within the range without missing the entry due to small
  price gaps.
- Average into a position with partial buys at different points within the range if the
  price keeps dropping (dollar-cost averaging within a defined zone).
- Combine the RSI(14) < 40 signal with a price range derived from recent support levels,
  e.g. a prior swing low or a moving average, so the entry is both momentum-confirmed and
  level-confirmed.
"""

SIGNAL_DEFINITIONS = """
How this dashboard's signals are defined:
- BUY: RSI(14) is below your configured buy threshold (default 40). This is your
  strategy's primary entry signal.
- WATCH: RSI(14) is within 10 points above your buy threshold (e.g. between 40 and 50 if
  threshold is 40). The stock is approaching your buy zone and is worth monitoring closely.
- HOLD: RSI(14) is comfortably above your buy threshold + 10. No entry signal currently;
  continue holding if already in a position, or wait for a pullback.
- UNKNOWN: Not enough price history was available to compute RSI (e.g. a newly listed
  stock, or a temporary data fetch issue).
"""

GENERAL_SWING_TRADING_NOTES = """
General swing trading principles:
Swing trading aims to capture gains over a few days to a few weeks, sitting between
day trading (minutes to hours) and long-term investing (months to years). Key practices:
- Use daily charts as the primary timeframe; weekly charts for broader trend context.
- Define entry, stop-loss, and target/exit levels before entering a trade.
- Keep position sizes proportionate to account risk tolerance (commonly 1-2% account
  risk per trade among disciplined swing traders).
- Re-evaluate RSI and price action regularly rather than only at entry - exit or trim a
  position if the original thesis (e.g. "buying a dip in an uptrend") breaks down.
- Liquidity matters: prefer stocks with sufficient daily trading volume so entries and
  exits can be executed without significant slippage.
"""

ALL_DOCS = [
    {"id": "rsi_basics", "title": "RSI Basics", "text": RSI_BASICS},
    {"id": "rsi_interpretation", "title": "RSI Interpretation", "text": RSI_INTERPRETATION},
    {"id": "swing_rsi_strategy", "title": "Swing Trading RSI<40 Strategy", "text": SWING_TRADING_RSI_STRATEGY},
    {"id": "buy_price_range", "title": "Buy Price Range Concept", "text": BUY_PRICE_RANGE_CONCEPT},
    {"id": "signal_definitions", "title": "Dashboard Signal Definitions", "text": SIGNAL_DEFINITIONS},
    {"id": "general_swing_notes", "title": "General Swing Trading Principles", "text": GENERAL_SWING_TRADING_NOTES},
]
