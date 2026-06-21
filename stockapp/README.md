# Swing Trade Dashboard (RSI Strategy) — NSE/BSE

A local web app to manually track NSE/BSE stocks, monitor RSI(14), and get RAG-powered
answers about your swing trading strategy: **buy when RSI(14) < 40**.

## Stack
- **FastAPI** — backend API (stock CRUD, RSI calculation, RAG endpoint)
- **Streamlit** — dashboard UI (multi-page: Dashboard, Add Stock, Strategy Assistant)
- **SQLite** — local storage for your watchlist and price/RSI history
- **yfinance** — free, no-API-key market data from Yahoo Finance (NSE via `.NS` suffix)
- **ChromaDB + sentence-transformers** — local vector search for RAG (no cloud calls)
- **Ollama (optional)** — local LLM to generate natural-language RAG answers

## Why yfinance / Yahoo Finance?
For NSE/BSE stocks, **yfinance is the best free option**: no signup, no API key, no rate-limit
headaches for personal use, and it covers search, daily OHLCV history, and live quotes — everything
this app needs to compute RSI(14). If you ever want a paid/alternate fallback, there's a placeholder
for **Alpha Vantage** (free tier: 5 calls/min, 500/day) in `.env`, but it's not required to run the app.

## Project Structure
```
stockapp/
├── .env                        # your local config (created from .env.example)
├── .env.example                # template — copy this to .env
├── requirements.txt
├── backend/
│   ├── main.py                 # FastAPI app & routes
│   ├── config.py               # loads .env settings
│   ├── database.py             # SQLAlchemy models (Stock, PriceSnapshot) + SQLite setup
│   ├── market_data.py          # yfinance search, RSI(14) calculation, signal logic
│   ├── rag_engine.py           # embeddings + Chroma retrieval + Ollama generation
│   └── schemas.py               # Pydantic request/response models
├── rag_kb/
│   └── strategy_notes.py       # static knowledge base: RSI theory & swing trading rules
├── frontend/
│   ├── app.py                   # Dashboard (main Streamlit page)
│   ├── api_client.py            # HTTP client wrapper for calling the backend
│   └── pages/
│       ├── 1_Add_Stock.py       # search-and-add stock page
│       └── 2_Strategy_Assistant.py  # RAG chat page
└── data/                        # created automatically: stocks.db, chroma_store/
```

## Setup

### 1. Create a virtual environment and install dependencies
```bash
cd stockapp
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```
The defaults work out of the box. Open `.env` if you want to change the RSI buy threshold,
ports, or auto-refresh interval.

### 3. (Optional but recommended) Install Ollama for AI-generated RAG answers
Without Ollama, the Strategy Assistant page still works — it just returns the raw retrieved
notes instead of an LLM-written answer.
```bash
# Install from https://ollama.com, then:
ollama pull llama3.2
ollama serve     # usually starts automatically after install
```

### 4. Run the backend (Terminal 1)
```bash
cd stockapp
source venv/bin/activate
uvicorn backend.main:app --reload --port 8000
```
Visit `http://127.0.0.1:8000/docs` to see/try the auto-generated API docs.

### 5. Run the frontend (Terminal 2)
```bash
cd stockapp
source venv/bin/activate
streamlit run frontend/app.py
```
This opens the dashboard at `http://localhost:8501`. The first time you open the
**Strategy Assistant** page, it will download the embedding model (`all-MiniLM-L6-v2`,
~80MB, one-time, needs internet).

## How to Use

### Add Stock page
1. Type a company name (e.g. "Reliance", "HDFC Bank", "Tata Motors") or exact ticker.
2. Click **Search** — matching NSE/BSE stocks appear with an **Add** button each.
3. Click **Add**, set your buy price range (min/max) and optional notes, then **Confirm & Save**.
4. The stock is stored in SQLite and its first RSI/price snapshot is fetched immediately.

### Dashboard page
- See all watchlist stocks with current price, RSI(14), and a signal:
  - 🟢 **BUY** — RSI below your threshold (default 40)
  - 🟡 **WATCH** — RSI within 10 points above threshold (approaching your buy zone)
  - ⚪ **HOLD** — RSI comfortably above threshold
- **Refresh All Now** — manually pulls fresh data for every stock.
- **Auto-refresh** toggle — re-fetches on a timer (60s to 15min) while the page is open.
- Adjust the **BUY signal threshold** slider live without editing `.env`.
- Select any stock to see a candlestick chart with your buy range highlighted, plus an
  RSI subplot with your buy threshold and the classic 30/70 overbought/oversold lines.
- Edit buy range/notes or remove a stock from the detail panel.

### Strategy Assistant page (RAG)
Ask things like:
- "Why do we buy when RSI is below 40?"
- "What's the RSI for Reliance right now?"
- "Is Tata Motors in my buy price range?"
- "What's the difference between BUY, WATCH, and HOLD?"

It retrieves relevant notes from a static strategy knowledge base **and** your live
stock data (re-embedded fresh on every query), then either has Ollama write a natural
answer, or — if Ollama isn't running — shows you the retrieved notes directly.

## Strategy Notes (built into the RAG knowledge base)
The core strategy this app is built around: **RSI(14) < 40 = potential buy signal** for
swing trading. This generally works best when:
1. The overall trend is still up (price above 50/200-day moving average) — you're buying
   a dip, not catching a falling knife.
2. You use a defined buy price range (not a single price) so you can scale in as price
   approaches support.
3. You set a stop-loss below recent swing lows — RSI < 40 is a signal, not a guarantee.
4. You watch for RSI to curl back upward as additional confirmation before entering.

Full notes are in `rag_kb/strategy_notes.py` and are queryable via the Strategy Assistant.

## Customizing the RSI Buy Threshold
Two ways:
- **Quick/session-only:** use the slider on the Dashboard page.
- **Permanent default:** edit `RSI_BUY_THRESHOLD` in `.env` and restart the backend.

## Notes & Limitations
- Yahoo Finance (via yfinance) is free and reliable for personal use, but it's an
  unofficial data source — don't use this for high-frequency or production trading.
- RSI is computed using Wilder's smoothing method (the standard approach), on daily
  closes, over a rolling 3-month history window.
- The SQLite database (`data/stocks.db`) is the single source of truth for your
  watchlist — back it up if you want to preserve your data long-term.
- This tool is for personal research/tracking only and is not financial advice.
