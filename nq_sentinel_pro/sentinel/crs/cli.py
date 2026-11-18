"""Daily CRS CLI."""
from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
from .manual import load_manual_evidence
from .runner import run_report

def main(argv=None):
    parser = argparse.ArgumentParser(description="CRS 1.0 research-only cross-asset risk monitor")
    parser.add_argument("--as-of", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--database", default="data/crs/crs.duckdb")
    parser.add_argument("--output", default="reports/crs")
    parser.add_argument("--parquet", default="data/crs/parquet")
    parser.add_argument("--manual-evidence")
    parser.add_argument("--state-history", default="data/crs/state.json",
                        help="Local state-machine memory; contains no positions or raw market data.")
    parser.add_argument("--confirmed-market-failure", action="store_true",
                        help="Explicitly record a manually confirmed market-function failure; requires human verification.")
    parser.add_argument("--nq-report", help="Optional public NQ-Sentinel report path; displayed separately and never mixed into CRS.")
    args = parser.parse_args(argv)
    date.fromisoformat(args.as_of)
    manual = load_manual_evidence(args.manual_evidence, args.as_of) if args.manual_evidence else None
    report, paths = run_report(args.as_of, args.database, args.output, args.parquet,
                               manual=manual,
                               emergency_market_failure=args.confirmed_market_failure,
                               nq_report=args.nq_report,
                               state_history_file=args.state_history)
    print(f"CRS {report['asof']}: {report['score_result']['status']} "
          f"score={report['score_result']['score']} state={report['state_machine']['state']}")
    print(paths)
    return 0 if report["score_result"]["score"] is not None else 2

if __name__ == "__main__":
    raise SystemExit(main())
