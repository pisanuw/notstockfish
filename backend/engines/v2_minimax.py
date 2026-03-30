"""
v2 — Minimax with Alpha-Beta Pruning
======================================
Searches the game tree to a configurable depth using minimax, accelerated by
alpha-beta pruning to cut branches that cannot influence the result.

Evaluation combines:
  - Material count (same as v1)
  - Piece-square tables (positional bonuses)

Concepts covered
----------------
- Game tree search
- Minimax algorithm
- Alpha-beta pruning
- Piece-square positional tables

Student TODO
------------
TODO 1: Implement `_minimax(board, depth, alpha, beta, maximising)`.
    Base cases:
        - depth == 0 or game over → return self.evaluate(board)
    Maximising player (White):
        - Iterate legal moves, push each, recurse with maximising=False
        - Track the max value; update alpha; prune when alpha >= beta
    Minimising player (Black):
        - Similar but track min; update beta; prune when beta <= alpha
    Remember to pop() after each recursive call if using the same board
    (or use board.copy() and don't pop — choose one approach consistently).

TODO 2: Implement `get_move(board)`.
    Iterate all legal moves at the root, call _minimax on each, pick the
    best move for the side to move.
    Hint: for Black (minimising), you want the move with the LOWEST score
    (since evaluate() returns from White's perspective).
"""

import random
import chess

from .base import ChessEngine, MoveInfo

# -----------------------------------------------------------------------
# Piece values (centipawns)
# -----------------------------------------------------------------------
PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:   20000,
}

MG_PIECE_VALUES = {
    chess.PAWN: 82,
    chess.KNIGHT: 337,
    chess.BISHOP: 365,
    chess.ROOK: 477,
    chess.QUEEN: 1025,
    chess.KING: 0,
}

EG_PIECE_VALUES = {
    chess.PAWN: 94,
    chess.KNIGHT: 281,
    chess.BISHOP: 297,
    chess.ROOK: 512,
    chess.QUEEN: 936,
    chess.KING: 0,
}

PHASE_WEIGHTS = {
    chess.PAWN: 0,
    chess.KNIGHT: 1,
    chess.BISHOP: 1,
    chess.ROOK: 2,
    chess.QUEEN: 4,
    chess.KING: 0,
}

# -----------------------------------------------------------------------
# Piece-square tables (from White's perspective, a1=index 0 … h8=index 63)
# These give positional bonuses/penalties on top of material.
# -----------------------------------------------------------------------
PAWN_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
   50, 50, 50, 50, 50, 50, 50, 50,
   10, 10, 20, 30, 30, 20, 10, 10,
    5,  5, 10, 25, 25, 10,  5,  5,
    0,  0,  0, 20, 20,  0,  0,  0,
    5, -5,-10,  0,  0,-10, -5,  5,
    5, 10, 10,-20,-20, 10, 10,  5,
    0,  0,  0,  0,  0,  0,  0,  0,
]

KNIGHT_TABLE = [
   -50,-40,-30,-30,-30,-30,-40,-50,
   -40,-20,  0,  0,  0,  0,-20,-40,
   -30,  0, 10, 15, 15, 10,  0,-30,
   -30,  5, 15, 20, 20, 15,  5,-30,
   -30,  0, 15, 20, 20, 15,  0,-30,
   -30,  5, 10, 15, 15, 10,  5,-30,
   -40,-20,  0,  5,  5,  0,-20,-40,
   -50,-40,-30,-30,-30,-30,-40,-50,
]

BISHOP_TABLE = [
   -20,-10,-10,-10,-10,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5, 10, 10,  5,  0,-10,
   -10,  5,  5, 10, 10,  5,  5,-10,
   -10,  0, 10, 10, 10, 10,  0,-10,
   -10, 10, 10, 10, 10, 10, 10,-10,
   -10,  5,  0,  0,  0,  0,  5,-10,
   -20,-10,-10,-10,-10,-10,-10,-20,
]

ROOK_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
    5, 10, 10, 10, 10, 10, 10,  5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
   -5,  0,  0,  0,  0,  0,  0, -5,
    0,  0,  0,  5,  5,  0,  0,  0,
]

QUEEN_TABLE = [
   -20,-10,-10, -5, -5,-10,-10,-20,
   -10,  0,  0,  0,  0,  0,  0,-10,
   -10,  0,  5,  5,  5,  5,  0,-10,
    -5,  0,  5,  5,  5,  5,  0, -5,
     0,  0,  5,  5,  5,  5,  0, -5,
   -10,  5,  5,  5,  5,  5,  0,-10,
   -10,  0,  5,  0,  0,  0,  0,-10,
   -20,-10,-10, -5, -5,-10,-10,-20,
]

KING_MIDDLE_TABLE = [
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -30,-40,-40,-50,-50,-40,-40,-30,
   -20,-30,-30,-40,-40,-30,-30,-20,
   -10,-20,-20,-20,-20,-20,-20,-10,
    20, 20,  0,  0,  0,  0, 20, 20,
    20, 30, 10,  0,  0, 10, 30, 20,
]

KING_ENDGAME_TABLE = [
   -74, -35, -18, -18, -11,  15,   4, -17,
   -12,  17,  14,  17,  17,  38,  23,  11,
    10,  17,  23,  15,  20,  45,  44,  13,
    -8,  22,  24,  27,  26,  33,  26,   3,
   -18,  -4,  21,  24,  27,  23,   9, -11,
   -19,  -3,  11,  21,  23,  16,   7,  -9,
   -27, -11,   4,  13,  14,   4,  -5, -17,
   -53, -34, -21, -11, -28, -14, -24, -43,
]

PST: dict[int, list[int]] = {
    chess.PAWN:   PAWN_TABLE,
    chess.KNIGHT: KNIGHT_TABLE,
    chess.BISHOP: BISHOP_TABLE,
    chess.ROOK:   ROOK_TABLE,
    chess.QUEEN:  QUEEN_TABLE,
    chess.KING:   KING_MIDDLE_TABLE,
}


class MinimaxEngine(ChessEngine):
    name = "Minimax + Alpha-Beta"
    description = (
        "Searches the game tree to a configurable depth using minimax with "
        "alpha-beta pruning and piece-square positional tables."
    )
    version = "v2"

    def __init__(self, depth: int = 3):
        self.depth = depth
        self._nodes = 0
        self._transposition_table: dict[tuple[str, int, bool], float] = {}

    # ------------------------------------------------------------------
    # Evaluation helpers (complete — students may read these as reference)
    # ------------------------------------------------------------------
    def _pst_score(self, piece_type: int, square: int, color: chess.Color) -> int:
        """Return the piece-square table bonus for a piece.

        The tables are written from White's perspective (a1=0, h8=63 in
        python-chess notation, but the PST above is laid out rank 8 → rank 1).
        For Black pieces the table is mirrored vertically.
        """
        table = PST.get(piece_type, [0] * 64)
        # python-chess squares: a1=0 … h8=63 (rank-major, rank 0 first)
        # PST above: index 0 = a8, index 63 = h1 (rank 8 first for White)
        if color == chess.WHITE:
            # Mirror vertically: rank r → rank (7-r)
            mirrored = (7 - chess.square_rank(square)) * 8 + chess.square_file(square)
            return table[mirrored]
        else:
            # Black sees the board upside down
            idx = chess.square_rank(square) * 8 + chess.square_file(square)
            return table[idx]

    def _pst_score_endgame_king(self, square: int, color: chess.Color) -> int:
        """Endgame king placement bonus."""
        if color == chess.WHITE:
            mirrored = (7 - chess.square_rank(square)) * 8 + chess.square_file(square)
            return KING_ENDGAME_TABLE[mirrored]
        idx = chess.square_rank(square) * 8 + chess.square_file(square)
        return KING_ENDGAME_TABLE[idx]

    def _phase(self, board: chess.Board) -> int:
        """Return game phase in [0, 24], where 24 is opening/middlegame heavy."""
        phase = 0
        for piece in board.piece_map().values():
            phase += PHASE_WEIGHTS.get(piece.piece_type, 0)
        return min(24, phase)

    def _mobility_score(self, board: chess.Board) -> int:
        """Simple mobility differential in centipawns."""
        original_turn = board.turn
        board.turn = chess.WHITE
        white_mobility = len(list(board.legal_moves))
        board.turn = chess.BLACK
        black_mobility = len(list(board.legal_moves))
        board.turn = original_turn
        return 3 * (white_mobility - black_mobility)

    def _pawn_structure_score(self, board: chess.Board) -> int:
        """Penalty for doubled/isolated pawns and bonus for passed pawns."""
        score = 0
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)

        def file_counts(pawns: chess.SquareSet) -> list[int]:
            counts = [0] * 8
            for sq in pawns:
                counts[chess.square_file(sq)] += 1
            return counts

        white_files = file_counts(white_pawns)
        black_files = file_counts(black_pawns)

        for f in range(8):
            if white_files[f] > 1:
                score -= 12 * (white_files[f] - 1)
            if black_files[f] > 1:
                score += 12 * (black_files[f] - 1)

        for sq in white_pawns:
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            left_has = f > 0 and white_files[f - 1] > 0
            right_has = f < 7 and white_files[f + 1] > 0
            if not left_has and not right_has:
                score -= 8

            is_passed = True
            for opp_sq in black_pawns:
                opp_f = chess.square_file(opp_sq)
                opp_r = chess.square_rank(opp_sq)
                if abs(opp_f - f) <= 1 and opp_r > r:
                    is_passed = False
                    break
            if is_passed:
                score += 14 + 2 * r

        for sq in black_pawns:
            f = chess.square_file(sq)
            r = chess.square_rank(sq)
            left_has = f > 0 and black_files[f - 1] > 0
            right_has = f < 7 and black_files[f + 1] > 0
            if not left_has and not right_has:
                score += 8

            is_passed = True
            for opp_sq in white_pawns:
                opp_f = chess.square_file(opp_sq)
                opp_r = chess.square_rank(opp_sq)
                if abs(opp_f - f) <= 1 and opp_r < r:
                    is_passed = False
                    break
            if is_passed:
                score -= 14 + 2 * (7 - r)

        return score

    def _bishop_pair_score(self, board: chess.Board) -> int:
        score = 0
        if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
            score += 30
        if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
            score -= 30
        return score

    def _rook_file_score(self, board: chess.Board) -> int:
        score = 0
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)

        for sq in board.pieces(chess.ROOK, chess.WHITE):
            f = chess.square_file(sq)
            own_on_file = any(chess.square_file(p) == f for p in white_pawns)
            opp_on_file = any(chess.square_file(p) == f for p in black_pawns)
            if not own_on_file:
                score += 10
            if not own_on_file and not opp_on_file:
                score += 8

        for sq in board.pieces(chess.ROOK, chess.BLACK):
            f = chess.square_file(sq)
            own_on_file = any(chess.square_file(p) == f for p in black_pawns)
            opp_on_file = any(chess.square_file(p) == f for p in white_pawns)
            if not own_on_file:
                score -= 10
            if not own_on_file and not opp_on_file:
                score -= 8

        return score

    def _king_safety_score(self, board: chess.Board, mg_phase: int) -> int:
        """Opening-heavy king shield term. Fades toward endgame."""
        if mg_phase <= 0:
            return 0

        def king_shield_penalty(color: chess.Color) -> int:
            king_square = board.king(color)
            if king_square is None:
                return 0

            rank = chess.square_rank(king_square)
            file = chess.square_file(king_square)
            step = 1 if color == chess.WHITE else -1
            target_rank = rank + step
            if target_rank < 0 or target_rank > 7:
                return 0

            missing = 0
            for df in (-1, 0, 1):
                tf = file + df
                if tf < 0 or tf > 7:
                    continue
                sq = chess.square(tf, target_rank)
                piece = board.piece_at(sq)
                if piece is None or piece.piece_type != chess.PAWN or piece.color != color:
                    missing += 1
            return missing * 12

        white_penalty = king_shield_penalty(chess.WHITE)
        black_penalty = king_shield_penalty(chess.BLACK)
        base = black_penalty - white_penalty
        return (base * mg_phase) // 24

    def _move_order_key(self, board: chess.Board, move: chess.Move) -> int:
        """Order tactical and forcing moves first for stronger alpha-beta pruning."""
        score = 0

        if board.is_capture(move):
            captured_piece = board.piece_at(move.to_square)
            if captured_piece is None and board.is_en_passant(move):
                captured_piece = chess.Piece(chess.PAWN, not board.turn)
            attacker = board.piece_at(move.from_square)
            if captured_piece is not None:
                score += PIECE_VALUES.get(captured_piece.piece_type, 0) * 10
            if attacker is not None:
                score -= PIECE_VALUES.get(attacker.piece_type, 0)

        if move.promotion:
            score += 800 + PIECE_VALUES.get(move.promotion, 0)

        if board.gives_check(move):
            score += 50

        to_file = chess.square_file(move.to_square)
        to_rank = chess.square_rank(move.to_square)
        if 2 <= to_file <= 5 and 2 <= to_rank <= 5:
            score += 6

        return score

    def _ordered_moves(self, board: chess.Board, forcing_only: bool = False) -> list[chess.Move]:
        legal_moves = list(board.legal_moves)
        if forcing_only:
            legal_moves = [
                move
                for move in legal_moves
                if board.is_capture(move) or move.promotion or board.gives_check(move)
            ]
        return sorted(
            legal_moves,
            key=lambda move: self._move_order_key(board, move),
            reverse=True,
        )

    def _tt_key(self, board: chess.Board, depth: int, maximising: bool) -> tuple[str, int, bool]:
        fen_prefix = " ".join(board.fen().split(" ")[:4])
        return (fen_prefix, depth, maximising)

    def _quiescence(
        self,
        board: chess.Board,
        alpha: float,
        beta: float,
        maximising: bool,
    ) -> float:
        self._nodes += 1
        stand_pat = self.evaluate(board)

        if maximising:
            if stand_pat >= beta:
                return beta
            alpha = max(alpha, stand_pat)
        else:
            if stand_pat <= alpha:
                return alpha
            beta = min(beta, stand_pat)

        for move in self._ordered_moves(board, forcing_only=True):
            board.push(move)
            score = self._quiescence(board, alpha, beta, not maximising)
            board.pop()

            if maximising:
                alpha = max(alpha, score)
                if alpha >= beta:
                    break
            else:
                beta = min(beta, score)
                if beta <= alpha:
                    break

        return alpha if maximising else beta

    def evaluate(self, board: chess.Board) -> float:
        """Static evaluation from White's perspective (in centipawns)."""
        if board.is_checkmate():
            # The side that just moved delivered checkmate
            return -20000 if board.turn == chess.WHITE else 20000
        if board.is_stalemate() or board.is_insufficient_material():
            return 0.0

        mg_score = 0
        eg_score = 0
        for square, piece in board.piece_map().items():
            mg_value = MG_PIECE_VALUES.get(piece.piece_type, 0)
            eg_value = EG_PIECE_VALUES.get(piece.piece_type, 0)

            mg_pst = self._pst_score(piece.piece_type, square, piece.color)
            eg_pst = (
                self._pst_score_endgame_king(square, piece.color)
                if piece.piece_type == chess.KING
                else mg_pst
            )

            if piece.color == chess.WHITE:
                mg_score += mg_value + mg_pst
                eg_score += eg_value + eg_pst
            else:
                mg_score -= mg_value + mg_pst
                eg_score -= eg_value + eg_pst

        mg_phase = self._phase(board)
        eg_phase = 24 - mg_phase
        tapered = (mg_score * mg_phase + eg_score * eg_phase) / 24.0

        tapered += self._mobility_score(board)
        tapered += self._pawn_structure_score(board)
        tapered += self._bishop_pair_score(board)
        tapered += self._rook_file_score(board)
        tapered += self._king_safety_score(board, mg_phase)

        tempo = 8 if board.turn == chess.WHITE else -8
        tapered += tempo

        return float(tapered)

    # ------------------------------------------------------------------
    # TODO 1: Implement the minimax search with alpha-beta pruning
    # ------------------------------------------------------------------
    def _minimax(
        self,
        board: chess.Board,
        depth: int,
        alpha: float,
        beta: float,
        maximising: bool,
    ) -> float:
        """Minimax search with alpha-beta pruning.

        Args:
            board: Current board state.
            depth: Remaining search depth (0 = leaf node).
            alpha: Best score the maximising player can guarantee.
            beta:  Best score the minimising player can guarantee.
            maximising: True if the current node is a max node (White to move).

        Returns:
            The minimax value of the position (from White's perspective).

        Notes:
            - At depth 0 (or terminal node), return self.evaluate(board).
            - Maximising: iterate moves, recurse with maximising=False,
              update alpha, prune when alpha >= beta (return beta).
            - Minimising: iterate moves, recurse with maximising=True,
              update beta, prune when beta <= alpha (return alpha).
            - Use board.push(move) / board.pop() to avoid copying.
        """
        if depth == 0 or board.is_game_over():
            return self._quiescence(board, alpha, beta, maximising)

        self._nodes += 1
        tt_key = self._tt_key(board, depth, maximising)
        cached = self._transposition_table.get(tt_key)
        if cached is not None:
            return cached

        legal = self._ordered_moves(board)
        if maximising:
            value = float("-inf")
            for move in legal:
                board.push(move)
                value = max(value, self._minimax(board, depth - 1, alpha, beta, False))
                board.pop()
                alpha = max(alpha, value)
                if alpha >= beta:
                    break
            self._transposition_table[tt_key] = value
            return value

        value = float("inf")
        for move in legal:
            board.push(move)
            value = min(value, self._minimax(board, depth - 1, alpha, beta, True))
            board.pop()
            beta = min(beta, value)
            if beta <= alpha:
                break
        self._transposition_table[tt_key] = value
        return value

    def _search_root(self, board: chess.Board, depth: int) -> tuple[list[chess.Move], float]:
        legal = self._ordered_moves(board)
        if not legal:
            raise ValueError("No legal moves — game should be over.")

        is_white = board.turn == chess.WHITE
        best_score = float("-inf") if is_white else float("inf")
        best_moves: list[chess.Move] = []

        for move in legal:
            board.push(move)
            score = self._minimax(
                board,
                depth - 1,
                float("-inf"),
                float("inf"),
                not is_white,
            )
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

        return best_moves, best_score

    # ------------------------------------------------------------------
    # TODO 2: Implement root move selection
    # ------------------------------------------------------------------
    def get_move(self, board: chess.Board) -> chess.Move:
        """Return the best move found by minimax at self.depth.

        Args:
            board: Current board position.

        Returns:
            The best legal move according to minimax.

        Hints:
            - Iterate legal moves, push each, call _minimax with depth-1.
            - White maximises; Black minimises (evaluate() is from White's POV).
            - Break ties randomly.
        """
        self._nodes = 0
        self._transposition_table.clear()
        best_moves: list[chess.Move] = []
        for current_depth in range(1, self.depth + 1):
            best_moves, _ = self._search_root(board, current_depth)
        return random.choice(best_moves)

    def get_move_with_info(self, board: chess.Board) -> MoveInfo:
        self._nodes = 0
        self._transposition_table.clear()
        best_moves: list[chess.Move] = []
        best_score = 0.0
        for current_depth in range(1, self.depth + 1):
            best_moves, best_score = self._search_root(board, current_depth)

        chosen = random.choice(best_moves)
        return MoveInfo(
            move=chosen,
            score=best_score / 100,  # convert centipawns → pawns
            depth=self.depth,
            nodes_searched=self._nodes,
            reasoning=(
                f"Iterative deepening to depth {self.depth} with quiescence search, "
                f"score {best_score/100:+.2f} pawns, {self._nodes} nodes searched, "
                f"TT entries {len(self._transposition_table)}."
            ),
        )
