"""
Swing Trade Dashboard - Main Streamlit entry point (Dashboard page).

Run with:
    streamlit run frontend/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import pandas as pd
import streamlit as st

from frontend import api_client as api

st.set_page_config(page_title="Swing Trade Dashboard", page_icon="📈", layout="wide")

# ── Auto-refresh control (lives in session state) ───────────────────────────
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = False
if "refresh_interval" not in st.session_state:
    st.session_state.refresh_interval = 300

st.title("📈 Swing Trade Dashboard")
st.caption("Strategy: Buy when RSI(14) drops below 40 — NSE/BSE stocks, live via Yahoo Finance")

if not api.health_check():
    st.error(
        "⚠️ Cannot reach the backend API. Make sure FastAPI is running:\n\n"
        "`uvicorn backend.main:app --reload --port 8000`"
    )
    st.stop()

# ── Top control bar ──────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns([1.2, 1.2, 1.6, 2])
with col1:
    if st.button("🔄 Refresh All Now", use_container_width=True):
        with st.spinner("Fetching latest prices & RSI..."):
            results = api.refresh_all_stocks()
        ok = sum(1 for r in results if r["success"])
        st.success(f"Refreshed {ok}/{len(results)} stocks.")
        st.rerun()

with col2:
    st.session_state.auto_refresh = st.toggle("Auto-refresh", value=st.session_state.auto_refresh)

with col3:
    st.session_state.refresh_interval = st.selectbox(
        "Interval", options=[60, 120, 300, 600, 900],
        format_func=lambda s: f"{s // 60} min" if s >= 60 else f"{s} sec",
        index=[60, 120, 300, 600, 900].index(st.session_state.refresh_interval)
        if st.session_state.refresh_interval in [60, 120, 300, 600, 900] else 2,
        disabled=not st.session_state.auto_refresh,
        label_visibility="collapsed",
    )

with col4:
    buy_threshold = st.slider("BUY signal threshold (RSI <)", min_value=20, max_value=50, value=40)

st.divider()

# ── Load stocks ───────────────────────────────────────────────────────────────
stocks = api.list_stocks(active_only=True)

if not stocks:
    st.info("👋 No stocks on your watchlist yet. Go to **Add Stock** in the sidebar to add your first one.")
    st.stop()

df = pd.DataFrame(stocks)


def classify(rsi):
    if rsi is None:
        return "UNKNOWN"
    if rsi < buy_threshold:
        return "BUY"
    if rsi < buy_threshold + 10:
        return "WATCH"
    return "HOLD"


df["signal"] = df["last_rsi"].apply(classify)

# ── Summary metrics ──────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Watchlist", len(df))
m2.metric("🟢 BUY signals", int((df["signal"] == "BUY").sum()))
m3.metric("🟡 WATCH (approaching)", int((df["signal"] == "WATCH").sum()))
m4.metric("⚪ HOLD", int((df["signal"] == "HOLD").sum()))

st.divider()


def signal_badge(sig):
    colors = {"BUY": "🟢 BUY", "WATCH": "🟡 WATCH", "HOLD": "⚪ HOLD", "UNKNOWN": "❔ N/A"}
    return colors.get(sig, sig)


def in_range(row):
    if row["last_price"] is None or row["buy_price_min"] is None or row["buy_price_max"] is None:
        return ""
    if row["buy_price_min"] <= row["last_price"] <= row["buy_price_max"]:
        return "✅ In range"
    return "—"


df_display = df.copy()
df_display["Signal"] = df_display["signal"].apply(signal_badge)
df_display["Price in buy range?"] = df_display.apply(in_range, axis=1)
df_display["Buy Range"] = df_display.apply(
    lambda r: f"₹{r['buy_price_min']} – ₹{r['buy_price_max']}"
    if r["buy_price_min"] is not None and r["buy_price_max"] is not None else "—",
    axis=1,
)

show_cols = ["name", "symbol", "exchange", "last_price", "last_rsi", "Signal", "Buy Range", "Price in buy range?", "last_updated"]
rename = {
    "name": "Stock", "symbol": "Symbol", "exchange": "Exch.",
    "last_price": "Price (₹)", "last_rsi": "RSI(14)", "last_updated": "Last Updated",
}

st.subheader("Watchlist")
sort_signal_order = {"BUY": 0, "WATCH": 1, "HOLD": 2, "UNKNOWN": 3}
df_display["_sort"] = df_display["signal"].map(sort_signal_order)
df_display = df_display.sort_values("_sort")

st.dataframe(
    df_display[show_cols].rename(columns=rename),
    use_container_width=True,
    hide_index=True,
    height=min(45 * (len(df_display) + 1), 500),
)

st.divider()

# ── Per-stock detail & actions ───────────────────────────────────────────────
st.subheader("Stock Details & Chart")
stock_names = {f"{row['name']} ({row['symbol']})": row["id"] for _, row in df.iterrows()}
selected_label = st.selectbox("Select a stock to view chart / edit / remove", options=list(stock_names.keys()))
selected_id = stock_names[selected_label]
selected_row = df[df["id"] == selected_id].iloc[0]

dcol1, dcol2, dcol3 = st.columns([2, 1, 1])
with dcol1:
    st.markdown(f"### {selected_row['name']}")
    st.caption(f"{selected_row['symbol']} · {selected_row['exchange']}")
    rsi_val = selected_row["last_rsi"]
    price_val = selected_row["last_price"]
    sig = classify(rsi_val)
    sig_color = {"BUY": "green", "WATCH": "orange", "HOLD": "gray", "UNKNOWN": "gray"}[sig]
    st.markdown(f"**Price:** ₹{price_val} &nbsp;&nbsp; **RSI(14):** {rsi_val} &nbsp;&nbsp; "
                f"**Signal:** :{sig_color}[{sig}]")
    if selected_row["notes"]:
        st.caption(f"📝 {selected_row['notes']}")

with dcol2:
    if st.button("🔄 Refresh this stock", use_container_width=True):
        with st.spinner("Refreshing..."):
            res = api.refresh_stock(int(selected_id))
        if res["success"]:
            st.success(f"Updated — Price ₹{res['price']}, RSI {res['rsi']}")
            st.rerun()
        else:
            st.error(f"Refresh failed: {res.get('error')}")

with dcol3:
    if st.button("🗑️ Remove from watchlist", use_container_width=True):
        api.remove_stock(int(selected_id))
        st.success("Removed.")
        time.sleep(0.5)
        st.rerun()

with st.expander("✏️ Edit buy price range / notes"):
    new_min = st.number_input("Buy price min (₹)", value=float(selected_row["buy_price_min"] or 0.0), step=1.0)
    new_max = st.number_input("Buy price max (₹)", value=float(selected_row["buy_price_max"] or 0.0), step=1.0)
    new_notes = st.text_area("Notes", value=selected_row["notes"] or "")
    if st.button("Save changes"):
        api.update_stock(int(selected_id), buy_price_min=new_min, buy_price_max=new_max, notes=new_notes)
        st.success("Saved.")
        st.rerun()

# ── Chart ─────────────────────────────────────────────────────────────────────
period = st.radio("Chart period", options=["1mo", "3mo", "6mo", "1y"], index=2, horizontal=True)
try:
    hist = api.get_history(int(selected_id), period=period)
    hist_df = pd.DataFrame(hist)
    hist_df["Date"] = pd.to_datetime(hist_df["Date"])

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3],
                         vertical_spacing=0.05, subplot_titles=("Price", "RSI(14)"))

    fig.add_trace(go.Candlestick(
        x=hist_df["Date"], open=hist_df["Open"], high=hist_df["High"],
        low=hist_df["Low"], close=hist_df["Close"], name="Price"
    ), row=1, col=1)

    if selected_row["buy_price_min"] and selected_row["buy_price_max"]:
        fig.add_hrect(y0=selected_row["buy_price_min"], y1=selected_row["buy_price_max"],
                      fillcolor="green", opacity=0.12, line_width=0, row=1, col=1)

    fig.add_trace(go.Scatter(x=hist_df["Date"], y=hist_df["RSI_14"], name="RSI(14)",
                              line=dict(color="purple")), row=2, col=1)
    fig.add_hline(y=buy_threshold, line_dash="dash", line_color="green",
                  annotation_text=f"Buy < {buy_threshold}", row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="red", row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, showlegend=False,
                       margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)
except Exception as e:
    st.warning(f"Could not load chart: {e}")

# ── Auto refresh loop ─────────────────────────────────────────────────────────
if st.session_state.auto_refresh:
    st.caption(f"⏱️ Auto-refreshing every {st.session_state.refresh_interval} seconds...")
    time.sleep(st.session_state.refresh_interval)
    st.rerun()
