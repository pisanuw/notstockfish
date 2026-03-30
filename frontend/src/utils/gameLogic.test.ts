import { describe, expect, it } from "vitest";
import { Chess } from "chess.js";
import type { GameState } from "../services/api";
import { formatClock, moveToUci, optimisticEngineMove, statusFromChess } from "./gameLogic";

function baseGameState(): GameState {
  const board = new Chess();
  return {
    game_id: "g1",
    fen: board.fen(),
    turn: "white",
    player_color: "white",
    legal_moves: board.moves({ verbose: true }).map((move) => moveToUci(move)),
    move_history: [],
    status: "ongoing",
    engine_id: "v0",
    engine_name: "Random",
  };
}

describe("gameLogic", () => {
  it("formats clock values", () => {
    expect(formatClock(90_000)).toBe("1:30");
    expect(formatClock(3_723_000)).toBe("1:02:03");
    expect(formatClock(0)).toBe("0:00");
  });

  it("applies optimistic move and updates turn/history", () => {
    const state = baseGameState();
    const next = optimisticEngineMove(state, "e2", "e4");

    expect(next).not.toBeNull();
    expect(next?.move_history).toEqual(["e2e4"]);
    expect(next?.turn).toBe("black");
    expect(next?.legal_moves.length).toBeGreaterThan(0);
  });

  it("returns null for illegal optimistic move", () => {
    const state = baseGameState();
    const next = optimisticEngineMove(state, "e2", "e5");
    expect(next).toBeNull();
  });

  it("derives checkmate status correctly", () => {
    const replay = new Chess();
    replay.move("f3");
    replay.move("e5");
    replay.move("g4");
    replay.move("Qh4#");
    expect(statusFromChess(replay)).toBe("checkmate:black");
  });
});