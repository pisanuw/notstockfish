#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="8000"
FRONTEND_PORT="5173"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required but was not found in PATH."
  exit 1
fi

if ! command -v lsof >/dev/null 2>&1; then
  echo "lsof is required but was not found in PATH."
  exit 1
fi

if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
  PYTHON_CMD="$BACKEND_DIR/.venv/bin/python"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_CMD="$ROOT_DIR/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="python3"
else
  echo "Python 3 is required but was not found in PATH."
  exit 1
fi

BACKEND_PID=""
FRONTEND_PID=""

kill_processes_on_port() {
  local port="$1"
  local pids
  local remaining

  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    return
  fi

  echo "Freeing port $port (PID(s): $(echo "$pids" | tr '\n' ' '))"
  echo "$pids" | xargs kill 2>/dev/null || true
  sleep 1

  remaining="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [ -n "$remaining" ]; then
    echo "Force killing remaining PID(s) on port $port: $(echo "$remaining" | tr '\n' ' ')"
    echo "$remaining" | xargs kill -9 2>/dev/null || true
  fi
}

cleanup() {
  if [ -n "$BACKEND_PID" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [ -n "$FRONTEND_PID" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}

trap cleanup INT TERM EXIT

kill_processes_on_port "$BACKEND_PORT"
kill_processes_on_port "$FRONTEND_PORT"

echo "Starting backend on http://localhost:$BACKEND_PORT"
(
  cd "$BACKEND_DIR"
  "$PYTHON_CMD" -m uvicorn main:app --reload --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "Starting frontend on http://localhost:$FRONTEND_PORT"
(
  cd "$FRONTEND_DIR"
  npm run dev -- --port "$FRONTEND_PORT" --strictPort
) &
FRONTEND_PID=$!

while true; do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "Backend process exited. Stopping frontend."
    break
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "Frontend process exited. Stopping backend."
    break
  fi

  sleep 1
done

cleanup
wait "$BACKEND_PID" 2>/dev/null || true
wait "$FRONTEND_PID" 2>/dev/null || true
