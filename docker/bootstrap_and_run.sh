#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Waiting for PostgreSQL..."
python - <<'PY'
import os
import sys
import time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
for attempt in range(90):
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[entrypoint] PostgreSQL is ready (attempt {attempt + 1})")
        sys.exit(0)
    except Exception as exc:
        print(f"[entrypoint] PostgreSQL not ready ({attempt + 1}/90): {exc}")
        time.sleep(2)

print("[entrypoint] PostgreSQL did not become ready in time")
sys.exit(1)
PY

if [ "${RUN_BOOTSTRAP:-true}" = "true" ]; then
  echo "[entrypoint] Running ETL + model bootstrap"
  python -m src.ingestion.load_excel_to_bronze
  python -m src.etl.transform_to_silver
  python -m src.etl.build_gold_schema
  python -m src.ml.predict_churn
else
  echo "[entrypoint] Skipping bootstrap (RUN_BOOTSTRAP=${RUN_BOOTSTRAP:-false})"
fi

PIDS=""

cleanup() {
  echo "[entrypoint] Stopping background processes"
  if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

if [ "${ENABLE_AUTO_SIMULATION:-false}" = "true" ]; then
  echo "[entrypoint] Starting auto-simulation"
  python -u -m src.simulation.auto_simulate \
    --interval "${AUTO_SIMULATION_INTERVAL_SEC:-30}" \
    --mode "${AUTO_SIMULATION_MODE:-new}" &
  PIDS="$PIDS $!"
else
  echo "[entrypoint] Auto-simulation disabled"
fi

echo "[entrypoint] Starting Streamlit"
exec streamlit run dashboards/app.py --server.address=0.0.0.0 --server.port=8501
