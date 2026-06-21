"""
FastAPI backend for the Swing Trade Dashboard.

Run with:
    uvicorn backend.main:app --reload --port 8000
(from the project root, with the virtualenv activated)
"""
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import init_db, get_db, Stock, PriceSnapshot
from backend import market_data
from backend import rag_engine
from backend.schemas import (
    StockSearchResult, StockCreate, StockUpdate, StockOut,
    RefreshResult, RagQuery, RagResponse,
)

app = FastAPI(title="Swing Trade Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()
    # NOTE: the embedding model + KB indexing is intentionally NOT done here.
    # Downloading the sentence-transformers model on first run can take a
    # while (or fail if offline), and we don't want that to block the API
    # from serving stock/dashboard requests. It is lazily indexed on first
    # call to /rag/query instead (see rag_engine.answer_query).


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


# ──────────────────────────────────────────────────────────────────────────
# Stock search (used by the "Add Stock" page to find matches as you type)
# ──────────────────────────────────────────────────────────────────────────
@app.get("/stocks/search", response_model=List[StockSearchResult])
def search_stocks(q: str = Query(..., min_length=1, description="Stock name or symbol to search")):
    results = market_data.search_stocks(q)
    if results and "error" in results[0]:
        raise HTTPException(status_code=502, detail=results[0]["error"])
    return results


# ──────────────────────────────────────────────────────────────────────────
# CRUD for the user's stock watchlist
# ──────────────────────────────────────────────────────────────────────────
@app.get("/stocks", response_model=List[StockOut])
def list_stocks(active_only: bool = True, db: Session = Depends(get_db)):
    query = db.query(Stock)
    if active_only:
        query = query.filter(Stock.is_active == True)  # noqa: E712
    stocks = query.order_by(Stock.created_at.desc()).all()

    out = []
    for s in stocks:
        signal = market_data.get_signal(s.last_rsi)
        item = StockOut.model_validate(s)
        item.signal = signal
        out.append(item)
    return out


@app.post("/stocks", response_model=StockOut, status_code=201)
def add_stock(payload: StockCreate, db: Session = Depends(get_db)):
    existing = db.query(Stock).filter(Stock.symbol == payload.symbol).first()
    if existing:
        if existing.is_active:
            raise HTTPException(status_code=409, detail="Stock already on your watchlist.")
        # Re-activate a previously removed stock instead of erroring
        existing.is_active = True
        existing.buy_price_min = payload.buy_price_min
        existing.buy_price_max = payload.buy_price_max
        existing.notes = payload.notes
        db.commit()
        db.refresh(existing)
        item = StockOut.model_validate(existing)
        item.signal = market_data.get_signal(existing.last_rsi)
        return item

    stock = Stock(
        symbol=payload.symbol,
        name=payload.name,
        exchange=payload.exchange,
        buy_price_min=payload.buy_price_min,
        buy_price_max=payload.buy_price_max,
        notes=payload.notes,
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)

    # Fetch initial price/RSI immediately so the dashboard isn't empty
    result = market_data.get_latest_price_and_rsi(stock.symbol)
    if result and "error" not in result:
        stock.last_price = result["price"]
        stock.last_rsi = result["rsi"]
        stock.last_updated = datetime.utcnow()
        db.commit()
        db.refresh(stock)

    item = StockOut.model_validate(stock)
    item.signal = market_data.get_signal(stock.last_rsi)
    return item


@app.patch("/stocks/{stock_id}", response_model=StockOut)
def update_stock(stock_id: int, payload: StockUpdate, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(stock, field, value)

    db.commit()
    db.refresh(stock)
    item = StockOut.model_validate(stock)
    item.signal = market_data.get_signal(stock.last_rsi)
    return item


@app.delete("/stocks/{stock_id}", status_code=204)
def remove_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    stock.is_active = False
    db.commit()
    return None


# ──────────────────────────────────────────────────────────────────────────
# RSI / price refresh
# ──────────────────────────────────────────────────────────────────────────
@app.post("/stocks/{stock_id}/refresh", response_model=RefreshResult)
def refresh_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    result = market_data.get_latest_price_and_rsi(stock.symbol)
    if not result or "error" in result:
        err = result.get("error", "Unknown error") if result else "No data returned"
        return RefreshResult(symbol=stock.symbol, success=False, error=err)

    stock.last_price = result["price"]
    stock.last_rsi = result["rsi"]
    stock.last_updated = datetime.utcnow()
    signal = market_data.get_signal(stock.last_rsi)

    db.add(PriceSnapshot(symbol=stock.symbol, price=result["price"], rsi_14=result["rsi"], signal=signal))
    db.commit()

    return RefreshResult(symbol=stock.symbol, success=True, price=result["price"], rsi=result["rsi"], signal=signal)


@app.post("/stocks/refresh-all", response_model=List[RefreshResult])
def refresh_all_stocks(db: Session = Depends(get_db)):
    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    results = []
    for stock in stocks:
        result = market_data.get_latest_price_and_rsi(stock.symbol)
        if not result or "error" in result:
            err = result.get("error", "Unknown error") if result else "No data returned"
            results.append(RefreshResult(symbol=stock.symbol, success=False, error=err))
            continue

        stock.last_price = result["price"]
        stock.last_rsi = result["rsi"]
        stock.last_updated = datetime.utcnow()
        signal = market_data.get_signal(stock.last_rsi)
        db.add(PriceSnapshot(symbol=stock.symbol, price=result["price"], rsi_14=result["rsi"], signal=signal))

        results.append(RefreshResult(symbol=stock.symbol, success=True, price=result["price"], rsi=result["rsi"], signal=signal))

    db.commit()
    return results


@app.get("/stocks/{stock_id}/history")
def stock_history(stock_id: int, period: str = "6mo", db: Session = Depends(get_db)):
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    hist = market_data.get_history(stock.symbol, period=period)
    if hist is None:
        raise HTTPException(status_code=502, detail="Could not fetch history")

    hist = hist.reset_index()
    hist["Date"] = hist["Date"].astype(str)
    return hist[["Date", "Open", "High", "Low", "Close", "Volume", "RSI_14"]].to_dict(orient="records")


# ──────────────────────────────────────────────────────────────────────────
# RAG endpoint
# ──────────────────────────────────────────────────────────────────────────
@app.post("/rag/query", response_model=RagResponse)
def rag_query(payload: RagQuery, db: Session = Depends(get_db)):
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")
    result = rag_engine.answer_query(db, payload.question.strip())
    return result
