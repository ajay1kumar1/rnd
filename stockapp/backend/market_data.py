"""
Market data service.

Uses yfinance (free, no API key) to:
  1. Search/resolve a user-typed stock name into matching NSE ticker symbols.
  2. Pull historical OHLCV data for RSI(14) calculation.
  3. Pull the latest market price.

yfinance under the hood calls Yahoo Finance's public endpoints. NSE symbols
are suffixed with ".NS" (e.g. RELIANCE.NS) and BSE symbols with ".BO".
"""
import pandas as pd
import yfinance as yf
from typing import List, Dict, Optional

from backend.config import settings


def search_stocks(query: str, limit: int = 10) -> List[Dict]:
    """
    Search Yahoo Finance for stocks matching the given name/text, using yfinance's
    built-in Search class (more resilient to header/rate-limit changes than calling
    the raw endpoint directly).
    Filters results to NSE/BSE (India) equities and returns a clean list:
        [{"symbol": "RELIANCE.NS", "name": "Reliance Industries Limited", "exchange": "NSE"}, ...]
    """
    if not query or len(query.strip()) < 1:
        return []

    try:
        search = yf.Search(query.strip(), max_results=limit * 3, news_count=0, enable_fuzzy_query=True)
        quotes = search.quotes or []
    except Exception as e:
        return [{"error": f"Search failed: {e}"}]

    results = []
    for quote in quotes:
        exch = quote.get("exchange", "")
        symbol = quote.get("symbol", "")
        if exch not in ("NSI", "BSE"):
            continue
        if quote.get("quoteType") != "EQUITY":
            continue
        results.append({
            "symbol": symbol,
            "name": quote.get("longname") or quote.get("shortname") or symbol,
            "exchange": "NSE" if exch == "NSI" else "BSE",
        })
        if len(results) >= limit:
            break

    return results


def get_latest_price_and_rsi(symbol: str, period: int = None) -> Optional[Dict]:
    """
    Fetch recent daily history for `symbol` and compute RSI(period).
    Returns: {"price": float, "rsi": float, "as_of": "YYYY-MM-DD HH:MM"} or None on failure.
    """
    period = period or settings.RSI_PERIOD
    try:
        ticker = yf.Ticker(symbol)
        # Need at least ~period*3 candles for a stable RSI; pull 3 months of daily data
        hist = ticker.history(period="3mo", interval="1d", auto_adjust=True)
        if hist is None or hist.empty or len(hist) < period + 1:
            return None

        closes = hist["Close"].dropna()
        rsi_series = _compute_rsi(closes, period)
        latest_rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else None
        latest_price = float(closes.iloc[-1])
        as_of = hist.index[-1].strftime("%Y-%m-%d %H:%M")

        return {"price": round(latest_price, 2), "rsi": round(latest_rsi, 2) if latest_rsi is not None else None, "as_of": as_of}
    except Exception as e:
        return {"error": str(e)}


def _compute_rsi(close_prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Standard Wilder's RSI calculation.
    RSI = 100 - (100 / (1 + RS))
    RS  = Average Gain / Average Loss  (smoothed with Wilder's moving average)
    """
    delta = close_prices.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing = EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def get_signal(rsi: Optional[float], buy_threshold: float = None) -> str:
    """Map an RSI value to a simple trading signal label based on the user's strategy."""
    buy_threshold = buy_threshold if buy_threshold is not None else settings.RSI_BUY_THRESHOLD
    if rsi is None:
        return "UNKNOWN"
    if rsi < buy_threshold:
        return "BUY"
    if rsi < buy_threshold + 10:
        return "WATCH"
    return "HOLD"


def get_history(symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    """Fetch OHLCV history with RSI column attached, for charting."""
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval="1d", auto_adjust=True)
        if hist is None or hist.empty:
            return None
        hist["RSI_14"] = _compute_rsi(hist["Close"], settings.RSI_PERIOD)
        return hist
    except Exception:
        return None
