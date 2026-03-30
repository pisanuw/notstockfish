"""
v0 — Random Engine
==================
Picks a uniformly random legal move. No evaluation, no search.
This is the simplest possible chess engine and serves as the baseline.

This engine is COMPLETE and should not be modified by students.
"""

import random
import chess

from .base import ChessEngine, MoveInfo


class RandomEngine(ChessEngine):
    name = "Random Mover"
    description = "Picks a uniformly random legal move. No strategy whatsoever."
    version = "v0"

    def get_move(self, board: chess.Board) -> chess.Move:
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No legal moves available — game should be over.")
        return random.choice(legal)

    def get_move_with_info(self, board: chess.Board) -> MoveInfo:
        move = self.get_move(board)
        return MoveInfo(
            move=move,
            score=None,
            depth=0,
            reasoning="Selected uniformly at random from all legal moves.",
        )
