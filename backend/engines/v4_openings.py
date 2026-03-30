"""
v4 — Opening Book + Minimax Fallback
======================================
Looks up the current position in an opening book (Polyglot .bin format or a
bundled JSON of ECO openings). If a known opening line exists, it plays a
book move (randomly chosen from the available continuations, weighted by
frequency if provided). Once out of the book, it falls back to v2 (minimax +
alpha-beta) for the rest of the game.

Concepts covered
----------------
- Opening theory and databases
- Polyglot hash / Zobrist hashing for position lookup
- Hybrid strategies: specialised early-game + general-purpose fallback

Student TODO
------------
TODO 1: Implement `_load_book(path)`.
    Load the JSON opening book from the given path.
    The expected schema is:
        { "<fen_prefix>": [{"move": "<uci>", "weight": <int>}, ...], ... }
    where the fen_prefix is the FEN without the halfmove / fullmove counters.
    Store it in self._book.

TODO 2: Implement `_book_move(board)`.
    Compute the FEN prefix for the current board and look it up in self._book.
    If found, pick a move:
      - Filter to only moves that are legal on the current board.
      - Return a random choice weighted by the "weight" field.
    Return None if no book move is available.

TODO 3: Implement `get_move(board)`.
    1. Try _book_move(board) — return if not None.
    2. Fall back to self._fallback.get_move(board).
"""

import json
import random
from pathlib import Path
from typing import Optional

import chess
import chess.polyglot

from .base import ChessEngine, MoveInfo
from .v2_minimax import MinimaxEngine

_DATA_DIR = Path(__file__).parent.parent / "data"
_BOOK_FILE = _DATA_DIR / "openings.json"
_BOOK_BIN_FILE = _DATA_DIR / "openings.bin"


class OpeningBookEngine(ChessEngine):
    name = "Opening Book + Minimax"
    description = (
        "Plays opening book moves when available, then switches to minimax "
        "with alpha-beta pruning (v2) for the middlegame and endgame."
    )
    version = "v4"

    def __init__(
        self,
        fallback_depth: int = 3,
        book_path: Optional[str] = None,
        minimum_weight: int = 1,
        use_weighted_book: bool = True,
    ):
        # Fallback engine used once we leave the opening book
        self._fallback = MinimaxEngine(depth=fallback_depth)
        # Opening book: fen_prefix → list of {move, weight}
        self._book: dict[str, list[dict]] = {}
        self._polyglot_reader: Optional[chess.polyglot.MemoryMappedReader] = None
        self._in_book = True  # set to False once we leave the book
        self._book_source = "none"
        self._minimum_weight = max(0, int(minimum_weight))
        self._use_weighted_book = bool(use_weighted_book)

        polyglot_path = None
        if book_path:
            provided = Path(book_path)
            if provided.suffix.lower() == ".bin":
                polyglot_path = provided
            elif provided.exists():
                self._load_book(provided)
                self._book_source = "json"

        if polyglot_path is None and _BOOK_BIN_FILE.exists():
            polyglot_path = _BOOK_BIN_FILE

        if polyglot_path is not None:
            self._open_polyglot(polyglot_path)

        if not self._book and _BOOK_FILE.exists():
            self._load_book(_BOOK_FILE)
            if self._book_source == "none":
                self._book_source = "json"

    def _open_polyglot(self, path: Path) -> None:
        """Open a Polyglot reader if available; otherwise stay on JSON fallback."""
        try:
            self._polyglot_reader = chess.polyglot.open_reader(path)
            self._book_source = "polyglot"
        except OSError:
            self._polyglot_reader = None

        if _BOOK_FILE.exists():
            self._load_book(_BOOK_FILE)

    # ------------------------------------------------------------------
    # TODO 1: Load opening book
    # ------------------------------------------------------------------
    def _load_book(self, path: Path) -> None:
        """Load the JSON opening book from disk.

        The file format is:
          {
            "<fen_prefix>": [
              {"move": "e2e4", "weight": 10},
              ...
            ],
            ...
          }
        where fen_prefix omits the halfmove clock and fullmove number fields.

        Args:
            path: Path to the JSON opening book file.
        """
        try:
            with open(path) as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            self._book = {}
            return

        book: dict[str, list[dict]] = {}
        for fen_prefix, entries in data.items():
            if not isinstance(fen_prefix, str) or not isinstance(entries, list):
                continue

            normalised_entries: list[dict] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                move = entry.get("move")
                weight = entry.get("weight", 1)
                if isinstance(move, str):
                    normalised_entries.append({
                        "move": move,
                        "weight": int(weight) if isinstance(weight, (int, float)) else 1,
                    })

            if normalised_entries:
                book[fen_prefix] = normalised_entries

        self._book = book

    # ------------------------------------------------------------------
    # TODO 2: Book move lookup
    # ------------------------------------------------------------------
    def _book_move(self, board: chess.Board) -> Optional[chess.Move]:
        """Return a book move for the current position, or None.

        Compute the FEN prefix (first 4 space-separated fields of the FEN,
        which omit the halfmove clock and fullmove number).
        Look it up in self._book. Filter to legal moves and pick one weighted
        by the "weight" field.

        Args:
            board: Current board position.

        Returns:
            A legal chess.Move from the book, or None if not in the book.
        """
        polyglot_move = self._polyglot_move(board)
        if polyglot_move is not None:
            return polyglot_move

        fen_prefix = " ".join(board.fen().split(" ")[:4])
        entries = self._book.get(fen_prefix, [])
        if not entries:
            return None

        legal_moves = set(board.legal_moves)
        weighted_moves: list[chess.Move] = []
        weights: list[int] = []

        for entry in entries:
            try:
                move = chess.Move.from_uci(entry["move"])
            except ValueError:
                continue
            if move not in legal_moves:
                continue

            weighted_moves.append(move)
            weights.append(max(1, int(entry.get("weight", 1))))

        if not weighted_moves:
            return None

        return random.choices(weighted_moves, weights=weights, k=1)[0]

    def _polyglot_move(self, board: chess.Board) -> Optional[chess.Move]:
        """Return a move from a Polyglot .bin opening book, if configured."""
        if self._polyglot_reader is None:
            return None

        try:
            entries = list(
                self._polyglot_reader.find_all(
                    board,
                    minimum_weight=self._minimum_weight,
                )
            )
        except IndexError:
            return None

        legal = set(board.legal_moves)
        legal_entries = [entry for entry in entries if entry.move in legal]
        if not legal_entries:
            return None

        if self._use_weighted_book:
            weights = [max(1, int(entry.weight)) for entry in legal_entries]
            return random.choices(legal_entries, weights=weights, k=1)[0].move

        return random.choice(legal_entries).move

    # ------------------------------------------------------------------
    # TODO 3: Move selection
    # ------------------------------------------------------------------
    def get_move(self, board: chess.Board) -> chess.Move:
        """Return a book move if available, otherwise fall back to minimax.

        Args:
            board: Current board position.

        Returns:
            A legal chess.Move.
        """
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No legal moves — game should be over.")

        book_move = self._book_move(board) if self._in_book else None
        if book_move is not None:
            self._in_book = True
            return book_move

        self._in_book = False
        return self._fallback.get_move(board)


    def get_move_with_info(self, board: chess.Board) -> MoveInfo:
        book_move = self._book_move(board) if self._in_book else None

        if book_move is not None:
            source = "opening database"
            if self._polyglot_reader is not None:
                source = "polyglot opening book"
            return MoveInfo(
                move=book_move,
                score=None,
                depth=0,
                reasoning=f"Book move ({source}).",
            )

        # Out of book — delegate to fallback and annotate
        info = self._fallback.get_move_with_info(board)
        info.reasoning = f"[Out of book] {info.reasoning}"
        return info

    def evaluate(self, board: chess.Board) -> float:
        return self._fallback.evaluate(board)
