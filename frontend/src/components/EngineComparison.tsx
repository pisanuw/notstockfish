/**
 * EngineComparison component.
 *
 * Shows a table of every engine's recommended move and score for the
 * current board position.  Engines that haven't been implemented show
 * a "not implemented" placeholder.
 */


import type { CompareEntry } from "../services/api";

interface EngineComparisonProps {
  results: CompareEntry[] | null;
  loading: boolean;
  onCompare: () => void;
  gameActive: boolean;
  selectedMove?: string | null;
  onSelectMove?: (move: string | null) => void;
}

export default function EngineComparison({
  results,
  loading,
  onCompare,
  gameActive,
  selectedMove = null,
  onSelectMove,
}: EngineComparisonProps) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h3>Compare Engines</h3>
        <button
          className="btn btn-primary"
          onClick={onCompare}
          disabled={!gameActive || loading}
        >
          {loading ? "Thinking…" : "Ask all engines"}
        </button>
      </div>

      {!results && !loading && (
        <p className="muted">
          Click "Ask all engines" to see what each version would play.
        </p>
      )}

      {results && (
        <table className="compare-table">
          <thead>
            <tr>
              <th>Version</th>
              <th>Engine</th>
              <th>Move</th>
              <th>Score</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
            {results.map((entry) => (
              <tr
                key={entry.engine_id}
                className={[
                  entry.implemented ? "" : "unimplemented-row",
                  entry.move && selectedMove === entry.move ? "selected-compare-row" : "",
                  entry.move ? "clickable-compare-row" : "",
                ].join(" ").trim()}
                onClick={() => {
                  if (!entry.move || !entry.implemented || !onSelectMove) return;
                  onSelectMove(selectedMove === entry.move ? null : entry.move);
                }}
              >
                <td>
                  <code>{entry.engine_id}</code>
                </td>
                <td>{entry.name}</td>
                <td>
                  {entry.implemented && entry.move ? (
                    <button
                      className="compare-move-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectMove?.(selectedMove === entry.move ? null : entry.move);
                      }}
                    >
                      {formatMove(entry.move)}
                    </button>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  {entry.score !== null && entry.score !== undefined ? (
                    <ScoreBadge score={entry.score} />
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td className="reasoning-cell">
                  {entry.reasoning ?? (entry.implemented ? "" : "Not implemented")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/** Show the move in a slightly friendlier format: e2→e4 */
function formatMove(uci: string): string {
  if (uci.length < 4) return uci;
  const from = uci.slice(0, 2);
  const to = uci.slice(2, 4);
  const promo = uci.length > 4 ? `=${uci[4].toUpperCase()}` : "";
  return `${from}→${to}${promo}`;
}

/** Colour-code the evaluation score. */
function ScoreBadge({ score }: { score: number }) {
  const color =
    score > 0.5 ? "#388e3c" : score < -0.5 ? "#c62828" : "#f57f17";
  return (
    <span style={{ color, fontWeight: 600 }}>
      {score > 0 ? "+" : ""}
      {score.toFixed(2)}
    </span>
  );
}
