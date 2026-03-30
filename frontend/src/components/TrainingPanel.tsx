/**
 * TrainingPanel component.
 *
 * Connects to the backend WebSocket to run live Q-learning training and
 * displays a real-time progress chart (episode rewards and Q-table growth).
 */

import { useState, useRef, useCallback } from "react";
import { startTraining, type TrainingProgress } from "../services/api";

interface DataPoint {
  episode: number;
  reward: number;
  qStates: number;
  epsilon: number;
}

export default function TrainingPanel() {
  const [episodes, setEpisodes] = useState(200);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState<DataPoint[]>([]);
  const [lastMsg, setLastMsg] = useState<TrainingProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const stopRef = useRef<(() => void) | null>(null);

  const handleStart = useCallback(() => {
    setRunning(true);
    setProgress([]);
    setError(null);
    setLastMsg(null);

    const stop = startTraining(
      { episodes, save: true },
      (msg) => {
        if (msg.error) {
          setError(msg.error);
          setRunning(false);
          return;
        }
        if (msg.done) {
          setRunning(false);
          return;
        }
        if (msg.episode !== undefined) {
          setLastMsg(msg);
          setProgress((prev) => {
            // Keep at most 500 data points (down-sample)
            const next: DataPoint = {
              episode: msg.episode!,
              reward: msg.total_reward ?? 0,
              qStates: msg.q_table_states ?? 0,
              epsilon: msg.epsilon ?? 0,
            };
            if (prev.length >= 500) {
              const step = Math.floor(prev.length / 400);
              return [...prev.filter((_, i) => i % step === 0), next];
            }
            return [...prev, next];
          });
        }
      },
      () => setRunning(false)
    );

    stopRef.current = stop;
  }, [episodes]);

  const handleStop = useCallback(() => {
    stopRef.current?.();
    setRunning(false);
  }, []);

  // Simple SVG sparkline
  const renderChart = (
    data: DataPoint[],
    key: keyof Omit<DataPoint, "episode">,
    color: string,
    label: string
  ) => {
    if (data.length < 2) return null;
    const values = data.map((d) => d[key] as number);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const W = 400;
    const H = 80;
    const points = data
      .map(
        (d, i) =>
          `${(i / (data.length - 1)) * W},${H - ((( d[key] as number) - min) / range) * H}`
      )
      .join(" ");

    return (
      <div style={{ marginBottom: 12 }}>
        <p style={{ margin: "4px 0", fontSize: 12, color: "#666" }}>
          {label} (latest:{" "}
          {typeof values[values.length - 1] === "number"
            ? values[values.length - 1].toFixed(3)
            : values[values.length - 1]}
          )
        </p>
        <svg
          width={W}
          height={H}
          style={{ border: "1px solid #e0e0e0", borderRadius: 4, background: "#fafafa" }}
        >
          <polyline
            points={points}
            fill="none"
            stroke={color}
            strokeWidth={1.5}
          />
        </svg>
      </div>
    );
  };

  return (
    <div className="panel">
      <h3>Q-Learning Live Training</h3>
      <p className="muted">
        Run self-play training episodes and watch the Q-table grow in real time.
        The trained weights are saved and used by v3 automatically.
      </p>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <label style={{ fontSize: 14 }}>
          Episodes:
          <input
            type="number"
            min={1}
            max={5000}
            value={episodes}
            onChange={(e) => setEpisodes(Number(e.target.value))}
            style={{ marginLeft: 8, width: 80 }}
            disabled={running}
          />
        </label>

        {!running ? (
          <button className="btn btn-primary" onClick={handleStart}>
            Start Training
          </button>
        ) : (
          <button className="btn btn-danger" onClick={handleStop}>
            Stop
          </button>
        )}
      </div>

      {error && <p style={{ color: "#c62828" }}>Error: {error}</p>}

      {lastMsg && !lastMsg.done && (
        <div className="training-stats">
          <span>Episode: {lastMsg.episode}</span>
          <span>Result: {lastMsg.result}</span>
          <span>ε: {lastMsg.epsilon?.toFixed(4)}</span>
          <span>Q-states: {lastMsg.q_table_states}</span>
        </div>
      )}

      {progress.length > 1 && (
        <>
          {renderChart(progress, "reward", "#6200ea", "Episode Reward")}
          {renderChart(progress, "qStates", "#0288d1", "Q-Table States")}
          {renderChart(progress, "epsilon", "#e65100", "Epsilon (exploration)")}
        </>
      )}
    </div>
  );
}
