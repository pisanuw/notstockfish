"""Tests for backend utility scripts."""

import json
import sys
from pathlib import Path

import chess
import chess.polyglot

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.benchmark_engines import (  # noqa: E402
    BenchmarkResult,
    create_benchmark_report,
    save_benchmark_report,
)
from scripts.build_openings_json import (  # noqa: E402
    build_opening_book,
    write_polyglot_book,
)


def test_build_opening_book_and_polyglot_output(tmp_path):
    pgn_path = tmp_path / "sample.pgn"
    json_path = tmp_path / "openings.json"
    bin_path = tmp_path / "openings.bin"

    pgn_path.write_text(
        """[Event \"G1\"]
[Site \"?\"]
[Date \"2026.03.28\"]
[Round \"-\"]
[White \"W1\"]
[Black \"B1\"]
[Result \"*\"]
[WhiteElo \"2000\"]
[BlackElo \"2100\"]

1. e4 e5 2. Nf3 *

[Event \"G2\"]
[Site \"?\"]
[Date \"2026.03.28\"]
[Round \"-\"]
[White \"W2\"]
[Black \"B2\"]
[Result \"*\"]
[WhiteElo \"2200\"]
[BlackElo \"2050\"]

1. e4 c5 2. Nf3 *
""",
        encoding="utf-8",
    )

    games_seen, games_used, unique_positions = build_opening_book(
        pgn_path=pgn_path,
        output_path=json_path,
        max_games=None,
        max_plies=4,
        min_elo=1800,
    )

    assert games_seen == 2
    assert games_used == 2
    assert unique_positions >= 2

    book = json.loads(json_path.read_text(encoding="utf-8"))
    start_fen = " ".join(chess.Board().fen().split(" ")[:4])
    assert book[start_fen][0]["move"] == "e2e4"
    assert book[start_fen][0]["weight"] == 2

    entries_written = write_polyglot_book(book, bin_path)
    assert entries_written >= 2

    with chess.polyglot.open_reader(bin_path) as reader:
        start_entries = list(reader.find_all(chess.Board()))
        e4_entries = [entry for entry in start_entries if entry.move == chess.Move.from_uci("e2e4")]
        assert e4_entries
        assert e4_entries[0].weight == 2


def test_benchmark_report_persistence(tmp_path):
    report = create_benchmark_report(
        [
            BenchmarkResult(
                engine_id="v2",
                engine_name="Minimax + Alpha-Beta",
                avg_ms=12.5,
                min_ms=10.0,
                max_ms=18.0,
                avg_nodes=1500.0,
            )
        ],
        ["v2"],
    )

    json_path = tmp_path / "latest.json"
    history_path = tmp_path / "history.jsonl"
    save_benchmark_report(report, json_path, history_path)

    latest = json.loads(json_path.read_text(encoding="utf-8"))
    assert latest["engine_ids"] == ["v2"]
    assert latest["results"][0]["engine_id"] == "v2"

    history_lines = history_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 1
    history_entry = json.loads(history_lines[0])
    assert history_entry["results"][0]["avg_nodes"] == 1500.0