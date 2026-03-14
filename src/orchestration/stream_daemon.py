"""
Watch the Excel feed for new rows and run the full pipeline on each event.

Trigger order per detected update:
    1) bronze load
    2) silver transform
    3) gold build
    4) churn prediction (predict-only, no retrain)
"""

from __future__ import annotations

import argparse
import os
import threading
import time
from zipfile import BadZipFile
from pathlib import Path

import pandas as pd

from src.ingestion.load_excel_to_bronze import load_excel_to_bronze
from src.etl.transform_to_silver import transform_bronze_to_silver
from src.etl.build_gold_schema import build_gold_from_silver
from src.ml.predict_churn import run_pipeline


DEFAULT_EXCEL_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "raw" / "new_churn.xlsx"
)
DEFAULT_SHEET_NAME = "E Comm"


def _read_row_count(excel_path: Path, sheet_name: str) -> int:
    df = pd.read_excel(excel_path, sheet_name=sheet_name, engine="openpyxl")
    return len(df)


def _read_row_count_with_retry(
    excel_path: Path,
    sheet_name: str,
    retries: int = 8,
    retry_wait_sec: float = 0.6,
) -> int:
    last_err: Exception | None = None
    for _ in range(retries):
        try:
            return _read_row_count(excel_path, sheet_name)
        except (EOFError, BadZipFile, PermissionError, ValueError) as exc:
            last_err = exc
            time.sleep(retry_wait_sec)

    raise RuntimeError(
        f"failed to read Excel row count after {retries} attempts: {last_err}"
    )


def _run_full_pipeline_cycle() -> None:
    print("[watcher] running cycle: bronze -> silver -> gold -> predict-only")
    load_excel_to_bronze()
    transform_bronze_to_silver()
    build_gold_from_silver()
    run_pipeline(retrain=False)
    print("[watcher] cycle complete")


def run_stream_watcher(
    interval_sec: int,
    excel_path: Path,
    sheet_name: str,
    startup_pipeline: bool = False,
) -> None:
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    run_lock = threading.Lock()
    while True:
        try:
            last_count = _read_row_count_with_retry(excel_path, sheet_name)
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[watcher] waiting for stable Excel read on startup: {exc}")
            time.sleep(interval_sec)

    print(
        f"[watcher] started | file={excel_path} sheet={sheet_name} "
        f"poll={interval_sec}s baseline_rows={last_count}"
    )

    if startup_pipeline:
        print("[watcher] startup pipeline requested")
        with run_lock:
            _run_full_pipeline_cycle()

    while True:
        try:
            current_count = _read_row_count_with_retry(excel_path, sheet_name)

            if current_count > last_count:
                delta = current_count - last_count
                print(f"[watcher] detected {delta} new rows (total={current_count})")

                acquired = run_lock.acquire(blocking=False)
                if not acquired:
                    print("[watcher] previous cycle still running; skipping this poll")
                else:
                    try:
                        _run_full_pipeline_cycle()
                        last_count = current_count
                    finally:
                        run_lock.release()

            elif current_count < last_count:
                # Handle file replacement/truncation safely.
                print(
                    f"[watcher] row count decreased ({last_count} -> {current_count}); "
                    "running full cycle and resetting baseline"
                )
                with run_lock:
                    _run_full_pipeline_cycle()
                    last_count = current_count

        except Exception as exc:  # noqa: BLE001
            print(f"[watcher] poll error: {exc}")

        time.sleep(interval_sec)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch Excel feed and trigger ETL/ML")
    parser.add_argument("--poll-interval", type=int, default=_env_int("STREAM_WATCH_INTERVAL_SEC", 5))
    parser.add_argument("--sheet", default=os.getenv("STREAM_EXCEL_SHEET", DEFAULT_SHEET_NAME))
    parser.add_argument("--excel-path", default=os.getenv("STREAM_EXCEL_PATH", str(DEFAULT_EXCEL_PATH)))
    parser.add_argument(
        "--startup-pipeline",
        action="store_true",
        default=os.getenv("STREAM_STARTUP_PIPELINE", "false").lower() == "true",
        help="Run one cycle on startup before watching",
    )
    args = parser.parse_args()

    run_stream_watcher(
        interval_sec=max(1, args.poll_interval),
        excel_path=Path(args.excel_path),
        sheet_name=args.sheet,
        startup_pipeline=args.startup_pipeline,
    )


if __name__ == "__main__":
    main()
