/**
 * EngineSelector component.
 *
 * Displays a dropdown of registered engines.  When a game is active it
 * also shows a "Switch engine mid-game" button.
 */

import React from "react";
import type { EngineInfo } from "../services/api";

interface V4Options {
  fallbackDepth: number;
  minimumWeight: number;
  useWeightedBook: boolean;
  bookPath: string;
}

interface EngineSelectorProps {
  engines: EngineInfo[];
  selectedId: string;
  onChange: (id: string) => void;
  onSwitch?: (id: string) => void;  // only present when a game is active
  greedyPlies?: number;
  onGreedyPliesChange?: (plies: number) => void;
  v4Options: V4Options;
  onV4OptionsChange: (next: V4Options) => void;
  gameActive: boolean;
  pendingSwitch?: boolean;
}

const BADGE: Record<string, { bg: string; text: string }> = {
  v0: { bg: "#9e9e9e", text: "Random" },
  v1: { bg: "#42a5f5", text: "Greedy" },
  v2: { bg: "#66bb6a", text: "Minimax" },
  v3: { bg: "#ab47bc", text: "Q-Learn" },
  v4: { bg: "#ef7c00", text: "Opening" },
};

export default function EngineSelector({
  engines,
  selectedId,
  onChange,
  onSwitch,
  greedyPlies = 1,
  onGreedyPliesChange,
  v4Options,
  onV4OptionsChange,
  gameActive,
  pendingSwitch = false,
}: EngineSelectorProps) {
  const [localId, setLocalId] = React.useState(selectedId);

  React.useEffect(() => {
    setLocalId(selectedId);
  }, [selectedId]);

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    setLocalId(e.target.value);
    if (!gameActive) {
      onChange(e.target.value);
    }
  }

  function handleSwitch() {
    if (onSwitch) onSwitch(localId);
  }

  function handlePliesChange(e: React.ChangeEvent<HTMLSelectElement>) {
    onGreedyPliesChange?.(Number(e.target.value));
  }

  function updateV4Options(patch: Partial<V4Options>) {
    onV4OptionsChange({ ...v4Options, ...patch });
  }

  return (
    <div className="panel">
      <h3>Engine</h3>

      <select value={localId} onChange={handleChange} className="engine-select">
        {engines.map((e) => (
          <option key={e.id} value={e.id} disabled={!e.implemented && e.id !== "v0"}>
            {e.name}
            {!e.implemented ? " (not implemented)" : ""}
          </option>
        ))}
      </select>

      {/* Show details of the selected engine */}
      {engines
        .filter((e) => e.id === localId)
        .map((e) => (
          <div key={e.id} className="engine-detail">
            <span
              className="badge"
              style={{ background: BADGE[e.id]?.bg ?? "#607d8b" }}
            >
              {BADGE[e.id]?.text ?? e.version}
            </span>
            <p className="engine-description">{e.description}</p>
            {e.training_episodes !== undefined && (
              <p className="engine-meta">
                Trained episodes: {e.training_episodes} / Q-states:{" "}
                {e.q_table_states}
              </p>
            )}
          </div>
        ))}

      {localId === "v1" && (
        <label style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10 }}>
          <span style={{ fontSize: "0.85rem", color: "#555" }}>Greedy search plies:</span>
          <select value={greedyPlies} onChange={handlePliesChange} className="engine-select" style={{ margin: 0 }}>
            {Array.from({ length: 10 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
        </label>
      )}

      {localId === "v4" && (
        <div className="stack-sm" style={{ marginTop: 10 }}>
          <label className="stack-xs">
            <span style={{ fontSize: "0.85rem", color: "#555" }}>Fallback search depth</span>
            <select
              value={v4Options.fallbackDepth}
              onChange={(e) => updateV4Options({ fallbackDepth: Number(e.target.value) })}
              className="engine-select"
              style={{ margin: 0 }}
            >
              {Array.from({ length: 6 }, (_, i) => i + 1).map((depth) => (
                <option key={depth} value={depth}>{depth}</option>
              ))}
            </select>
          </label>

          <label className="stack-xs">
            <span style={{ fontSize: "0.85rem", color: "#555" }}>Minimum book weight</span>
            <input
              className="text-input"
              type="number"
              min={0}
              value={v4Options.minimumWeight}
              onChange={(e) => updateV4Options({ minimumWeight: Number(e.target.value) })}
            />
          </label>

          <label className="stack-xs">
            <span style={{ fontSize: "0.85rem", color: "#555" }}>Custom book path</span>
            <input
              className="text-input"
              value={v4Options.bookPath}
              onChange={(e) => updateV4Options({ bookPath: e.target.value })}
              placeholder="Optional /absolute/path/to/openings.bin"
            />
          </label>

          <label className="check-label">
            <input
              type="checkbox"
              checked={v4Options.useWeightedBook}
              onChange={(e) => updateV4Options({ useWeightedBook: e.target.checked })}
            />
            <span>Use weighted Polyglot / JSON book selection</span>
          </label>
        </div>
      )}

      {/* Switch button — only shown during an active game */}
      {gameActive && localId !== selectedId && (
        <button
          className="btn btn-warning"
          onClick={handleSwitch}
          disabled={pendingSwitch}
        >
          {pendingSwitch ? "Switching…" : `Switch to ${localId} mid-game`}
        </button>
      )}
    </div>
  );
}
