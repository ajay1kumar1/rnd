"""
Thin HTTP client wrapper so Streamlit pages talk to the FastAPI backend
through one consistent module.
"""
import os
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = os.getenv("BACKEND_PORT", "8000")
API_BASE = f"http://{BACKEND_HOST}:{BACKEND_PORT}"


def search_stocks(query: str):
    resp = requests.get(f"{API_BASE}/stocks/search", params={"q": query}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def list_stocks(active_only: bool = True):
    resp = requests.get(f"{API_BASE}/stocks", params={"active_only": active_only}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def add_stock(symbol: str, name: str, exchange: str, buy_min, buy_max, notes: str = ""):
    payload = {
        "symbol": symbol,
        "name": name,
        "exchange": exchange,
        "buy_price_min": buy_min,
        "buy_price_max": buy_max,
        "notes": notes,
    }
    resp = requests.post(f"{API_BASE}/stocks", json=payload, timeout=20)
    return resp


def update_stock(stock_id: int, **fields):
    resp = requests.patch(f"{API_BASE}/stocks/{stock_id}", json=fields, timeout=15)
    resp.raise_for_status()
    return resp.json()


def remove_stock(stock_id: int):
    resp = requests.delete(f"{API_BASE}/stocks/{stock_id}", timeout=15)
    return resp


def refresh_stock(stock_id: int):
    resp = requests.post(f"{API_BASE}/stocks/{stock_id}/refresh", timeout=30)
    resp.raise_for_status()
    return resp.json()


def refresh_all_stocks():
    resp = requests.post(f"{API_BASE}/stocks/refresh-all", timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_history(stock_id: int, period: str = "6mo"):
    resp = requests.get(f"{API_BASE}/stocks/{stock_id}/history", params={"period": period}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def rag_query(question: str):
    resp = requests.post(f"{API_BASE}/rag/query", json={"question": question}, timeout=60)
    resp.raise_for_status()
    return resp.json()


def health_check():
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
