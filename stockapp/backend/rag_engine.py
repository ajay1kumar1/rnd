"""
RAG (Retrieval Augmented Generation) engine.

Knowledge sources combined into one retrievable index:
  1. Static strategy notes (RSI theory, swing trading rules) from rag_kb/strategy_notes.py
  2. Live data about the user's own stocks (symbol, buy range, last RSI/price, signal)
     pulled fresh from the SQLite DB at query time, so answers reflect current state.

Pipeline:
  query -> embed query -> similarity search against in-memory Chroma collection
        -> top-k chunks -> build prompt -> Ollama generate (if available)
        -> else: fallback to returning the retrieved chunks directly (no LLM)
"""
import json
from datetime import datetime
from typing import List, Dict

import chromadb
import httpx
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import Stock
from rag_kb.strategy_notes import ALL_DOCS

_embedder = None
_chroma_client = None
_collection = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _embedder


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _chroma_client.get_or_create_collection(name="swing_trade_kb")
    return _collection


def index_static_knowledge_base():
    """
    Embed and store the static strategy notes into Chroma.
    Safe to call repeatedly (upserts by id), e.g. on backend startup.
    """
    collection = _get_collection()
    embedder = _get_embedder()

    ids = [doc["id"] for doc in ALL_DOCS]
    texts = [doc["text"] for doc in ALL_DOCS]
    metadatas = [{"title": doc["title"], "source": "strategy_kb"} for doc in ALL_DOCS]
    embeddings = embedder.encode(texts).tolist()

    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)


def _stock_to_text(stock: Stock) -> str:
    """Render one Stock row as a natural-language chunk for retrieval."""
    price_range = ""
    if stock.buy_price_min is not None and stock.buy_price_max is not None:
        price_range = f"Your configured buy price range is {stock.buy_price_min} to {stock.buy_price_max}."

    rsi_text = f"Last known RSI(14) is {stock.last_rsi}." if stock.last_rsi is not None else "RSI has not been fetched yet."
    price_text = f"Last known price is {stock.last_price}." if stock.last_price is not None else "Price has not been fetched yet."
    updated_text = f"Data last updated at {stock.last_updated}." if stock.last_updated else "Data has not been refreshed yet."
    notes_text = f"User notes: {stock.notes}" if stock.notes else ""

    return (
        f"Stock {stock.name} ({stock.symbol}) on {stock.exchange} is on your watchlist. "
        f"{price_range} {rsi_text} {price_text} {updated_text} {notes_text}"
    ).strip()


def index_user_stocks(db: Session):
    """
    Embed and store current user stock rows into Chroma under a separate id namespace
    (prefixed with "stock_") so they can be refreshed independently of the static KB.
    """
    collection = _get_collection()
    embedder = _get_embedder()

    stocks = db.query(Stock).filter(Stock.is_active == True).all()  # noqa: E712
    if not stocks:
        return

    ids = [f"stock_{s.symbol}" for s in stocks]
    texts = [_stock_to_text(s) for s in stocks]
    metadatas = [{"title": s.name, "source": "user_stock", "symbol": s.symbol} for s in stocks]
    embeddings = embedder.encode(texts).tolist()

    collection.upsert(ids=ids, documents=texts, metadatas=metadatas, embeddings=embeddings)


def retrieve(query: str, top_k: int = 4) -> List[Dict]:
    """Return the top_k most relevant chunks (static KB + user stock data) for a query."""
    collection = _get_collection()
    embedder = _get_embedder()

    query_embedding = embedder.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=top_k)

    chunks = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        chunks.append({"text": doc, "title": meta.get("title", ""), "source": meta.get("source", "")})
    return chunks


def _try_ollama_generate(prompt: str) -> str:
    """Call local Ollama server if available; raise on failure so caller can fall back."""
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"
    payload = {"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False}
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()


_static_kb_indexed = False


def answer_query(db: Session, question: str) -> Dict:
    """
    Full RAG pipeline: ensure static KB is indexed, refresh user-stock embeddings,
    retrieve relevant chunks, then generate an answer via Ollama (or fall back to
    raw retrieval if Ollama is not reachable).
    """
    global _static_kb_indexed
    try:
        if not _static_kb_indexed:
            index_static_knowledge_base()
            _static_kb_indexed = True
        index_user_stocks(db)  # keep user data fresh on every query
        chunks = retrieve(question, top_k=4)
    except Exception as e:
        return {
            "answer": (
                "I couldn't load the embedding model needed for search. This usually means "
                "either the model is still downloading on first run, or there's no internet "
                f"connection available right now. Details: {e}"
            ),
            "sources": [],
            "mode": "error",
        }

    if not chunks:
        return {
            "answer": "I don't have enough indexed information yet to answer that. Try adding some stocks first.",
            "sources": [],
            "mode": "no_context",
        }

    context_block = "\n\n".join(f"[{c['title']}]\n{c['text']}" for c in chunks)
    prompt = (
        "You are a swing trading assistant for an Indian stock (NSE/BSE) dashboard. "
        "Answer the user's question using ONLY the context below. Be concise and concrete. "
        "If the question is about a specific stock and the context has its RSI/price, state it plainly.\n\n"
        f"CONTEXT:\n{context_block}\n\n"
        f"QUESTION: {question}\n\n"
        "ANSWER:"
    )

    try:
        answer = _try_ollama_generate(prompt)
        if not answer:
            raise ValueError("Empty response from Ollama")
        mode = "llm"
    except Exception:
        # Fallback: no LLM available, just present the retrieved context directly
        answer = (
            "Local LLM (Ollama) is not reachable, so here is the most relevant information "
            "retrieved directly:\n\n" + "\n\n".join(f"• {c['title']}: {c['text'].strip()}" for c in chunks)
        )
        mode = "retrieval_only"

    return {
        "answer": answer,
        "sources": [c["title"] for c in chunks],
        "mode": mode,
    }
