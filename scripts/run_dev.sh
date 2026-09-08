#!/usr/bin/env bash
# Starts FastAPI backend + Next.js React frontend together.
# Usage: bash scripts/run_dev.sh
set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Ensure data directories exist
mkdir -p data/uploads

echo ""
echo "╔═══════════════════════════════════════════╗"
echo "║           Crosscheck Dev Server           ║"
echo "╚═══════════════════════════════════════════╝"
echo ""
echo "  → FastAPI backend:   http://localhost:8000"
echo "  → React frontend:    http://localhost:3000"
echo "  → API docs:          http://localhost:8000/docs"
echo ""

# Start FastAPI backend in background
echo "[1/2] Starting FastAPI backend..."
PYTHONPATH="$PROJECT_ROOT" python3 -m uvicorn backend.app.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  --reload-dir backend/ &
BACKEND_PID=$!

# Start Next.js React frontend
echo "[2/2] Starting Next.js frontend..."
cd "$PROJECT_ROOT/frontend-react"
NEXT_PUBLIC_API_URL="http://localhost:8000" npm run dev -- --port 3000 &
FRONTEND_PID=$!

# Cleanup on exit
cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  exit 0
}

trap cleanup INT TERM

echo ""
echo "✓ Both servers started. Press Ctrl+C to stop."
echo ""

# Wait for either process to exit
wait
