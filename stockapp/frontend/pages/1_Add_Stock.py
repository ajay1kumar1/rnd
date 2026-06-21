"""
Add Stock page.

Flow:
  1. User types a stock name into a textbox.
  2. On submit, the backend searches Yahoo Finance and returns matching NSE/BSE stocks.
  3. Each match is shown with an "Add" button.
  4. Clicking Add opens a small form for the buy price range + notes, then saves to SQLite.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from frontend import api_client as api

st.set_page_config(page_title="Add Stock", page_icon="➕", layout="wide")
st.title("➕ Add a Stock to Your Watchlist")
st.caption("Search by company name or symbol (NSE/BSE). Matches come live from Yahoo Finance.")

if not api.health_check():
    st.error("⚠️ Backend API not reachable. Start it with: `uvicorn backend.main:app --reload --port 8000`")
    st.stop()

if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "pending_add" not in st.session_state:
    st.session_state.pending_add = None  # holds the symbol currently being configured for add

# ── Search box ────────────────────────────────────────────────────────────────
with st.form("search_form", clear_on_submit=False):
    query = st.text_input("Stock name or symbol", placeholder="e.g. Reliance, TCS, HDFC Bank, INFY")
    submitted = st.form_submit_button("🔍 Search")

if submitted:
    if not query.strip():
        st.warning("Type a stock name first.")
    else:
        with st.spinner("Searching..."):
            try:
                st.session_state.search_results = api.search_stocks(query.strip())
            except Exception as e:
                st.error(f"Search failed: {e}")
                st.session_state.search_results = []
        st.session_state.pending_add = None

# ── Existing watchlist symbols, to disable duplicate adds ─────────────────────
try:
    existing_symbols = {s["symbol"] for s in api.list_stocks(active_only=True)}
except Exception:
    existing_symbols = set()

# ── Results list ────────────────────────────────────────────────────────────
results = st.session_state.search_results

if submitted and not results:
    st.info("No matching NSE/BSE stocks found. Try a different name or the exact ticker.")

if results:
    st.subheader(f"Found {len(results)} match(es)")
    for r in results:
        symbol = r["symbol"]
        already_added = symbol in existing_symbols

        with st.container(border=True):
            c1, c2, c3 = st.columns([3, 1.2, 1.2])
            with c1:
                st.markdown(f"**{r['name']}**")
                st.caption(f"{symbol} · {r['exchange']}")
            with c2:
                if already_added:
                    st.success("✅ Already added")
            with c3:
                if not already_added:
                    if st.button("➕ Add", key=f"add_btn_{symbol}", use_container_width=True):
                        st.session_state.pending_add = r

            # Inline form to capture buy price range once "Add" is clicked
            if st.session_state.pending_add and st.session_state.pending_add["symbol"] == symbol:
                with st.form(key=f"add_form_{symbol}"):
                    st.markdown(f"**Configure buy range for {r['name']}**")
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        buy_min = st.number_input("Buy price min (₹)", min_value=0.0, step=1.0, key=f"min_{symbol}")
                    with fc2:
                        buy_max = st.number_input("Buy price max (₹)", min_value=0.0, step=1.0, key=f"max_{symbol}")
                    notes = st.text_area("Notes (optional)", key=f"notes_{symbol}",
                                          placeholder="e.g. waiting for RSI dip below 40 near support at ₹2400")
                    confirm = st.form_submit_button("✅ Confirm & Save to Watchlist")

                    if confirm:
                        if buy_max and buy_min and buy_max < buy_min:
                            st.error("Max price must be greater than or equal to min price.")
                        else:
                            resp = api.add_stock(
                                symbol=symbol,
                                name=r["name"],
                                exchange=r["exchange"],
                                buy_min=buy_min or None,
                                buy_max=buy_max or None,
                                notes=notes,
                            )
                            if resp.status_code in (200, 201):
                                st.success(f"{r['name']} added to your watchlist! Fetching initial RSI...")
                                st.session_state.pending_add = None
                                st.session_state.search_results = []
                                st.rerun()
                            elif resp.status_code == 409:
                                st.warning("This stock is already on your watchlist.")
                            else:
                                st.error(f"Failed to add: {resp.text}")

st.divider()
st.caption(
    "💡 Tip: the buy price range is used purely as your own reference — combine it with the "
    "RSI(14) < 40 signal on the Dashboard page to decide on entries."
)
