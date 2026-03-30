/**
 * Typed API client for the stockreptile backend.
 *
 * All communication with the FastAPI backend goes through this module.
 * The BASE_URL points to the backend dev server and can be overridden via
 * an environment variable.
 */

import axios from "axios";

function defaultApiBaseUrl(): string {
  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }

  const protocol = window.location.protocol === "https:" ? "https:" : "http:";
  const hostname = window.location.hostname || "localhost";
  const isLocalhost = hostname === "localhost" || hostname === "127.0.0.1";
  const isPrivateIpv4 =
    /^10\./.test(hostname) ||
    /^192\.168\./.test(hostname) ||
    /^172\.(1[6-9]|2\d|3[0-1])\./.test(hostname);

  if (isLocalhost || isPrivateIpv4) {
    return `${protocol}//${hostname}:8000`;
  }

  // In hosted environments, default to same-origin /api unless VITE_API_URL is set.
  return window.location.origin;
}

export const BASE_URL = import.meta.env.VITE_API_URL ?? defaultApiBaseUrl();

const api = axios.create({ baseURL: BASE_URL });

// ---------------------------------------------------------------------------
// Types (mirroring the backend response shapes)
// ---------------------------------------------------------------------------

export interface EngineInfo {
  id: string;
  name: string;
  description: string;
  version: string;
  implemented: boolean;
  training_episodes?: number;
  q_table_states?: number;
}

export interface MoveInfo {
  move: string | null;      // UCI notation, e.g. "e2e4"
  score: number | null;
  depth: number | null;
  nodes_searched: number | null;
  reasoning: string | null;
}

export interface GameState {
  game_id: string;
  fen: string;
  turn: "white" | "black";
  player_color: "white" | "black";
  legal_moves: string[];          // UCI strings
  move_history: string[];         // UCI strings
  status: string;                 // "ongoing" | "check" | "checkmate:white" | ...
  engine_id: string;
  engine_name: string;
  engine_move?: MoveInfo;         // only present after a move response
}

export interface CompareEntry extends MoveInfo {
  engine_id: string;
  name: string;
  implemented: boolean;
}

export interface HealthResponse {
  status: "ok";
}

export interface EngineOptions {
  plies?: number;
  fallback_depth?: number;
  minimum_weight?: number;
  use_weighted_book?: boolean;
  book_path?: string;
}

export interface AuthUser {
  user_id: string;
  email: string;
  display_name: string;
  provider: string;
  created_at: number;
  last_login_at: number;
}

export interface AuthConfig {
  magic_link_enabled: boolean;
  google_enabled: boolean;
  google_client_id?: string | null;
}

export interface MagicLinkStartResponse {
  sent: boolean;
  magic_link_token: string;
  magic_link_url: string;
  expires_in_seconds: number;
  user: AuthUser;
}

export interface AuthSessionResponse {
  access_token: string;
  user: AuthUser;
}

export interface PvPGameState {
  game_id: string;
  join_code: string;
  mode: "pvp";
  fen: string;
  turn: "white" | "black";
  player_color: "white" | "black" | null;
  legal_moves: string[];
  move_history: string[];
  status: string;
  waiting_for_opponent: boolean;
  players: {
    white: string | null;
    black: string | null;
  };
}

export interface PvPCreateJoinResponse {
  player_token: string;
  state: PvPGameState;
}

export interface BenchmarkResult {
  engine_id: string;
  engine_name: string;
  avg_ms: number;
  min_ms: number;
  max_ms: number;
  avg_nodes: number;
}

export interface BenchmarkReport {
  created_at: string;
  fens: string[];
  engine_ids: string[];
  results: BenchmarkResult[];
}

export interface OpeningBuildResult {
  games_seen: number;
  games_used: number;
  unique_positions: number;
  polyglot_entries: number;
  json_path: string;
  polyglot_path: string;
  activated: boolean;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/** List all registered engines. */
export async function getEngines(): Promise<EngineInfo[]> {
  const { data } = await api.get<EngineInfo[]>("/api/engines");
  return data;
}

/** Lightweight connectivity check for the backend. */
export async function getBackendHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>("/api/health");
  return data;
}

export async function getAuthConfig(): Promise<AuthConfig> {
  const { data } = await api.get<AuthConfig>("/api/auth/config");
  return data;
}

export async function requestMagicLink(
  email: string,
  displayName?: string
): Promise<MagicLinkStartResponse> {
  const { data } = await api.post<MagicLinkStartResponse>("/api/auth/magic-link/request", {
    email,
    display_name: displayName ?? null,
  });
  return data;
}

export async function verifyMagicLink(token: string): Promise<AuthSessionResponse> {
  const { data } = await api.post<AuthSessionResponse>("/api/auth/magic-link/verify", { token });
  return data;
}

export async function loginWithGoogle(idToken: string): Promise<AuthSessionResponse> {
  const { data } = await api.post<AuthSessionResponse>("/api/auth/google", { id_token: idToken });
  return data;
}

export async function getCurrentUser(accessToken: string): Promise<AuthUser> {
  const { data } = await api.get<{ user: AuthUser }>("/api/auth/me", {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  return data.user;
}

export async function logoutAuth(accessToken?: string): Promise<void> {
  await api.post(
    "/api/auth/logout",
    { access_token: accessToken ?? null },
    accessToken
      ? { headers: { Authorization: `Bearer ${accessToken}` } }
      : undefined
  );
}

/** Start a new game. */
export async function newGame(
  engineId: string,
  playerColor: "white" | "black",
  engineOptions?: EngineOptions
): Promise<GameState> {
  const { data } = await api.post<GameState>("/api/game/new", {
    engine_id: engineId,
    player_color: playerColor,
    engine_options: engineOptions ?? null,
  });
  return data;
}

/** Fetch current game state. */
export async function getState(gameId: string): Promise<GameState> {
  const { data } = await api.get<GameState>(`/api/game/${gameId}/state`);
  return data;
}

/** Submit a human move.  Returns the updated state (including engine reply). */
export async function makeMove(
  gameId: string,
  fromSq: string,
  toSq: string,
  promotion?: string
): Promise<GameState> {
  const { data } = await api.post<GameState>(`/api/game/${gameId}/move`, {
    from_sq: fromSq,
    to_sq: toSq,
    promotion: promotion ?? null,
  });
  return data;
}

/** Switch the active engine mid-game. */
export async function switchEngine(
  gameId: string,
  engineId: string,
  engineOptions?: EngineOptions
): Promise<GameState> {
  const { data } = await api.patch<GameState>(`/api/game/${gameId}/engine`, {
    engine_id: engineId,
    engine_options: engineOptions ?? null,
  });
  return data;
}

/** Ask all engines what they recommend. */
export async function compareEngines(gameId: string): Promise<CompareEntry[]> {
  const { data } = await api.post<CompareEntry[]>(
    `/api/game/${gameId}/compare`
  );
  return data;
}

export async function createPvpGame(
  playerName: string,
  preferredColor: "white" | "black" | "random",
  accessToken?: string
): Promise<PvPCreateJoinResponse> {
  const { data } = await api.post<PvPCreateJoinResponse>(
    "/api/pvp/create",
    {
      player_name: playerName,
      preferred_color: preferredColor,
    },
    accessToken
      ? { headers: { Authorization: `Bearer ${accessToken}` } }
      : undefined
  );
  return data;
}

export async function joinPvpGame(
  joinCode: string,
  playerName: string,
  accessToken?: string
): Promise<PvPCreateJoinResponse> {
  const { data } = await api.post<PvPCreateJoinResponse>(
    "/api/pvp/join",
    {
      join_code: joinCode,
      player_name: playerName,
    },
    accessToken
      ? { headers: { Authorization: `Bearer ${accessToken}` } }
      : undefined
  );
  return data;
}

export async function getPvpState(
  gameId: string,
  playerToken?: string
): Promise<PvPGameState> {
  const { data } = await api.get<PvPGameState>(`/api/pvp/${gameId}/state`, {
    params: playerToken ? { player_token: playerToken } : undefined,
  });
  return data;
}

export async function makePvpMove(
  gameId: string,
  playerToken: string,
  fromSq: string,
  toSq: string,
  promotion?: string
): Promise<PvPGameState> {
  const { data } = await api.post<PvPGameState>(`/api/pvp/${gameId}/move`, {
    player_token: playerToken,
    from_sq: fromSq,
    to_sq: toSq,
    promotion: promotion ?? null,
  });
  return data;
}

export async function runBenchmarks(
  engineIds?: string[],
  persist = true
): Promise<BenchmarkReport> {
  const { data } = await api.post<BenchmarkReport>("/api/tooling/benchmarks/run", {
    engine_ids: engineIds ?? null,
    persist,
  });
  return data;
}

export async function getLatestBenchmark(): Promise<BenchmarkReport | null> {
  const { data } = await api.get<{ report: BenchmarkReport | null }>("/api/tooling/benchmarks/latest");
  return data.report;
}

export async function getBenchmarkHistory(limit = 20): Promise<BenchmarkReport[]> {
  const { data } = await api.get<{ reports: BenchmarkReport[] }>("/api/tooling/benchmarks/history", {
    params: { limit },
  });
  return data.reports;
}

export async function buildOpeningBook(payload: {
  pgnText: string;
  maxGames?: number;
  maxPlies?: number;
  minElo?: number;
  activate?: boolean;
}): Promise<OpeningBuildResult> {
  const { data } = await api.post<OpeningBuildResult>("/api/tooling/openings/build", {
    pgn_text: payload.pgnText,
    max_games: payload.maxGames ?? null,
    max_plies: payload.maxPlies ?? 16,
    min_elo: payload.minElo ?? null,
    activate: payload.activate ?? false,
  });
  return data;
}

// ---------------------------------------------------------------------------
// WebSocket helper for Q-learning training
// ---------------------------------------------------------------------------

export interface TrainingConfig {
  episodes: number;
  save: boolean;
}

export interface TrainingProgress {
  episode?: number;
  result?: "win" | "loss" | "draw" | "ongoing";
  total_reward?: number;
  q_table_states?: number;
  epsilon?: number;
  done?: boolean;
  episodes_trained?: number;
  error?: string;
}

/**
 * Open a WebSocket to the training endpoint and call `onMessage` for each
 * progress update.  Returns a close function.
 */
export function startTraining(
  config: TrainingConfig,
  onMessage: (msg: TrainingProgress) => void,
  onClose?: () => void
): () => void {
  const wsUrl = BASE_URL.replace(/^http/, "ws") + "/api/train/qlearning";
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    ws.send(JSON.stringify(config));
  };

  ws.onmessage = (event) => {
    try {
      const msg: TrainingProgress = JSON.parse(event.data);
      onMessage(msg);
    } catch {
      // ignore malformed messages
    }
  };

  ws.onclose = () => onClose?.();

  return () => ws.close();
}
