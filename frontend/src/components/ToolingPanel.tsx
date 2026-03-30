import { useState } from "react";
import type { BenchmarkReport, OpeningBuildResult } from "../services/api";

interface ToolingPanelProps {
  latestBenchmark: BenchmarkReport | null;
  benchmarkHistory: BenchmarkReport[];
  benchmarkLoading: boolean;
  openingLoading: boolean;
  lastOpeningResult: OpeningBuildResult | null;
  onRunBenchmarks: (engineIds?: string[]) => Promise<void>;
  onBuildOpenings: (payload: {
    pgnText: string;
    maxPlies: number;
    minElo?: number;
    activate: boolean;
  }) => Promise<void>;
}

export default function ToolingPanel({
  latestBenchmark,
  benchmarkHistory,
  benchmarkLoading,
  openingLoading,
  lastOpeningResult,
  onRunBenchmarks,
  onBuildOpenings,
}: ToolingPanelProps) {
  const [engineIdsText, setEngineIdsText] = useState("v0 v1 v2 v4");
  const [pgnText, setPgnText] = useState("");
  const [maxPlies, setMaxPlies] = useState(16);
  const [minElo, setMinElo] = useState(1800);
  const [activate, setActivate] = useState(false);

  const engineIds = engineIdsText
    .split(/[,\s]+/)
    .map((value) => value.trim())
    .filter(Boolean);

  return (
    <div className="panel stack-md">
      <h3>Engine Tools</h3>

      <div className="tool-box stack-sm">
        <div className="inline-actions">
          <strong>Benchmarks</strong>
          <button className="btn btn-primary" onClick={() => void onRunBenchmarks(engineIds)} disabled={benchmarkLoading}>
            {benchmarkLoading ? "Running…" : "Run benchmark"}
          </button>
        </div>
        <input
          className="text-input"
          value={engineIdsText}
          onChange={(e) => setEngineIdsText(e.target.value)}
          placeholder="v0 v1 v2 v4"
        />
        {latestBenchmark && (
          <div className="stack-sm">
            <div className="muted">Latest benchmark: {new Date(latestBenchmark.created_at).toLocaleString()}</div>
            <table className="compare-table">
              <thead>
                <tr>
                  <th>Engine</th>
                  <th>Avg ms</th>
                  <th>Avg nodes</th>
                </tr>
              </thead>
              <tbody>
                {latestBenchmark.results.map((result) => (
                  <tr key={result.engine_id}>
                    <td>{result.engine_id}</td>
                    <td>{result.avg_ms.toFixed(2)}</td>
                    <td>{result.avg_nodes.toFixed(0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {benchmarkHistory.length > 0 && (
          <p className="muted">Saved reports: {benchmarkHistory.length}</p>
        )}
      </div>

      <div className="tool-box stack-sm">
        <strong>Opening book builder</strong>
        <textarea
          className="text-area"
          value={pgnText}
          onChange={(e) => setPgnText(e.target.value)}
          placeholder="Paste PGN data here to build JSON and Polyglot opening books."
          rows={10}
        />
        <div className="inline-grid">
          <label className="stack-xs">
            <span>Max plies</span>
            <input className="text-input" type="number" min={1} max={40} value={maxPlies} onChange={(e) => setMaxPlies(Number(e.target.value))} />
          </label>
          <label className="stack-xs">
            <span>Min Elo</span>
            <input className="text-input" type="number" min={0} value={minElo} onChange={(e) => setMinElo(Number(e.target.value))} />
          </label>
          <label className="check-label">
            <input type="checkbox" checked={activate} onChange={(e) => setActivate(e.target.checked)} />
            <span>Activate for v4</span>
          </label>
        </div>
        <button
          className="btn btn-warning"
          onClick={() => void onBuildOpenings({ pgnText, maxPlies, minElo, activate })}
          disabled={openingLoading || !pgnText.trim()}
        >
          {openingLoading ? "Building…" : "Build opening book"}
        </button>
        {lastOpeningResult && (
          <div className="stack-xs muted">
            <span>Games used: {lastOpeningResult.games_used}</span>
            <span>Unique positions: {lastOpeningResult.unique_positions}</span>
            <span>Polyglot entries: {lastOpeningResult.polyglot_entries}</span>
          </div>
        )}
      </div>
    </div>
  );
}