"""Build a weighted opening JSON book from PGN files.

Usage:
  python scripts/build_openings_json.py \
      --pgn /path/to/games.pgn \
      --output data/openings.generated.json \
      --max-games 20000 \
      --max-plies 16 \
      --min-elo 1800
"""

from __future__ import annotations

import argparse
import json
import struct
from collections import defaultdict
from pathlib import Path
from typing import Optional

import chess
import chess.pgn
import chess.polyglot


ENTRY_STRUCT = struct.Struct(">QHHI")


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


def build_opening_book(
    pgn_path: Path,
    output_path: Path,
    max_games: Optional[int],
    max_plies: int,
    min_elo: Optional[int],
) -> tuple[int, int, int]:
    """Build opening move weights indexed by FEN prefix.

    Returns:
        (games_seen, games_used, unique_positions)
    """
    weights: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    games_seen = 0
    games_used = 0

    with pgn_path.open("r", encoding="utf-8", errors="replace") as handle:
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break

            games_seen += 1
            if max_games is not None and games_seen > max_games:
                break

            if not _eligible_by_elo(game, min_elo):
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

    serializable: dict[str, list[dict[str, int | str]]] = {}
    for fen_prefix, move_weights in sorted(weights.items()):
        entries = [
            {"move": move, "weight": weight}
            for move, weight in sorted(move_weights.items(), key=lambda item: item[1], reverse=True)
        ]
        serializable[fen_prefix] = entries

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as out:
        json.dump(serializable, out, indent=2)

    return games_seen, games_used, len(serializable)


def _encode_polyglot_move(board: chess.Board, move: chess.Move) -> int:
    """Encode a move using the Polyglot raw move format."""
    polyglot_move = board._to_chess960(move)
    promotion_part = 0 if polyglot_move.promotion is None else polyglot_move.promotion - 1
    return (
        polyglot_move.to_square
        | (polyglot_move.from_square << 6)
        | (promotion_part << 12)
    )


def write_polyglot_book(book: dict[str, list[dict[str, int | str]]], output_path: Path) -> int:
    """Write a Polyglot .bin book from weighted FEN-prefix entries.

    Returns:
        Number of book entries written.
    """
    entries: list[tuple[int, int, int, int]] = []

    for fen_prefix, move_entries in book.items():
        board = chess.Board(f"{fen_prefix} 0 1")
        zobrist_key = chess.polyglot.zobrist_hash(board)

        for move_entry in move_entries:
            move_uci = move_entry["move"]
            weight = int(move_entry["weight"])
            move = chess.Move.from_uci(str(move_uci))
            if move not in board.legal_moves:
                continue

            raw_move = _encode_polyglot_move(board, move)
            clamped_weight = max(1, min(65535, weight))
            entries.append((zobrist_key, raw_move, clamped_weight, 0))

    entries.sort(key=lambda item: (item[0], item[1], -item[2], item[3]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as out:
        for key, raw_move, weight, learn in entries:
            out.write(ENTRY_STRUCT.pack(key, raw_move, weight, learn))

    return len(entries)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build weighted opening JSON from PGN data.")
    parser.add_argument("--pgn", required=True, help="Path to input PGN file.")
    parser.add_argument("--output", required=True, help="Path to output JSON book.")
    parser.add_argument(
        "--polyglot-output",
        default=None,
        help="Optional path to also write a Polyglot .bin opening book.",
    )
    parser.add_argument("--max-games", type=int, default=None, help="Stop after reading this many games.")
    parser.add_argument("--max-plies", type=int, default=16, help="Only include this many plies from each game.")
    parser.add_argument("--min-elo", type=int, default=None, help="Keep games where both players meet this Elo.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pgn_path = Path(args.pgn)
    output_path = Path(args.output)
    polyglot_output = Path(args.polyglot_output) if args.polyglot_output else None

    if not pgn_path.exists():
        raise FileNotFoundError(f"PGN file not found: {pgn_path}")

    games_seen, games_used, unique_positions = build_opening_book(
        pgn_path=pgn_path,
        output_path=output_path,
        max_games=args.max_games,
        max_plies=max(1, args.max_plies),
        min_elo=args.min_elo,
    )

    polyglot_entries = None
    if polyglot_output is not None:
        with output_path.open("r", encoding="utf-8") as handle:
            book = json.load(handle)
        polyglot_entries = write_polyglot_book(book, polyglot_output)

    print(
        "Built opening JSON.",
        f"games_seen={games_seen}",
        f"games_used={games_used}",
        f"unique_positions={unique_positions}",
        f"output={output_path}",
        *([f"polyglot_output={polyglot_output}", f"polyglot_entries={polyglot_entries}"] if polyglot_output else []),
    )


if __name__ == "__main__":
    main()
