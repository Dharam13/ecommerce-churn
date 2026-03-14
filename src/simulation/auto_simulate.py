"""
src/simulation/auto_simulate.py
===============================
Background auto-simulation script.

Continuously adds new random customers to the system at a set interval.
Each iteration:
  1. Generates a random customer
  2. Inserts into bronze
  3. Runs ETL (bronze → silver → gold)
  4. Predicts churn using the saved ML model
  5. Stores prediction in gold.churn_predictions

Usage:
    python -m src.simulation.auto_simulate                  # default: 30s interval
    python -m src.simulation.auto_simulate --interval 10    # every 10 seconds
    python -m src.simulation.auto_simulate --count 5        # stop after 5 customers
    python -m src.simulation.auto_simulate --mode mixed     # alternate new + activity
"""

import sys
import time
import signal
import argparse
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.simulation.engine import simulate_new_customer, simulate_activity

# ── Graceful shutdown ────────────────────────────────────
_running = True

def _handle_signal(signum, frame):
    global _running
    _running = False
    print("\n  Stopping auto-simulation (finishing current run)...")

signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


def run_auto_simulation(interval: int = 30, max_count: int = None, mode: str = "new"):
    """
    Run continuous simulation.

    Args:
        interval:  seconds between each simulation
        max_count: stop after N simulations (None = run forever)
        mode:      'new'      — only add new customers
                   'activity' — only simulate activity on existing customers
                   'mixed'    — alternate between new and activity
    """
    print("=" * 55)
    print("  AUTO-SIMULATION STARTED")
    print("=" * 55)
    print(f"  Mode     : {mode}")
    print(f"  Interval : {interval}s")
    print(f"  Max count: {max_count or 'unlimited'}")
    print(f"  Started  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Stop     : Press Ctrl+C")
    print("=" * 55)

    count = 0

    while _running:
        if max_count is not None and count >= max_count:
            print(f"\n  Reached max count ({max_count}). Stopping.")
            break

        count += 1
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Decide which simulation to run
        if mode == "new":
            sim_type = "new"
        elif mode == "activity":
            sim_type = "activity"
        else:  # mixed
            sim_type = "new" if count % 2 == 1 else "activity"

        print(f"\n  [{timestamp}] Simulation #{count} ({sim_type})...")

        try:
            if sim_type == "new":
                result = simulate_new_customer()
                cid = result["customer_id"]
                pred = result.get("prediction", {})
                prob = pred.get("churn_probability", "?") if pred else "?"
                seg = pred.get("risk_segment", "?") if pred else "?"
                print(f"    New customer {cid} added")
                print(f"    Churn probability: {prob} | Risk: {seg}")
            else:
                result = simulate_activity()
                cid = result.get("customer_id", "?")
                after = result.get("after_prediction", {})
                prob = after.get("churn_probability", "?") if after else "?"
                seg = after.get("risk_segment", "?") if after else "?"
                print(f"    Activity updated for customer {cid}")
                print(f"    New churn probability: {prob} | Risk: {seg}")

        except Exception as e:
            print(f"    ERROR: {e}")

        # Wait for next iteration
        if _running and (max_count is None or count < max_count):
            print(f"    Next simulation in {interval}s...")
            for _ in range(interval):
                if not _running:
                    break
                time.sleep(1)

    print(f"\n{'=' * 55}")
    print(f"  AUTO-SIMULATION STOPPED")
    print(f"  Total simulations: {count}")
    print(f"  Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'=' * 55}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-Simulation Background Script")
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Seconds between each simulation (default: 30)",
    )
    parser.add_argument(
        "--count", type=int, default=None,
        help="Stop after N simulations (default: run forever)",
    )
    parser.add_argument(
        "--mode", choices=["new", "activity", "mixed"], default="new",
        help="Simulation mode: 'new', 'activity', or 'mixed' (default: new)",
    )
    args = parser.parse_args()

    run_auto_simulation(
        interval=args.interval,
        max_count=args.count,
        mode=args.mode,
    )
