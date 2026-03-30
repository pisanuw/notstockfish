"""
Engine registry.

Engines are imported with try/except so that individual engine files can be
removed (e.g., for student distributions) without breaking the application.
The missing engine simply won't appear in the available engines list.
"""

from __future__ import annotations
from typing import Optional
from .base import ChessEngine

# Registry maps version id → engine class
ENGINES: dict[str, type[ChessEngine]] = {}

try:
    from .v0_random import RandomEngine
    ENGINES["v0"] = RandomEngine
except ImportError:
    pass

try:
    from .v1_search import GreedySearchEngine
    ENGINES["v1"] = GreedySearchEngine
except ImportError:
    pass

try:
    from .v2_minimax import MinimaxEngine
    ENGINES["v2"] = MinimaxEngine
except ImportError:
    pass

try:
    from .v3_qlearning import QLearningEngine
    ENGINES["v3"] = QLearningEngine
except ImportError:
    pass

try:
    from .v4_openings import OpeningBookEngine
    ENGINES["v4"] = OpeningBookEngine
except ImportError:
    pass


def get_engine(version_id: str, config: Optional[dict] = None) -> ChessEngine:
    """Instantiate and return the engine for a given version id.

    Args:
        version_id: e.g. "v0", "v1", ...

    Returns:
        A ChessEngine instance.

    Raises:
        KeyError: If version_id is not in the registry.
    """
    if version_id not in ENGINES:
        raise KeyError(
            f"Engine '{version_id}' is not available. "
            f"Available engines: {list(ENGINES.keys())}"
        )
    config = config or {}
    cls = ENGINES[version_id]

    if version_id == "v1":
        plies = int(config.get("plies", 1))
        plies = max(1, min(10, plies))
        return cls(plies=plies)

    if version_id == "v4":
        fallback_depth = int(config.get("fallback_depth", 3))
        fallback_depth = max(1, min(6, fallback_depth))
        book_path = config.get("book_path")
        minimum_weight = int(config.get("minimum_weight", 1))
        use_weighted_book = bool(config.get("use_weighted_book", True))
        return cls(
            fallback_depth=fallback_depth,
            book_path=book_path,
            minimum_weight=minimum_weight,
            use_weighted_book=use_weighted_book,
        )

    return cls()


def list_engines(check_implemented: bool = True) -> list[dict]:
    """Return metadata for all registered engines.

    Args:
        check_implemented: If True, include an 'implemented' flag that
            indicates whether the engine raises NotImplementedError on first
            use (useful for the comparison panel to skip unimplemented engines).
    """
    result = []
    for version_id, cls in ENGINES.items():
        instance = cls()
        meta = instance.metadata()
        if check_implemented:
            import chess
            try:
                instance.get_move(chess.Board())
                meta["implemented"] = True
            except NotImplementedError:
                meta["implemented"] = False
            except Exception:
                # Any other error means it ran but crashed — treat as implemented
                meta["implemented"] = True
        result.append(meta)
    return result
