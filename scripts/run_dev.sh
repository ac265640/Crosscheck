#!/usr/bin/env bash
# Starts FastAPI backend and Streamlit frontend together.
# Usage: bash scripts/run_dev.sh
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure data directories exist
mkdir -p data/uploads

echo "Starting FastAPI backend on http://localhost:8000 ..."
PYTHONPATH="$PROJECT_ROOT" uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

echo "Starting Streamlit frontend on http://localhost:8501 ..."
PYTHONPATH="$PROJECT_ROOT" streamlit run frontend/streamlit_app.py --server.port 8501

# When streamlit exits, kill backend
kill "$BACKEND_PID" 2>/dev/null || true
