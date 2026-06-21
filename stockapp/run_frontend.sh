#!/bin/bash
# Convenience launcher for the Streamlit dashboard.
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || echo "Tip: create a venv first - python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
streamlit run frontend/app.py
