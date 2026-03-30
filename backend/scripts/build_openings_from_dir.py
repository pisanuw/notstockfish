"""Build a weighted opening book from all PGN files in a directory tree.

Example:
  python scripts/build_openings_from_dir.py \
    --pgn-dir "../data_sources/Lichess Elite Database" \
      --output data/openings.json \
      --polyglot-output data/openings.bin \
      --max-plies 16
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

import chess.pgn

from build_openings_json import write_polyglot_book


def _parse_elo(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _eligible_by_elo(game: chess.pgn.Game, min_elo: Optional[int]) -> bool:
    if min_elo is None:
        return True

    white_elo = _parse_elo(game.headers.get("WhiteElo"))
    black_elo = _parse_elo(game.headers.get("BlackElo"))
    if white_elo is None or black_elo is None:
        return False
    return white_elo >= min_elo and black_elo >= min_elo


def _iter_pgn_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.pgn") if path.is_file())


def _to_serializable(weights: dict[str, dict[str, int]]) -> dict[str, list[dict[str, int | str]]]:
    serializable: dict[str, list[dict[str, int | str]]] = {}
    for fen_prefix, move_weights in sorted(weights.items()):
        entries = [
            {"move": move, "weight": weight}
            for move, weight in sorted(move_weights.items(), key=lambda item: item[1], reverse=True)
        ]
        serializable[fen_prefix] = entries
    return serializable


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as out:
        json.dump(payload, out)
    temp_path.replace(path)


def _load_weights_from_output(path: Path) -> dict[str, dict[str, int]]:
    weights: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    if not path.exists():
        return weights

    payload = json.loads(path.read_text(encoding="utf-8"))
    for fen_prefix, entries in payload.items():
        fen_bucket = weights[fen_prefix]
        for entry in entries:
            fen_bucket[str(entry["move"])] = int(entry["weight"])

    return weights


def _load_state(path: Path, output_path: Path) -> tuple[dict[str, dict[str, int]], set[str], int, int]:
    if not path.exists():
        return _load_weights_from_output(output_path), set(), 0, 0

    payload = json.loads(path.read_text(encoding="utf-8"))
    if "weights" in payload:
        weights_payload = payload.get("weights", {})
        weights: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for fen_prefix, move_weights in weights_payload.items():
            fen_bucket = weights[fen_prefix]
            for move, weight in move_weights.items():
                fen_bucket[str(move)] = int(weight)
    else:
        weights = _load_weights_from_output(output_path)

    completed_files = {str(item) for item in payload.get("completed_files", [])}
    games_seen = int(payload.get("games_seen", 0))
    games_used = int(payload.get("games_used", 0))
    return weights, completed_files, games_seen, games_used


def _save_checkpoint(
    state_path: Path,
    output_path: Path,
    polyglot_output: Optional[Path],
    weights: dict[str, dict[str, int]],
    completed_files: set[str],
    games_seen: int,
    games_used: int,
) -> int:
    state_payload = {
        "completed_files": sorted(completed_files),
        "games_seen": games_seen,
        "games_used": games_used,
    }
    _write_json_atomic(state_path, state_payload)

    serializable = _to_serializable(weights)
    _write_json_atomic(output_path, serializable)

    polyglot_entries = 0
    if polyglot_output is not None:
        polyglot_entries = write_polyglot_book(serializable, polyglot_output)

    return polyglot_entries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build weighted opening books from all PGNs in a directory.")
    parser.add_argument("--pgn-dir", required=True, help="Directory containing .pgn files (recursive).")
    parser.add_argument("--output", required=True, help="Path to output JSON opening book.")
    parser.add_argument(
        "--polyglot-output",
        default=None,
        help="Optional path to also write a Polyglot .bin opening book.",
    )
    parser.add_argument("--max-games", type=int, default=None, help="Stop after processing this many games.")
    parser.add_argument("--max-plies", type=int, default=16, help="Only include this many plies from each game.")
    parser.add_argument("--min-elo", type=int, default=None, help="Keep games where both players meet this Elo.")
    parser.add_argument(
        "--state-path",
        default=None,
        help="Optional checkpoint file path. If omitted, uses <output>.state.json and resumes automatically.",
    )
    parser.add_argument(
        "--checkpoint-every-files",
        type=int,
        default=5,
        help="Rewrite outputs after this many newly processed PGN files. Use 1 for maximum durability.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pgn_dir = Path(args.pgn_dir)
    output_path = Path(args.output)
    polyglot_output = Path(args.polyglot_output) if args.polyglot_output else None
    state_path = Path(args.state_path) if args.state_path else output_path.with_suffix(output_path.suffix + ".state.json")
    max_plies = max(1, int(args.max_plies))
    checkpoint_every_files = max(1, int(args.checkpoint_every_files))

    if not pgn_dir.exists():
        raise FileNotFoundError(f"PGN directory not found: {pgn_dir}")

    pgn_files = _iter_pgn_files(pgn_dir)
    if not pgn_files:
        raise FileNotFoundError(f"No .pgn files found under: {pgn_dir}")

    weights, completed_files, games_seen, games_used = _load_state(state_path, output_path)
    polyglot_entries = 0
    files_since_checkpoint = 0

    if completed_files:
        print(
            "Resuming from checkpoint.",
            f"completed_files={len(completed_files)}",
            f"games_seen={games_seen}",
            f"games_used={games_used}",
            f"state_path={state_path}",
        )

    for index, pgn_file in enumerate(pgn_files, start=1):
        pgn_key = str(pgn_file.resolve())
        if pgn_key in completed_files:
            print(f"[{index}/{len(pgn_files)}] Skipping completed {pgn_file}")
            continue

        print(f"[{index}/{len(pgn_files)}] {pgn_file}")
        with pgn_file.open("r", encoding="utf-8", errors="replace") as handle:
            while True:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break

                games_seen += 1
                if args.max_games is not None and games_seen > args.max_games:
                    break

                if not _eligible_by_elo(game, args.min_elo):
                    continue

                games_used += 1
                board = game.board()
                ply = 0
                for move in game.mainline_moves():
                    if ply >= max_plies:
                        break

                    fen_prefix = " ".join(board.fen().split(" ")[:4])
                    weights[fen_prefix][move.uci()] += 1
                    board.push(move)
                    ply += 1

        completed_files.add(pgn_key)
        files_since_checkpoint += 1
        if files_since_checkpoint >= checkpoint_every_files:
            polyglot_entries = _save_checkpoint(
                state_path=state_path,
                output_path=output_path,
                polyglot_output=polyglot_output,
                weights=weights,
                completed_files=completed_files,
                games_seen=games_seen,
                games_used=games_used,
            )
            files_since_checkpoint = 0
            print(
                "Checkpoint saved.",
                f"completed_files={len(completed_files)}",
                f"games_seen={games_seen}",
                f"games_used={games_used}",
                f"unique_positions={len(weights)}",
                *([f"polyglot_entries={polyglot_entries}"] if polyglot_output is not None else []),
            )

        if args.max_games is not None and games_seen > args.max_games:
            break

    polyglot_entries = _save_checkpoint(
        state_path=state_path,
        output_path=output_path,
        polyglot_output=polyglot_output,
        weights=weights,
        completed_files=completed_files,
        games_seen=games_seen,
        games_used=games_used,
    )

    print(
        "Built opening books.",
        f"games_seen={games_seen}",
        f"games_used={games_used}",
        f"unique_positions={len(weights)}",
        f"json_output={output_path}",
        f"state_path={state_path}",
        *(
            [f"polyglot_output={polyglot_output}", f"polyglot_entries={polyglot_entries}"]
            if polyglot_output is not None
            else []
        ),
    )


if __name__ == "__main__":
    main()
