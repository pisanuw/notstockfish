"""In-memory player-vs-player room management."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from typing import Optional

import chess


def _status_for_board(board: chess.Board) -> str:
    if board.is_checkmate():
        winner = "black" if board.turn == chess.WHITE else "white"
        return f"checkmate:{winner}"
    if board.is_stalemate():
        return "draw:stalemate"
    if board.is_insufficient_material():
        return "draw:insufficient_material"
    if board.is_seventyfive_moves():
        return "draw:75_moves"
    if board.is_fivefold_repetition():
        return "draw:fivefold_repetition"
    if board.is_check():
        return "check"
    return "ongoing"


@dataclass
class PvPGameSession:
    game_id: str
    join_code: str
    board: chess.Board
    white_name: Optional[str] = None
    black_name: Optional[str] = None
    white_token: Optional[str] = None
    black_token: Optional[str] = None
    move_history: list[str] = field(default_factory=list)

    def player_color_for_token(self, player_token: Optional[str]) -> Optional[str]:
        if player_token and player_token == self.white_token:
            return "white"
        if player_token and player_token == self.black_token:
            return "black"
        return None

    def is_full(self) -> bool:
        return bool(self.white_token and self.black_token)

    def state_dict(self, player_token: Optional[str] = None) -> dict:
        your_color = self.player_color_for_token(player_token)
        legal_moves = [m.uci() for m in self.board.legal_moves]
        if not self.is_full() or your_color != ("white" if self.board.turn == chess.WHITE else "black"):
            legal_moves = []
        return {
            "game_id": self.game_id,
            "join_code": self.join_code,
            "mode": "pvp",
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn == chess.WHITE else "black",
            "player_color": your_color,
            "legal_moves": legal_moves,
            "move_history": self.move_history,
            "status": _status_for_board(self.board),
            "waiting_for_opponent": not self.is_full(),
            "players": {
                "white": self.white_name,
                "black": self.black_name,
            },
        }

    def is_game_over(self) -> bool:
        return self.board.is_game_over()


_games: dict[str, PvPGameSession] = {}
_join_index: dict[str, str] = {}


def _new_game_id() -> str:
    return secrets.token_hex(8)


def _new_join_code() -> str:
    while True:
        join_code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
        if join_code not in _join_index:
            return join_code


def _new_player_token() -> str:
    return secrets.token_urlsafe(24)


def _clean_name(name: str) -> str:
    value = name.strip()
    if not value:
        raise ValueError("Player name is required.")
    return value[:40]


def create_pvp_game(player_name: str, preferred_color: str = "white") -> tuple[PvPGameSession, str]:
    preferred = preferred_color.lower().strip()
    if preferred not in {"white", "black", "random"}:
        raise ValueError("preferred_color must be white, black, or random.")

    assigned_color = preferred
    if assigned_color == "random":
        assigned_color = "white" if secrets.randbelow(2) == 0 else "black"

    session = PvPGameSession(
        game_id=_new_game_id(),
        join_code=_new_join_code(),
        board=chess.Board(),
    )
    player_token = _new_player_token()
    name = _clean_name(player_name)

    if assigned_color == "white":
        session.white_name = name
        session.white_token = player_token
    else:
        session.black_name = name
        session.black_token = player_token

    _games[session.game_id] = session
    _join_index[session.join_code] = session.game_id
    return session, player_token


def join_pvp_game(join_code: str, player_name: str) -> tuple[PvPGameSession, str]:
    game_id = _join_index.get(join_code.strip().upper())
    if game_id is None:
        raise KeyError("Join code was not found.")
    session = _games[game_id]
    if session.is_full():
        raise ValueError("This room already has two players.")

    player_token = _new_player_token()
    name = _clean_name(player_name)
    if session.white_token is None:
        session.white_token = player_token
        session.white_name = name
    else:
        session.black_token = player_token
        session.black_name = name
    return session, player_token


def get_pvp_game(game_id: str) -> PvPGameSession:
    if game_id not in _games:
        raise KeyError(f"PvP game '{game_id}' not found.")
    return _games[game_id]


def apply_pvp_move(
    session: PvPGameSession,
    player_token: str,
    from_sq: str,
    to_sq: str,
    promotion: Optional[str] = None,
) -> dict:
    if not session.is_full():
        raise ValueError("Waiting for an opponent to join.")
    if session.is_game_over():
        raise ValueError("Game is already over.")

    player_color = session.player_color_for_token(player_token)
    if player_color is None:
        raise ValueError("Player token is invalid.")

    turn_color = "white" if session.board.turn == chess.WHITE else "black"
    if player_color != turn_color:
        raise ValueError("It is not your turn.")

    uci = from_sq + to_sq + (promotion or "")
    try:
        move = chess.Move.from_uci(uci)
    except ValueError as exc:
        raise ValueError(f"Invalid move format: {uci!r}") from exc

    if move not in session.board.legal_moves:
        raise ValueError(f"Illegal move: {uci}")

    session.board.push(move)
    session.move_history.append(uci)
    return session.state_dict(player_token)