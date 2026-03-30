"""Quick benchmark harness for engine latency and node counts.

Usage:
  python scripts/benchmark_engines.py
  python scripts/benchmark_engines.py --engine-ids v1 v2 v4
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import chess

# Allow running as a script from backend/scripts
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engines import get_engine, list_engines  # noqa: E402


DEFAULT_FENS = [
    chess.STARTING_FEN,
    "r1bqkbnr/pppp1ppp/2n5/4p3/1bP1P3/2N2N2/PP1P1PPP/R1BQKB1R w KQkq - 2 4",
    "r2q1rk1/pp2bppp/2npbn2/2p1p3/2P1P3/2NP1N1P/PPQ1BPP1/R1B2RK1 w - - 2 10",
    "2r2rk1/1bq1bppp/p2ppn2/1pn5/3NP3/1BN1B2P/PPQ2PP1/2RR2K1 w - - 2 16",
    "8/5pk1/2p2np1/3p4/3P4/2P2N2/5PPP/4R1K1 w - - 0 28",
]


@dataclass
class BenchmarkResult:
    engine_id: str
    engine_name: str
    avg_ms: float
    min_ms: float
    max_ms: float
    avg_nodes: float


def create_benchmark_report(results: list[BenchmarkResult], engine_ids: list[str]) -> dict:
    """Build a serializable benchmark report payload."""
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "fens": DEFAULT_FENS,
        "engine_ids": engine_ids,
        "results": [asdict(result) for result in results],
    }


def save_benchmark_report(report: dict, output_json: Path | None, history_jsonl: Path | None) -> None:
    """Persist benchmark results to JSON and/or append-only JSONL history."""
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with output_json.open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    if history_jsonl is not None:
        history_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with history_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(report) + "\n")


def _implemented_engine_ids() -> list[str]:
    ids: list[str] = []
    for meta in list_engines(check_implemented=True):
        if meta.get("implemented"):
            ids.append(meta["version"])
    return ids


def benchmark_engine(engine_id: str, fens: Iterable[str]) -> BenchmarkResult:
    engine = get_engine(engine_id)
    latencies: list[float] = []
    nodes: list[int] = []

    for fen in fens:
        board = chess.Board(fen)
        start = time.perf_counter()
        info = engine.get_move_with_info(board)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        latencies.append(elapsed_ms)
        nodes.append(int(info.nodes_searched or 0))

    return BenchmarkResult(
        engine_id=engine_id,
        engine_name=engine.name,
        avg_ms=statistics.mean(latencies),
        min_ms=min(latencies),
        max_ms=max(latencies),
        avg_nodes=statistics.mean(nodes),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark move generation latency across engines.")
    parser.add_argument("--engine-ids", nargs="*", default=None, help="Engine IDs to benchmark (default: all implemented).")
    parser.add_argument("--output-json", default=None, help="Optional path to write the latest benchmark report as JSON.")
    parser.add_argument(
        "--history-jsonl",
        default=None,
        help="Optional path to append benchmark reports as JSON lines for regression tracking.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine_ids = args.engine_ids or _implemented_engine_ids()
    output_json = Path(args.output_json) if args.output_json else None
    history_jsonl = Path(args.history_jsonl) if args.history_jsonl else None

    if not engine_ids:
        raise RuntimeError("No implemented engines found to benchmark.")

    results = [benchmark_engine(engine_id, DEFAULT_FENS) for engine_id in engine_ids]
    report = create_benchmark_report(results, engine_ids)
    save_benchmark_report(report, output_json, history_jsonl)

    print("engine_id | name | avg_ms | min_ms | max_ms | avg_nodes")
    print("-" * 72)
    for r in results:
        print(
            f"{r.engine_id:8} | {r.engine_name:24.24} | "
            f"{r.avg_ms:7.2f} | {r.min_ms:7.2f} | {r.max_ms:7.2f} | {r.avg_nodes:9.1f}"
        )

    if output_json is not None:
        print(f"wrote_json={output_json}")
    if history_jsonl is not None:
        print(f"appended_history={history_jsonl}")


if __name__ == "__main__":
    main()
