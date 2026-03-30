"""
Game session management.

A GameSession holds the board state for one active game, the current engine,
and the move history.  Sessions are stored in-memory (no database).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional

import chess
import chess.pgn

from engines import get_engine, ENGINES
from engines.base import ChessEngine


@dataclass
class GameSession:
    """Represents one active game between a human and an engine."""

    game_id: str
    board: chess.Board
    engine: ChessEngine
    player_color: chess.Color   # chess.WHITE or chess.BLACK
    move_history: list[str] = field(default_factory=list)  # UCI strings

    def state_dict(self) -> dict:
        """Serialise the current game state for API responses."""
        legal_moves = [m.uci() for m in self.board.legal_moves]
        return {
            "game_id": self.game_id,
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "player_color": "white" if self.player_color == chess.WHITE else "black",
            "legal_moves": legal_moves,
            "move_history": self.move_history,
            "status": self._status(),
            "engine_id": self.engine.version,
            "engine_name": self.engine.name,
        }

    def _status(self) -> str:
        if self.board.is_checkmate():
            winner = "black" if self.board.turn == chess.WHITE else "white"
            return f"checkmate:{winner}"
        if self.board.is_stalemate():
            return "draw:stalemate"
        if self.board.is_insufficient_material():
            return "draw:insufficient_material"
        if self.board.is_seventyfive_moves():
            return "draw:75_moves"
        if self.board.is_fivefold_repetition():
            return "draw:fivefold_repetition"
        if self.board.is_check():
            return "check"
        return "ongoing"

    def is_game_over(self) -> bool:
        return self.board.is_game_over()


# ---------------------------------------------------------------------------
# Session store — simple in-memory dict
# ---------------------------------------------------------------------------
_sessions: dict[str, GameSession] = {}


def create_session(
    engine_id: str,
    player_color: str,
    engine_options: Optional[dict] = None,
) -> GameSession:
    """Create a new game session.

    Args:
        engine_id: e.g. "v0", "v1", ...
        player_color: "white" or "black"

    Returns:
        A new GameSession.

    Raises:
        KeyError: If engine_id is not registered.
        ValueError: If player_color is invalid.
    """
    if player_color not in ("white", "black"):
        raise ValueError(f"player_color must be 'white' or 'black', got {player_color!r}")

    engine = get_engine(engine_id, config=engine_options)
    color = chess.WHITE if player_color == "white" else chess.BLACK
    game_id = str(uuid.uuid4())
    session = GameSession(
        game_id=game_id,
        board=chess.Board(),
        engine=engine,
        player_color=color,
    )
    _sessions[game_id] = session

    # If the player chose Black, the engine (White) moves first
    if color == chess.BLACK:
        _engine_move(session)

    return session


def get_session(game_id: str) -> GameSession:
    """Retrieve an existing session.

    Raises:
        KeyError: If game_id is not found.
    """
    if game_id not in _sessions:
        raise KeyError(f"Game session '{game_id}' not found.")
    return _sessions[game_id]


def apply_player_move(
    session: GameSession, from_sq: str, to_sq: str, promotion: Optional[str] = None
) -> dict:
    """Validate and apply a human move, then let the engine reply.

    Args:
        session: The active game session.
        from_sq: Origin square in algebraic notation (e.g. "e2").
        to_sq: Destination square in algebraic notation (e.g. "e4").
        promotion: Optional promotion piece type ("q", "r", "b", "n").

    Returns:
        Updated state_dict after both moves.

    Raises:
        ValueError: If the move is illegal or it's not the player's turn.
    """
    board = session.board

    if board.turn != session.player_color:
        raise ValueError("It is not your turn.")

    # Build the move
    promo = None
    if promotion:
        promo = chess.Piece.from_symbol(promotion.upper()).piece_type
    uci = from_sq + to_sq + (promotion or "")
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise ValueError(f"Invalid move format: {uci!r}")

    if move not in board.legal_moves:
        raise ValueError(f"Illegal move: {uci}")

    board.push(move)
    session.move_history.append(uci)

    # Engine replies unless game is over or it's still the player's turn
    engine_info = None
    if not session.is_game_over() and board.turn != session.player_color:
        engine_info = _engine_move(session)

    state = session.state_dict()
    if engine_info is not None:
        state["engine_move"] = engine_info
    return state


def switch_engine(
    session: GameSession,
    engine_id: str,
    engine_options: Optional[dict] = None,
) -> dict:
    """Replace the engine for an ongoing game without resetting the board.

    Returns:
        Updated state_dict.
    """
    session.engine = get_engine(engine_id, config=engine_options)
    return session.state_dict()


def compare_engines(session: GameSession) -> list[dict]:
    """Ask every implemented engine for its recommended move on the current position.

    Returns:
        List of dicts: [{engine_id, name, move, score, reasoning, implemented}, ...]
    """
    results = []
    board = session.board.copy()

    for engine_id, cls in ENGINES.items():
        engine = cls()
        try:
            info = engine.get_move_with_info(board)
            results.append({
                "engine_id": engine_id,
                "name": engine.name,
                "implemented": True,
                **info.to_dict(),
            })
        except NotImplementedError:
            results.append({
                "engine_id": engine_id,
                "name": engine.name,
                "implemented": False,
                "move": None,
                "score": None,
                "reasoning": "Not yet implemented.",
            })
        except Exception as exc:
            results.append({
                "engine_id": engine_id,
                "name": engine.name,
                "implemented": True,
                "move": None,
                "score": None,
                "reasoning": f"Error: {exc}",
            })

    return results


def _engine_move(session: GameSession) -> dict:
    """Let the engine make its move.  Returns the MoveInfo dict."""
    info = session.engine.get_move_with_info(session.board)
    session.board.push(info.move)
    session.move_history.append(info.move.uci())
    return info.to_dict()
