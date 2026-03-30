"""
v3 — Q-Learning Engine
========================
Uses a Q-table (state → action values) trained by self-play.

State representation (simplified for tractability)
---------------------------------------------------
Rather than the full 64-square board, we use a feature vector:
  - Material balance (White total - Black total, clamped to [-30, 30])
  - Mobility ratio (White legal moves / max expected mobility)
  - King safety proxy (# squares attacked near own king)
  - Game phase (opening / middlegame / endgame) encoded as integer

This keeps the state space small enough for a Q-table used in teaching, while
still demonstrating the Q-learning concept.

Concepts covered
----------------
- Reinforcement learning, Q-learning
- State abstraction / feature engineering
- Exploration vs exploitation (ε-greedy policy)
- Offline pre-training vs live training

Student TODO
------------
TODO 1: Implement `_state_key(board)`.
    Extract features from the board and return a hashable tuple that
    uniquely-ish represents the board state for Q-learning purposes.

TODO 2: Implement `_reward(board, move, board_after)`.
    Define the reward signal. Suggestions:
      - +1 for checkmate, -1 for being checkmated
      - Fractional values for material gain/loss
      - 0 for other moves (sparse reward) or small positional delta

TODO 3: Implement `update(state, action_uci, reward, next_state, done)`.
    Standard Q-learning update:
      Q(s,a) ← Q(s,a) + α * [r + γ * max_a' Q(s',a') - Q(s,a)]
    Use self.alpha, self.gamma.  If done, the future term is 0.

TODO 4: Implement `get_move(board)`.
    ε-greedy policy:
      - With probability self.epsilon: pick a random legal move (explore)
      - Otherwise: pick the move with the highest Q-value for this state
    Fall back to random if no Q-value is known for this state.
"""

import json
import random
from pathlib import Path

import chess

from .base import ChessEngine, MoveInfo

# Path to pre-trained weights (may not exist on first run)
_DATA_DIR = Path(__file__).parent.parent / "data"
_WEIGHTS_FILE = _DATA_DIR / "qlearning_weights.json"
PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 0,
}


class QLearningEngine(ChessEngine):
    name = "Q-Learning"
    description = (
        "Uses a Q-table trained by self-play. Supports live training via the "
        "training panel. Falls back to random moves if untrained."
    )
    version = "v3"

    def __init__(
        self,
        epsilon: float = 0.1,
        alpha: float = 0.1,
        gamma: float = 0.95,
        load_weights: bool = True,
    ):
        self.epsilon = epsilon   # exploration rate
        self.alpha = alpha       # learning rate
        self.gamma = gamma       # discount factor
        # Q-table: {state_key: {action_uci: float}}
        self.q_table: dict[tuple, dict[str, float]] = {}
        self.training_episodes = 0

        if load_weights and _WEIGHTS_FILE.exists():
            self._load_weights()

    # ------------------------------------------------------------------
    # TODO 1: State abstraction
    # ------------------------------------------------------------------
    def _state_key(self, board: chess.Board) -> tuple:
        """Convert the board into a compact, hashable state tuple.

        This is one of the most important design choices in Q-learning for
        chess.  A good state should capture the essential features without
        making the state space too large.

        Suggested features (implement at least 3):
          - Material balance (total White value - total Black value)
          - Number of legal moves for the side to move (mobility)
          - Whether the side to move is in check
          - Game phase: opening (> 12 pieces), middlegame, endgame

        Returns:
            A hashable tuple of feature values.
        """
        material_balance = 0
        piece_count = len(board.piece_map())
        for piece in board.piece_map().values():
            value = PIECE_VALUES.get(piece.piece_type, 0)
            if piece.color == chess.WHITE:
                material_balance += value
            else:
                material_balance -= value

        mobility = min(len(list(board.legal_moves)), 63)
        mobility_bucket = mobility // 4

        if piece_count > 24:
            phase = 0
        elif piece_count > 12:
            phase = 1
        else:
            phase = 2

        return (
            int(board.turn),
            max(-30, min(30, material_balance)),
            mobility_bucket,
            int(board.is_check()),
            phase,
            int(board.has_kingside_castling_rights(chess.WHITE)),
            int(board.has_queenside_castling_rights(chess.WHITE)),
            int(board.has_kingside_castling_rights(chess.BLACK)),
            int(board.has_queenside_castling_rights(chess.BLACK)),
        )

    # ------------------------------------------------------------------
    # TODO 2: Reward function
    # ------------------------------------------------------------------
    def _reward(
        self,
        board_before: chess.Board,
        move: chess.Move,
        board_after: chess.Board,
    ) -> float:
        """Compute the reward for taking `move` from `board_before`.

        Args:
            board_before: Board state BEFORE the move (turn = side that moved).
            move: The move that was made.
            board_after: Board state AFTER the move.

        Returns:
            A float reward signal. Higher is better for the side that moved.

        Suggestions:
          - Terminal: +1 for checkmate win, -1 for checkmate loss, 0 for draw
          - Non-terminal: material delta (normalise to small values)
        """
        mover = board_before.turn

        if board_after.is_checkmate():
            return 1.0
        if (
            board_after.is_stalemate()
            or board_after.is_insufficient_material()
            or board_after.is_seventyfive_moves()
            or board_after.is_fivefold_repetition()
        ):
            return 0.0

        material_delta = 0.0
        if board_before.is_capture(move):
            captured_piece = board_before.piece_at(move.to_square)
            if captured_piece is None and board_before.is_en_passant(move):
                offset = -8 if mover == chess.WHITE else 8
                captured_piece = board_before.piece_at(move.to_square + offset)
            if captured_piece is not None:
                material_delta += PIECE_VALUES.get(captured_piece.piece_type, 0) / 10.0

        if board_after.is_check():
            material_delta += 0.1

        return material_delta

    # ------------------------------------------------------------------
    # TODO 3: Q-table update
    # ------------------------------------------------------------------
    def update(
        self,
        state: tuple,
        action_uci: str,
        reward: float,
        next_state: tuple,
        done: bool,
        next_legal_actions: list[str],
    ) -> None:
        """Apply one Q-learning update.

        Q(s,a) ← Q(s,a) + α * [r + γ * max_a' Q(s',a') - Q(s,a)]

        Args:
            state: Current state key (from _state_key).
            action_uci: UCI string of the action taken.
            reward: Observed reward.
            next_state: State key after the action.
            done: True if the game ended.
            next_legal_actions: UCI strings of legal moves in next_state.
        """
        state_actions = self.q_table.setdefault(state, {})
        current_q = state_actions.get(action_uci, 0.0)

        next_q = 0.0
        if not done and next_legal_actions:
            next_actions = self.q_table.get(next_state, {})
            next_q = max((next_actions.get(action, 0.0) for action in next_legal_actions), default=0.0)

        target = reward + (0.0 if done else self.gamma * next_q)
        state_actions[action_uci] = current_q + self.alpha * (target - current_q)

    # ------------------------------------------------------------------
    # TODO 4: Move selection (ε-greedy)
    # ------------------------------------------------------------------
    def get_move(self, board: chess.Board) -> chess.Move:
        """Select a move using an ε-greedy policy over the Q-table.

        Args:
            board: Current board position.

        Returns:
            A legal chess.Move.
        """
        legal = list(board.legal_moves)
        if not legal:
            raise ValueError("No legal moves — game should be over.")

        if random.random() < self.epsilon:
            return random.choice(legal)

        state = self._state_key(board)
        state_actions = self.q_table.get(state, {})
        if not state_actions:
            return random.choice(legal)

        best_score = float("-inf")
        best_moves: list[chess.Move] = []

        for move in legal:
            score = state_actions.get(move.uci(), 0.0)
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return random.choice(best_moves)

    # ------------------------------------------------------------------
    # Weight persistence
    # ------------------------------------------------------------------
    def _load_weights(self) -> None:
        """Load Q-table from the pre-trained weights file."""
        try:
            with open(_WEIGHTS_FILE) as f:
                data = json.load(f)
            # Keys serialised as JSON strings; convert back to tuples
            self.q_table = {
                tuple(json.loads(k)): v for k, v in data.get("q_table", {}).items()
            }
            self.training_episodes = data.get("episodes", 0)
        except (json.JSONDecodeError, OSError):
            self.q_table = {}

    def save_weights(self) -> None:
        """Persist the current Q-table to disk."""
        _DATA_DIR.mkdir(exist_ok=True)
        serialised = {
            json.dumps(list(k)): v for k, v in self.q_table.items()
        }
        with open(_WEIGHTS_FILE, "w") as f:
            json.dump({"q_table": serialised, "episodes": self.training_episodes}, f)

    def get_move_with_info(self, board: chess.Board) -> MoveInfo:
        legal = list(board.legal_moves)
        state = self._state_key(board)
        q_values = self.q_table.get(state, {})
        known = len(q_values)

        move = self.get_move(board)
        best_q = q_values.get(move.uci(), None)

        return MoveInfo(
            move=move,
            score=best_q,
            depth=0,
            nodes_searched=known,
            reasoning=(
                f"ε-greedy (ε={self.epsilon}), "
                f"Q-table entries for state: {known}, "
                f"trained for {self.training_episodes} episodes."
            ),
        )

    def metadata(self) -> dict:
        m = super().metadata()
        m["training_episodes"] = self.training_episodes
        m["q_table_states"] = len(self.q_table)
        return m
