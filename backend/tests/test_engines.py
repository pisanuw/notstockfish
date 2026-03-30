"""Tests for chess engine implementations."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import chess
import pytest

from engines.base import ChessEngine, MoveInfo
from engines.v0_random import RandomEngine
from engines.v2_minimax import MinimaxEngine
from engines import ENGINES, get_engine, list_engines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def assert_legal(move: chess.Move, board: chess.Board):
    assert move in board.legal_moves, f"Engine returned illegal move {move.uci()}"


# ---------------------------------------------------------------------------
# v0 — Random engine (always fully implemented)
# ---------------------------------------------------------------------------

class TestRandomEngine:
    def test_returns_legal_move(self):
        engine = RandomEngine()
        board = chess.Board()
        move = engine.get_move(board)
        assert_legal(move, board)

    def test_returns_legal_move_midgame(self):
        engine = RandomEngine()
        board = chess.Board("r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4")
        move = engine.get_move(board)
        assert_legal(move, board)

    def test_board_not_mutated(self):
        engine = RandomEngine()
        board = chess.Board()
        fen_before = board.fen()
        engine.get_move(board)
        assert board.fen() == fen_before, "get_move must not mutate the board"

    def test_raises_on_no_legal_moves(self):
        engine = RandomEngine()
        # Stalemate position: no legal moves
        board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
        with pytest.raises(ValueError):
            engine.get_move(board)

    def test_get_move_with_info_returns_moveinfo(self):
        engine = RandomEngine()
        board = chess.Board()
        info = engine.get_move_with_info(board)
        assert isinstance(info, MoveInfo)
        assert_legal(info.move, board)

    def test_metadata(self):
        engine = RandomEngine()
        meta = engine.metadata()
        assert meta["version"] == "v0"
        assert "name" in meta

    def test_plays_full_game_without_error(self):
        """Engine should be able to play both sides of a full game."""
        import random
        random.seed(42)
        engine = RandomEngine()
        board = chess.Board()
        moves = 0
        while not board.is_game_over() and moves < 200:
            move = engine.get_move(board)
            assert_legal(move, board)
            board.push(move)
            moves += 1


# ---------------------------------------------------------------------------
# Engine registry
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_v0_always_registered(self):
        assert "v0" in ENGINES

    def test_get_engine_returns_instance(self):
        engine = get_engine("v0")
        assert isinstance(engine, ChessEngine)

    def test_get_engine_unknown_raises(self):
        with pytest.raises(KeyError):
            get_engine("v99")

    def test_list_engines_contains_v0(self):
        engines = list_engines(check_implemented=False)
        ids = [e["id"] for e in engines]
        assert "v0" in ids

    def test_list_engines_implemented_flag(self):
        engines = list_engines(check_implemented=True)
        v0 = next(e for e in engines if e["id"] == "v0")
        assert v0["implemented"] is True

    def test_all_engines_have_required_metadata(self):
        for e in list_engines(check_implemented=False):
            assert "id" in e
            assert "name" in e
            assert "description" in e
            assert "version" in e


# ---------------------------------------------------------------------------
# v1–v4: parametrised tests for any implemented engine
# ---------------------------------------------------------------------------

def implemented_engine_ids():
    """Return ids of engines that are implemented (don't raise NotImplementedError)."""
    ids = []
    board = chess.Board()
    for eid, cls in ENGINES.items():
        try:
            cls().get_move(board)
            ids.append(eid)
        except NotImplementedError:
            pass
        except Exception:
            ids.append(eid)  # ran but crashed for another reason — include it
    return ids


@pytest.mark.parametrize("engine_id", implemented_engine_ids())
class TestImplementedEngines:
    def test_returns_legal_move(self, engine_id):
        engine = get_engine(engine_id)
        board = chess.Board()
        move = engine.get_move(board)
        assert_legal(move, board)

    def test_board_not_mutated(self, engine_id):
        engine = get_engine(engine_id)
        board = chess.Board()
        fen_before = board.fen()
        engine.get_move(board)
        assert board.fen() == fen_before

    def test_get_move_with_info(self, engine_id):
        engine = get_engine(engine_id)
        board = chess.Board()
        info = engine.get_move_with_info(board)
        assert isinstance(info, MoveInfo)
        assert_legal(info.move, board)

    def test_evaluate_returns_float(self, engine_id):
        engine = get_engine(engine_id)
        board = chess.Board()
        score = engine.evaluate(board)
        assert isinstance(score, (int, float))


class TestMinimaxEvaluationImprovements:
    def test_knight_centralization_scores_higher(self):
        engine = MinimaxEngine(depth=2)
        center = chess.Board("4k3/7p/8/3N4/8/8/P3K3/8 w - - 0 1")
        rim = chess.Board("4k3/7p/8/8/8/N7/P3K3/8 w - - 0 1")
        assert engine.evaluate(center) > engine.evaluate(rim)

    def test_bishop_pair_bonus_applies(self):
        engine = MinimaxEngine(depth=2)
        bishop_pair = chess.Board("4k3/8/8/8/8/8/3BB3/4K3 w - - 0 1")
        bishop_knight = chess.Board("4k3/8/8/8/8/8/3BN3/4K3 w - - 0 1")
        assert engine.evaluate(bishop_pair) > engine.evaluate(bishop_knight)

    def test_passed_pawn_bonus_applies(self):
        engine = MinimaxEngine(depth=2)
        passed = chess.Board("4k3/7p/8/3P4/8/8/P3K3/8 w - - 0 1")
        blocked = chess.Board("4k3/7p/2p5/3P4/8/8/P3K3/8 w - - 0 1")
        assert engine.evaluate(passed) > engine.evaluate(blocked)

    def test_endgame_king_activity_is_rewarded(self):
        engine = MinimaxEngine(depth=2)
        active_king = chess.Board("4k3/7p/8/8/4K3/8/P7/8 w - - 0 1")
        passive_king = chess.Board("4k3/7p/8/8/8/8/P7/K7 w - - 0 1")
        assert engine.evaluate(active_king) > engine.evaluate(passive_king)


class TestOpeningEngineConfiguration:
    def test_v4_accepts_fallback_depth_from_registry(self):
        engine = get_engine("v4", config={"fallback_depth": 5})
        assert engine._fallback.depth == 5

    def test_v4_missing_polyglot_path_falls_back_cleanly(self):
        engine = get_engine(
            "v4",
            config={
                "book_path": "/tmp/does-not-exist.bin",
                "fallback_depth": 2,
                "minimum_weight": 1,
                "use_weighted_book": True,
            },
        )
        board = chess.Board()
        move = engine.get_move(board)
        assert_legal(move, board)


class TestMinimaxSearchImprovements:
    def test_search_info_mentions_new_search_features(self):
        engine = MinimaxEngine(depth=3)
        info = engine.get_move_with_info(chess.Board())
        assert info.reasoning is not None
        assert "quiescence" in info.reasoning.lower()
        assert "tt entries" in info.reasoning.lower()
