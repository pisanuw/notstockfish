import { Chess } from "chess.js";
import type { GameState } from "../services/api";

export function statusFromChess(replay: Chess): string {
  if (replay.isCheckmate()) {
    const winner = replay.turn() === "w" ? "black" : "white";
    return `checkmate:${winner}`;
  }
  if (replay.isStalemate()) {
    return "draw:stalemate";
  }
  if (replay.isInsufficientMaterial()) {
    return "draw:insufficient_material";
  }
  if (replay.isDraw()) {
    return "draw";
  }
  if (replay.isCheck()) {
    return "check";
  }
  return "ongoing";
}

export function moveToUci(move: { from: string; to: string; promotion?: string }): string {
  return `${move.from}${move.to}${move.promotion ?? ""}`;
}

export function optimisticEngineMove(
  state: GameState,
  from: string,
  to: string,
  promotion?: string
): GameState | null {
  const replay = new Chess(state.fen);
  let moved;
  try {
    moved = replay.move({ from, to, promotion });
  } catch {
    return null;
  }
  if (!moved) {
    return null;
  }

  const legal = replay.moves({ verbose: true }).map((move) => moveToUci(move));
  const uci = moveToUci({ from, to, promotion });
  return {
    ...state,
    fen: replay.fen(),
    turn: replay.turn() === "w" ? "white" : "black",
    legal_moves: legal,
    move_history: [...state.move_history, uci],
    status: statusFromChess(replay),
    engine_move: undefined,
  };
}

export function formatClock(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes >= 60) {
    const hours = Math.floor(minutes / 60);
    const remMinutes = minutes % 60;
    return `${hours}:${String(remMinutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}