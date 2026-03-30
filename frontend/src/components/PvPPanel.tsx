import { useState } from "react";
import type { AuthUser } from "../services/api";

interface PvPPanelProps {
  user: AuthUser | null;
  pending: boolean;
  onCreate: (playerName: string, preferredColor: "white" | "black" | "random") => Promise<void>;
  onJoin: (joinCode: string, playerName: string) => Promise<void>;
}

export default function PvPPanel({ user, pending, onCreate, onJoin }: PvPPanelProps) {
  const [createName, setCreateName] = useState(user?.display_name ?? "");
  const [joinName, setJoinName] = useState(user?.display_name ?? "");
  const [joinCode, setJoinCode] = useState("");
  const [preferredColor, setPreferredColor] = useState<"white" | "black" | "random">("white");

  return (
    <div className="panel stack-md">
      <h3>Player vs Player</h3>

      <div className="tool-box stack-sm">
        <label className="stack-xs">
          <span>Your name</span>
          <input className="text-input" value={createName} onChange={(e) => setCreateName(e.target.value)} />
        </label>
        <label className="stack-xs">
          <span>Seat</span>
          <select className="engine-select" value={preferredColor} onChange={(e) => setPreferredColor(e.target.value as "white" | "black" | "random")}>
            <option value="white">White</option>
            <option value="black">Black</option>
            <option value="random">Random</option>
          </select>
        </label>
        <button className="btn btn-primary" onClick={() => void onCreate(createName, preferredColor)} disabled={pending || !createName.trim()}>
          Create room
        </button>
      </div>

      <div className="tool-box stack-sm">
        <label className="stack-xs">
          <span>Join code</span>
          <input className="text-input" value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} />
        </label>
        <label className="stack-xs">
          <span>Your name</span>
          <input className="text-input" value={joinName} onChange={(e) => setJoinName(e.target.value)} />
        </label>
        <button className="btn btn-warning" onClick={() => void onJoin(joinCode, joinName)} disabled={pending || !joinCode.trim() || !joinName.trim()}>
          Join room
        </button>
      </div>
    </div>
  );
}