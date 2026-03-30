"""
FastAPI application entry point.

Run with:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import (
    auth_config,
    get_user_for_token,
    login_with_google,
    logout,
    request_magic_link,
    verify_magic_link,
)
from engines import list_engines
from game import (
    apply_player_move,
    compare_engines,
    create_session,
    get_session,
    switch_engine,
)
from pvp import apply_pvp_move, create_pvp_game, get_pvp_game, join_pvp_game
from scripts.benchmark_engines import (
    DEFAULT_FENS,
    _implemented_engine_ids,
    benchmark_engine,
    create_benchmark_report,
    save_benchmark_report,
)
from scripts.build_openings_json import build_opening_book, write_polyglot_book


def _parse_env_line(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        # Keep real environment values higher priority than local files.
        os.environ.setdefault(key, value)


def _load_local_env() -> None:
    backend_dir = Path(__file__).resolve().parent
    project_root = backend_dir.parent
    _load_env_file(project_root / ".env")
    _load_env_file(backend_dir / ".env")


_load_local_env()

app = FastAPI(title="stockreptile Chess API", version="1.0.0")

DATA_DIR = Path(__file__).parent / "data"
BENCHMARK_DIR = DATA_DIR / "benchmarks"
BENCHMARK_LATEST = BENCHMARK_DIR / "latest.json"
BENCHMARK_HISTORY = BENCHMARK_DIR / "history.jsonl"
OPENING_JSON_PATH = DATA_DIR / "openings.json"
OPENING_BIN_PATH = DATA_DIR / "openings.bin"
OPENING_GENERATED_JSON_PATH = DATA_DIR / "openings.generated.json"
OPENING_GENERATED_BIN_PATH = DATA_DIR / "openings.generated.bin"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://stockreptile.netlify.app",
    ],
    allow_origin_regex=(
        r"https?://(localhost|127\.0\.0\.1|\[::1\]|0\.0\.0\.0|"
        r"10(?:\.\d{1,3}){3}|"
        r"192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[0-1])(?:\.\d{1,3}){2})(?::\d+)?$"
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class NewGameRequest(BaseModel):
    engine_id: str = "v0"
    player_color: str = "white"   # "white" | "black"
    engine_options: Optional[dict] = None


class MoveRequest(BaseModel):
    from_sq: str                  # e.g. "e2"
    to_sq: str                    # e.g. "e4"
    promotion: Optional[str] = None  # "q" | "r" | "b" | "n"


class SwitchEngineRequest(BaseModel):
    engine_id: str
    engine_options: Optional[dict] = None


class MagicLinkRequest(BaseModel):
    email: str
    display_name: Optional[str] = None


class MagicLinkVerifyRequest(BaseModel):
    token: str


class GoogleLoginRequest(BaseModel):
    id_token: str


class LogoutRequest(BaseModel):
    access_token: Optional[str] = None


class PvPCreateRequest(BaseModel):
    player_name: str
    preferred_color: str = "white"


class PvPJoinRequest(BaseModel):
    join_code: str
    player_name: str


class PvPMoveRequest(BaseModel):
    player_token: str
    from_sq: str
    to_sq: str
    promotion: Optional[str] = None


class BenchmarkRunRequest(BaseModel):
    engine_ids: Optional[list[str]] = None
    persist: bool = True


class OpeningBuildRequest(BaseModel):
    pgn_text: str
    max_games: Optional[int] = None
    max_plies: int = 16
    min_elo: Optional[int] = None
    activate: bool = False


def _extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return None
    return value.strip()


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    """Simple health check for frontend connectivity status."""
    return {"status": "ok"}


@app.get("/api/auth/config")
def get_auth_config() -> dict:
    return auth_config()


@app.post("/api/auth/magic-link/request")
def begin_magic_link_login(req: MagicLinkRequest, request: Request) -> dict:
    try:
        return request_magic_link(
            email=req.email,
            display_name=req.display_name,
            app_base_url=str(request.base_url).rstrip("/"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/magic-link/verify")
def complete_magic_link_login(req: MagicLinkVerifyRequest) -> dict:
    try:
        return verify_magic_link(req.token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/google")
def google_login(req: GoogleLoginRequest) -> dict:
    try:
        return login_with_google(req.id_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    user = get_user_for_token(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication is required.")
    return {"user": user.to_dict()}


@app.post("/api/auth/logout")
def auth_logout(req: LogoutRequest, authorization: Optional[str] = Header(default=None)) -> dict:
    token = req.access_token or _extract_bearer_token(authorization)
    logout(token)
    return {"ok": True}

@app.get("/api/engines")
def get_engines() -> list[dict]:
    """List all available (registered) engines with metadata."""
    return list_engines(check_implemented=True)


# ---------------------------------------------------------------------------
# Game lifecycle
# ---------------------------------------------------------------------------

@app.post("/api/game/new")
def new_game(req: NewGameRequest) -> dict:
    """Start a new game.

    Returns the initial game state.  If the player chose Black, the engine
    (White) has already made its first move.
    """
    try:
        session = create_session(req.engine_id, req.player_color, req.engine_options)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return session.state_dict()


@app.get("/api/game/{game_id}/state")
def game_state(game_id: str) -> dict:
    """Return the current state of a game."""
    try:
        session = get_session(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return session.state_dict()


@app.post("/api/game/{game_id}/move")
def make_move(game_id: str, req: MoveRequest) -> dict:
    """Submit a human move.

    The engine will automatically reply unless the game is over.
    Returns the updated state, including the engine's move info under
    `engine_move` if one was made.
    """
    try:
        session = get_session(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    if session.is_game_over():
        raise HTTPException(status_code=400, detail="Game is already over.")

    try:
        state = apply_player_move(session, req.from_sq, req.to_sq, req.promotion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return state


@app.patch("/api/game/{game_id}/engine")
def change_engine(game_id: str, req: SwitchEngineRequest) -> dict:
    """Switch the active engine mid-game without resetting the board."""
    try:
        session = get_session(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        state = switch_engine(session, req.engine_id, req.engine_options)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return state


@app.post("/api/game/{game_id}/compare")
def compare(game_id: str) -> list[dict]:
    """Ask every registered engine for its recommended move on the current position.

    Engines that have not been implemented (raise NotImplementedError) are
    included in the response with `implemented: false`.
    """
    try:
        session = get_session(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return compare_engines(session)


@app.post("/api/pvp/create")
def pvp_create(req: PvPCreateRequest, authorization: Optional[str] = Header(default=None)) -> dict:
    try:
        user = get_user_for_token(_extract_bearer_token(authorization))
        session, player_token = create_pvp_game(
            player_name=user.display_name if user else req.player_name,
            preferred_color=req.preferred_color,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "player_token": player_token,
        "state": session.state_dict(player_token),
    }


@app.post("/api/pvp/join")
def pvp_join(req: PvPJoinRequest, authorization: Optional[str] = Header(default=None)) -> dict:
    try:
        user = get_user_for_token(_extract_bearer_token(authorization))
        session, player_token = join_pvp_game(
            join_code=req.join_code,
            player_name=user.display_name if user else req.player_name,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "player_token": player_token,
        "state": session.state_dict(player_token),
    }


@app.get("/api/pvp/{game_id}/state")
def pvp_state(game_id: str, player_token: Optional[str] = None) -> dict:
    try:
        session = get_pvp_game(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return session.state_dict(player_token)


@app.post("/api/pvp/{game_id}/move")
def pvp_move(game_id: str, req: PvPMoveRequest) -> dict:
    try:
        session = get_pvp_game(game_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        return apply_pvp_move(session, req.player_token, req.from_sq, req.to_sq, req.promotion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/tooling/benchmarks/run")
def run_benchmarks(req: BenchmarkRunRequest) -> dict:
    engine_ids = req.engine_ids or _implemented_engine_ids()
    if not engine_ids:
        raise HTTPException(status_code=400, detail="No implemented engines available for benchmarking.")

    results = [benchmark_engine(engine_id, DEFAULT_FENS) for engine_id in engine_ids]
    report = create_benchmark_report(results, engine_ids)

    if req.persist:
        save_benchmark_report(report, BENCHMARK_LATEST, BENCHMARK_HISTORY)

    return report


@app.get("/api/tooling/benchmarks/latest")
def get_latest_benchmark() -> dict:
    if not BENCHMARK_LATEST.exists():
        return {"report": None}
    return {"report": json.loads(BENCHMARK_LATEST.read_text(encoding="utf-8"))}


@app.get("/api/tooling/benchmarks/history")
def get_benchmark_history(limit: int = 20) -> dict:
    if not BENCHMARK_HISTORY.exists():
        return {"reports": []}
    lines = BENCHMARK_HISTORY.read_text(encoding="utf-8").splitlines()
    selected = lines[-max(1, min(limit, 100)):]
    return {"reports": [json.loads(line) for line in selected if line.strip()]}


@app.post("/api/tooling/openings/build")
def build_openings(req: OpeningBuildRequest) -> dict:
    if not req.pgn_text.strip():
        raise HTTPException(status_code=400, detail="PGN text is required.")

    output_json = OPENING_JSON_PATH if req.activate else OPENING_GENERATED_JSON_PATH
    output_bin = OPENING_BIN_PATH if req.activate else OPENING_GENERATED_BIN_PATH

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".pgn", delete=False) as handle:
        handle.write(req.pgn_text)
        temp_path = Path(handle.name)

    try:
        games_seen, games_used, unique_positions = build_opening_book(
            pgn_path=temp_path,
            output_path=output_json,
            max_games=req.max_games,
            max_plies=max(1, req.max_plies),
            min_elo=req.min_elo,
        )
        book = json.loads(output_json.read_text(encoding="utf-8"))
        polyglot_entries = write_polyglot_book(book, output_bin)
    finally:
        temp_path.unlink(missing_ok=True)

    return {
        "games_seen": games_seen,
        "games_used": games_used,
        "unique_positions": unique_positions,
        "polyglot_entries": polyglot_entries,
        "json_path": str(output_json),
        "polyglot_path": str(output_bin),
        "activated": req.activate,
    }


# ---------------------------------------------------------------------------
# WebSocket — live Q-learning training stream
# ---------------------------------------------------------------------------

@app.websocket("/api/train/qlearning")
async def qlearning_training(websocket: WebSocket):
    """Stream Q-learning self-play training progress.

    The client sends a JSON config:
        {"episodes": 500, "save": true}

    The server sends JSON messages:
        {"episode": N, "result": "win"|"loss"|"draw", "total_reward": float,
         "q_table_states": int, "epsilon": float}
    A final message {"done": true, "episodes_trained": N} is sent at the end.
    """
    await websocket.accept()

    try:
        from engines.v3_qlearning import QLearningEngine
        import chess
    except ImportError:
        await websocket.send_json({"error": "Q-learning engine not available."})
        await websocket.close()
        return

    try:
        config = await websocket.receive_json()
    except Exception:
        config = {}

    episodes = min(int(config.get("episodes", 200)), 5000)
    save_after = bool(config.get("save", True))

    engine = QLearningEngine(epsilon=0.3, load_weights=True)

    for ep in range(episodes):
        board = chess.Board()
        total_reward = 0.0

        while not board.is_game_over():
            state = engine._state_key(board)

            try:
                move = engine.get_move(board)
            except NotImplementedError:
                # Engine not implemented — send error and stop
                await websocket.send_json(
                    {"error": "QLearning engine get_move not implemented."}
                )
                await websocket.close()
                return

            board_before = board.copy()
            board.push(move)
            next_state = engine._state_key(board)
            done = board.is_game_over()

            try:
                reward = engine._reward(board_before, move, board)
            except NotImplementedError:
                await websocket.send_json(
                    {"error": "QLearning engine _reward not implemented."}
                )
                await websocket.close()
                return

            next_legal = [m.uci() for m in board.legal_moves]

            try:
                engine.update(state, move.uci(), reward, next_state, done, next_legal)
            except NotImplementedError:
                await websocket.send_json(
                    {"error": "QLearning engine update not implemented."}
                )
                await websocket.close()
                return

            total_reward += reward

        engine.training_episodes += 1
        # Decay epsilon
        engine.epsilon = max(0.05, engine.epsilon * 0.999)

        result = "ongoing"
        if board.is_checkmate():
            result = "loss" if board.turn == chess.WHITE else "win"
        elif board.is_game_over():
            result = "draw"

        # Send progress update every episode (throttled by yield)
        await websocket.send_json({
            "episode": engine.training_episodes,
            "result": result,
            "total_reward": round(total_reward, 3),
            "q_table_states": len(engine.q_table),
            "epsilon": round(engine.epsilon, 4),
        })

        # Yield control to allow other tasks to run
        if ep % 10 == 0:
            await asyncio.sleep(0)

    if save_after:
        engine.save_weights()

    await websocket.send_json({
        "done": True,
        "episodes_trained": engine.training_episodes,
        "q_table_states": len(engine.q_table),
    })
    await websocket.close()
