"""
ChessEngine abstract base class.

Every engine version must subclass ChessEngine and implement `get_move()`.
The optional `get_move_with_info()` and `evaluate()` methods enrich the
comparison panel in the UI.

Student assignment hint
-----------------------
When implementing a new engine:
1. Subclass ChessEngine.
2. Set `name`, `description`, and `version` class attributes.
3. Implement `get_move(board)` — it MUST return a move that is legal on the
   given board.  Use `board.legal_moves` to enumerate possibilities.
4. Never mutate `board` permanently — use `board.copy()` or push/pop.
5. Optionally override `get_move_with_info` to expose scores / depth info to
   the comparison panel.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional
import chess


class MoveInfo:
    """Rich result returned by get_move_with_info()."""

    def __init__(
        self,
        move: chess.Move,
        score: Optional[float] = None,
        depth: Optional[int] = None,
        nodes_searched: Optional[int] = None,
        reasoning: Optional[str] = None,
    ):
        self.move = move
        self.score = score           # positive = good for the side to move
        self.depth = depth
        self.nodes_searched = nodes_searched
        self.reasoning = reasoning

    def to_dict(self) -> dict:
        return {
            "move": self.move.uci(),
            "score": self.score,
            "depth": self.depth,
            "nodes_searched": self.nodes_searched,
            "reasoning": self.reasoning,
        }


class ChessEngine(ABC):
    """Abstract base class for all chess engine versions."""

    # Subclasses must set these
    name: str = "Unnamed Engine"
    description: str = ""
    version: str = "vX"

    @abstractmethod
    def get_move(self, board: chess.Board) -> chess.Move:
        """Return a legal move for the current position.

        Args:
            board: The current board state (do NOT mutate permanently).

        Returns:
            A legal chess.Move.

        Raises:
            ValueError: If the board has no legal moves.
        """
        ...

    def get_move_with_info(self, board: chess.Board) -> MoveInfo:
        """Return a move along with optional diagnostic information.

        Base implementation just calls get_move() with no extra info.
        Override to expose scores, depth, reasoning, etc.
        """
        move = self.get_move(board)
        return MoveInfo(move=move)

    def evaluate(self, board: chess.Board) -> float:
        """Evaluate the current position from White's perspective.

        Positive values favour White, negative favour Black.
        Returns 0.0 by default (engines that have no evaluator).
        """
        return 0.0

    def metadata(self) -> dict:
        """Return engine metadata for the UI."""
        return {
            "id": self.version,
            "name": self.name,
            "description": self.description,
            "version": self.version,
        }
