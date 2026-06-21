#!/bin/bash
# Convenience launcher for the FastAPI backend.
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || echo "Tip: create a venv first - python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
uvicorn backend.main:app --reload --port 8000
