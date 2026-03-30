"""
v1 — Greedy 1-ply Search Engine
=================================
Evaluates every legal move using a simple material count, then picks the move
that leads to the best immediate position (one ply look-ahead).

Concepts covered
----------------
- Static board evaluation
- Exhaustive 1-ply search (no tree, no recursion)
- Piece values

Student TODO
------------
TODO 1: Implement the `_piece_value` helper.
    Use standard material values:
        Pawn=1, Knight=3, Bishop=3, Rook=5, Queen=9, King=0 (not capturable)

TODO 2: Implement `evaluate(board)`.
    Count the total material for White minus total material for Black.
    Use `board.piece_map()` to iterate over all pieces.
    Return a float where positive = good for White, negative = good for Black.

TODO 3: Implement `get_move(board)`.
    For each legal move:
        1. Push the move onto a copy of the board (use board.copy()).
        2. Evaluate the resulting position.
        3. Adjust the sign so you are always maximising from the perspective
           of the side to move (hint: if board.turn == chess.BLACK, negate).
    Return the move with the highest adjusted score. Break ties randomly.
"""

import random
import chess

from .base import ChessEngine, MoveInfo

# Standard piece values (centipawns if you prefer, but here we use pawns)
PIECE_VALUES = {
    chess.PAWN:   1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK:   5,
    chess.QUEEN:  9,
    chess.KING:   0,
}


class GreedySearchEngine(ChessEngine):
    name = "Greedy 1-ply Search"
    description = (
        "Evaluates all legal moves one ply deep using material count and "
        "picks the best immediate gain."
    )
    version = "v1"

    def __init__(self, plies: int = 1):
        self.plies = max(1, min(10, int(plies)))

    def _search(self, board: chess.Board, depth: int) -> float:
        """Depth-limited material-only minimax from White's perspective."""
        if depth <= 0 or board.is_game_over():
            return self.evaluate(board)

        legal = list(board.legal_moves)
        if not legal:
            return self.evaluate(board)

        if board.turn == chess.WHITE:
            best = float("-inf")
            for move in legal:
                board.push(move)
                best = max(best, self._search(board, depth - 1))
                board.pop()
            return best

        best = float("inf")
        for move in legal:
            board.push(move)
            best = min(best, self._search(board, depth - 1))
            board.pop()
        return best

    # ------------------------------------------------------------------
    # TODO 1: Implement piece value lookup
    # ------------------------------------------------------------------
    def _piece_value(self, piece_type: int) -> float:
        """Return the material value of a piece type.

        Args:
            piece_type: A chess.PAWN / chess.KNIGHT / … constant.

        Returns:
            Float value in pawns.
        """
        return float(PIECE_VALUES.get(piece_type, 0))

    # ------------------------------------------------------------------
    # TODO 2: Implement board evaluation
    # ------------------------------------------------------------------
    def evaluate(self, board: chess.Board) -> float:
        """Evaluate the board from White's perspective.

        Sum up the values of all White pieces and subtract the sum of all
        Black pieces.

        Args:
            board: The board to evaluate.

        Returns:
            Float where positive = good for White.
        """
        score = 0.0
        for _, piece in board.piece_map().items():
            value = self._piece_value(piece.piece_type)
            if piece.color == chess.WHITE:
                score += value
            else:
                score -= value
        return score

    # ------------------------------------------------------------------
    # TODO 3: Implement 1-ply greedy search
    # ------------------------------------------------------------------
    def get_move(self, board: chess.Board) -> chess.Move:
        """Return the move that maximises immediate material gain.

        Args:
            board: Current board position (do NOT mutate permanently).

        Returns:
            The best legal move according to 1-ply material evaluation.
        """
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No legal moves — game should be over.")

        is_white = board.turn == chess.WHITE
        best_score = float("-inf") if is_white else float("inf")
        best_moves: list[chess.Move] = []

        for move in legal:
            board.push(move)
            score = self._search(board, self.plies - 1)
            board.pop()

            if is_white:
                if score > best_score:
                    best_score = score
                    best_moves = [move]
                elif score == best_score:
                    best_moves.append(move)
            else:
                if score < best_score:
                    best_score = score
                    best_moves = [move]
                elif score == best_score:
                    best_moves.append(move)

        return random.choice(best_moves)

    def get_move_with_info(self, board: chess.Board) -> MoveInfo:
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No legal moves — game should be over.")

        is_white = board.turn == chess.WHITE
        best_score = float("-inf") if is_white else float("inf")
        best_moves = []

        for move in legal:
            board.push(move)
            score = self._search(board, self.plies - 1)
            board.pop()
            if is_white:
                if score > best_score:
                    best_score = score
                    best_moves = [move]
                elif score == best_score:
                    best_moves.append(move)
            else:
                if score < best_score:
                    best_score = score
                    best_moves = [move]
                elif score == best_score:
                    best_moves.append(move)

        chosen = random.choice(best_moves)
        return MoveInfo(
            move=chosen,
            score=best_score,
            depth=self.plies,
            reasoning=f"Best material score at depth {self.plies}: {best_score:+.1f}",
        )

    def metadata(self) -> dict:
        meta = super().metadata()
        meta["max_plies"] = 10
        meta["default_plies"] = 1
        return meta
