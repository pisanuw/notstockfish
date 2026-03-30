/**
 * stockreptile — root application component.
 *
 * Layout:
 *   Left column:  Chess board + game controls
 *   Right column: Engine selector, comparison panel, training panel (tabs)
 */

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { Chess } from "chess.js";
import Board from "./components/Board";
import EngineSelector from "./components/EngineSelector";
import EngineComparison from "./components/EngineComparison";
import TrainingPanel from "./components/TrainingPanel";
import AuthPanel from "./components/AuthPanel";
import PvPPanel from "./components/PvPPanel";
import ToolingPanel from "./components/ToolingPanel";
import {
  BASE_URL,
  buildOpeningBook,
  compareEngines,
  createPvpGame,
  getAuthConfig,
  getBackendHealth,
  getBenchmarkHistory,
  getCurrentUser,
  getEngines,
  getLatestBenchmark,
  getPvpState,
  joinPvpGame,
  loginWithGoogle,
  logoutAuth,
  makeMove,
  makePvpMove,
  newGame,
  requestMagicLink,
  runBenchmarks,
  switchEngine,
  verifyMagicLink,
  type AuthConfig,
  type AuthSessionResponse,
  type AuthUser,
  type BenchmarkReport,
  type CompareEntry,
  type EngineInfo,
  type GameState,
  type OpeningBuildResult,
  type PvPGameState,
} from "./services/api";
import { formatClock, optimisticEngineMove } from "./utils/gameLogic";
import "./App.css";

type RightTab = "engine" | "compare" | "training" | "tools" | "account";
type BackendStatus = "checking" | "online" | "offline";
type StartMode = "engine" | "pvp";
type ActiveGame = GameState | PvPGameState;

type ClockPreset = {
  id: string;
  label: string;
  category: "bullet" | "blitz" | "rapid";
  baseSeconds: number;
  incrementSeconds: number;
};

type ClockState = {
  whiteMs: number;
  blackMs: number;
  incrementMs: number;
  flagged: "white" | "black" | null;
};

const AUTH_STORAGE_KEY = "stockreptile.auth";
const CLOCK_TICK_MS = 100;

const CLOCK_PRESETS: ClockPreset[] = [
  { id: "bullet_1_0", label: "1 + 0", category: "bullet", baseSeconds: 60, incrementSeconds: 0 },
  { id: "bullet_2_1", label: "2 + 1", category: "bullet", baseSeconds: 120, incrementSeconds: 1 },
  { id: "blitz_3_0", label: "3 + 0", category: "blitz", baseSeconds: 180, incrementSeconds: 0 },
  { id: "blitz_3_2", label: "3 + 2", category: "blitz", baseSeconds: 180, incrementSeconds: 2 },
  { id: "blitz_5_0", label: "5 + 0", category: "blitz", baseSeconds: 300, incrementSeconds: 0 },
  { id: "blitz_5_3", label: "5 + 3", category: "blitz", baseSeconds: 300, incrementSeconds: 3 },
  { id: "rapid_10_0", label: "10 + 0", category: "rapid", baseSeconds: 600, incrementSeconds: 0 },
  { id: "rapid_10_5", label: "10 + 5", category: "rapid", baseSeconds: 600, incrementSeconds: 5 },
  { id: "rapid_15_10", label: "15 + 10", category: "rapid", baseSeconds: 900, incrementSeconds: 10 },
];

export default function App() {
  const [engines, setEngines] = useState<EngineInfo[]>([]);
  const [selectedEngine, setSelectedEngine] = useState<string>("v0");
  const [playerColor, setPlayerColor] = useState<"white" | "black" | "random">("white");
  const [engineGame, setEngineGame] = useState<GameState | null>(null);
  const [pvpGame, setPvpGame] = useState<PvPGameState | null>(null);
  const [pvpPlayerToken, setPvpPlayerToken] = useState<string | null>(null);
  const [startMode, setStartMode] = useState<StartMode>("engine");
  const [activeMode, setActiveMode] = useState<StartMode>("engine");
  const [compareResults, setCompareResults] = useState<CompareEntry[] | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [switchPending, setSwitchPending] = useState(false);
  const [pvpPending, setPvpPending] = useState(false);
  const [rightTab, setRightTab] = useState<RightTab>("engine");
  const [error, setError] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");
  const [clockEnabled, setClockEnabled] = useState(false);
  const [selectedClockPresetId, setSelectedClockPresetId] = useState("blitz_3_0");
  const [clockState, setClockState] = useState<ClockState | null>(null);
  const [greedyPlies, setGreedyPlies] = useState<number>(1);
  const [v4Options, setV4Options] = useState({
    fallbackDepth: 3,
    minimumWeight: 1,
    useWeightedBook: true,
    bookPath: "",
  });
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "failed">("idle");
  const [showCelebration, setShowCelebration] = useState(false);
  const [selectedCompareMove, setSelectedCompareMove] = useState<string | null>(null);
  const [authConfig, setAuthConfig] = useState<AuthConfig | null>(null);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [authPending, setAuthPending] = useState(false);
  const [latestBenchmark, setLatestBenchmark] = useState<BenchmarkReport | null>(null);
  const [benchmarkHistory, setBenchmarkHistory] = useState<BenchmarkReport[]>([]);
  const [benchmarkLoading, setBenchmarkLoading] = useState(false);
  const [openingLoading, setOpeningLoading] = useState(false);
  const [lastOpeningResult, setLastOpeningResult] = useState<OpeningBuildResult | null>(null);
  const previousMoveCountRef = useRef(0);
  const previousTurnRef = useRef<"white" | "black">("white");
  const previousClockMoveCountRef = useRef(0);
  const previousClockTurnRef = useRef<"white" | "black">("white");
  const previousStatusRef = useRef<string>("");
  const moveInFlightRef = useRef(false);
  const audioContextRef = useRef<AudioContext | null>(null);

  const activeGame: ActiveGame | null = activeMode === "engine" ? engineGame : pvpGame;
  const isEngineGame = activeMode === "engine" && engineGame !== null;
  const selectedClockPreset = CLOCK_PRESETS.find((preset) => preset.id === selectedClockPresetId) ?? CLOCK_PRESETS[2];

  const getEngineOptions = useCallback((engineId: string) => {
    if (engineId === "v1") {
      return { plies: Math.max(1, Math.min(10, greedyPlies)) };
    }
    if (engineId === "v4") {
      return {
        fallback_depth: Math.max(1, Math.min(6, v4Options.fallbackDepth)),
        minimum_weight: Math.max(0, v4Options.minimumWeight),
        use_weighted_book: v4Options.useWeightedBook,
        book_path: v4Options.bookPath.trim() || undefined,
      };
    }
    return undefined;
  }, [greedyPlies, v4Options]);

  const ensureAudioContext = useCallback(async () => {
    if (typeof window === "undefined") return null;
    if (!audioContextRef.current) {
      audioContextRef.current = new window.AudioContext();
    }
    if (audioContextRef.current.state === "suspended") {
      try {
        await audioContextRef.current.resume();
      } catch {
        return null;
      }
    }
    return audioContextRef.current;
  }, []);

  const playTone = useCallback(async (frequency: number, durationMs: number, type: OscillatorType, gainValue = 0.05) => {
    const context = await ensureAudioContext();
    if (!context) return;

    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = type;
    oscillator.frequency.value = frequency;
    gain.gain.value = gainValue;
    oscillator.connect(gain);
    gain.connect(context.destination);

    const now = context.currentTime;
    const durationSec = durationMs / 1000;
    gain.gain.setValueAtTime(gainValue, now);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + durationSec);
    oscillator.start(now);
    oscillator.stop(now + durationSec);
  }, [ensureAudioContext]);

  const playSoundEvent = useCallback(async (kind: "move" | "capture" | "check" | "win" | "lose") => {
    if (kind === "capture") {
      await playTone(220, 90, "square", 0.045);
      await playTone(165, 100, "triangle", 0.04);
      return;
    }
    if (kind === "check") {
      await playTone(740, 120, "sawtooth", 0.03);
      return;
    }
    if (kind === "win") {
      await playTone(523, 120, "triangle", 0.04);
      await playTone(659, 120, "triangle", 0.04);
      await playTone(784, 180, "triangle", 0.04);
      return;
    }
    if (kind === "lose") {
      await playTone(330, 140, "sine", 0.035);
      await playTone(247, 180, "sine", 0.035);
      return;
    }
    await playTone(440, 60, "sine", 0.03);
  }, [playTone]);

  const persistSession = useCallback((session: AuthSessionResponse) => {
    setAccessToken(session.access_token);
    setAuthUser(session.user);
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
  }, []);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setAuthUser(null);
    localStorage.removeItem(AUTH_STORAGE_KEY);
  }, []);

  const loadHealth = useCallback(async () => {
    try {
      await getBackendHealth();
      setBackendStatus("online");
    } catch {
      setBackendStatus("offline");
    }
  }, []);

  const loadEngines = useCallback(async () => {
    try {
      const engineList = await getEngines();
      setEngines(engineList);
      setBackendStatus("online");
    } catch {
      setBackendStatus("offline");
      setError(`Could not reach the backend at ${BASE_URL}. Is the server running?`);
    }
  }, []);

  const loadAuthRuntimeConfig = useCallback(async () => {
    try {
      setAuthConfig(await getAuthConfig());
    } catch {
      setAuthConfig(null);
    }
  }, []);

  const loadToolingReports = useCallback(async () => {
    try {
      const [latest, history] = await Promise.all([
        getLatestBenchmark(),
        getBenchmarkHistory(10),
      ]);
      setLatestBenchmark(latest);
      setBenchmarkHistory(history);
    } catch {
      // Non-critical UI data.
    }
  }, []);

  useEffect(() => {
    void loadEngines();
    void loadAuthRuntimeConfig();
    void loadToolingReports();
  }, [loadAuthRuntimeConfig, loadEngines, loadToolingReports]);

  useEffect(() => {
    void loadHealth();
    const intervalId = window.setInterval(() => {
      void loadHealth();
    }, 15000);
    return () => window.clearInterval(intervalId);
  }, [loadHealth]);

  useEffect(() => {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) {
      return;
    }

    try {
      const session = JSON.parse(raw) as AuthSessionResponse;
      setAccessToken(session.access_token);
      setAuthUser(session.user);
      void getCurrentUser(session.access_token)
        .then((user) => setAuthUser(user))
        .catch(() => clearSession());
    } catch {
      clearSession();
    }
  }, [clearSession]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const magicToken = params.get("magic_token");
    if (!magicToken) {
      return;
    }

    setAuthPending(true);
    void verifyMagicLink(magicToken)
      .then((session) => {
        persistSession(session);
        setError(null);
      })
      .catch((reason: unknown) => {
        setError(reason instanceof Error ? reason.message : String(reason));
      })
      .finally(() => {
        setAuthPending(false);
        params.delete("magic_token");
        const query = params.toString();
        window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
      });
  }, [persistSession]);

  useEffect(() => {
    if (!pvpGame || !pvpPlayerToken) {
      return;
    }

    const intervalId = window.setInterval(() => {
      void getPvpState(pvpGame.game_id, pvpPlayerToken)
        .then((state) => setPvpGame(state))
        .catch(() => {
          // Ignore transient polling errors.
        });
    }, 2000);

    return () => window.clearInterval(intervalId);
  }, [pvpGame, pvpPlayerToken]);

  const handleNewGame = useCallback(async () => {
    setError(null);
    setCompareResults(null);
    try {
      const resolvedColor = playerColor === "random"
        ? (Math.random() < 0.5 ? "white" : "black")
        : playerColor;
      const state = await newGame(selectedEngine, resolvedColor, getEngineOptions(selectedEngine));
      setEngineGame(state);
      setPvpGame(null);
      setPvpPlayerToken(null);
      setActiveMode("engine");
      setSelectedCompareMove(null);
      setShowCelebration(false);
      if (clockEnabled) {
        const initialMs = selectedClockPreset.baseSeconds * 1000;
        setClockState({
          whiteMs: initialMs,
          blackMs: initialMs,
          incrementMs: selectedClockPreset.incrementSeconds * 1000,
          flagged: null,
        });
      } else {
        setClockState(null);
      }
      previousMoveCountRef.current = state.move_history.length;
      previousTurnRef.current = state.turn;
      previousClockMoveCountRef.current = state.move_history.length;
      previousClockTurnRef.current = state.turn;
      previousStatusRef.current = state.status;
    } catch (reason: unknown) {
      setError(String(reason));
    }
  }, [clockEnabled, getEngineOptions, playerColor, selectedClockPreset, selectedEngine]);

  const handleCreatePvp = useCallback(async (playerName: string, preferredColor: "white" | "black" | "random") => {
    setPvpPending(true);
    setError(null);
    try {
      const result = await createPvpGame(playerName, preferredColor, accessToken ?? undefined);
      setPvpGame(result.state);
      setPvpPlayerToken(result.player_token);
      setEngineGame(null);
      setCompareResults(null);
      setActiveMode("pvp");
      setClockState(null);
      previousMoveCountRef.current = result.state.move_history.length;
      previousTurnRef.current = result.state.turn;
      previousClockMoveCountRef.current = result.state.move_history.length;
      previousClockTurnRef.current = result.state.turn;
      previousStatusRef.current = result.state.status;
    } catch (reason: unknown) {
      setError(String(reason));
    } finally {
      setPvpPending(false);
    }
  }, [accessToken]);

  const handleJoinPvp = useCallback(async (joinCode: string, playerName: string) => {
    setPvpPending(true);
    setError(null);
    try {
      const result = await joinPvpGame(joinCode, playerName, accessToken ?? undefined);
      setPvpGame(result.state);
      setPvpPlayerToken(result.player_token);
      setEngineGame(null);
      setCompareResults(null);
      setActiveMode("pvp");
      setClockState(null);
      previousMoveCountRef.current = result.state.move_history.length;
      previousTurnRef.current = result.state.turn;
      previousClockMoveCountRef.current = result.state.move_history.length;
      previousClockTurnRef.current = result.state.turn;
      previousStatusRef.current = result.state.status;
    } catch (reason: unknown) {
      setError(String(reason));
    } finally {
      setPvpPending(false);
    }
  }, [accessToken]);

  const handleLeavePvp = useCallback(() => {
    setPvpGame(null);
    setPvpPlayerToken(null);
    setActiveMode(startMode);
    setSelectedCompareMove(null);
  }, [startMode]);

  const handleReturnToStart = useCallback(() => {
    setStartMode(activeMode);
    setEngineGame(null);
    setPvpGame(null);
    setPvpPlayerToken(null);
    setClockState(null);
    setCompareResults(null);
    setSelectedCompareMove(null);
    setError(null);
    setThinking(false);
    moveInFlightRef.current = false;
    setShowCelebration(false);
  }, [activeMode]);

  const handleMove = useCallback(async (from: string, to: string, promotion?: string) => {
    if (!activeGame || thinking || moveInFlightRef.current) {
      return;
    }

    moveInFlightRef.current = true;
    setThinking(true);
    setError(null);
    let engineSnapshot: GameState | null = null;
    try {
      if (activeMode === "engine" && engineGame) {
        engineSnapshot = engineGame;
        const optimistic = optimisticEngineMove(engineSnapshot, from, to, promotion);
        if (optimistic) {
          setEngineGame(optimistic);
        }
        const state = await makeMove(engineGame.game_id, from, to, promotion);
        setEngineGame(state);
        setCompareResults(null);
        setSelectedCompareMove(null);
      } else if (activeMode === "pvp" && pvpGame && pvpPlayerToken) {
        const state = await makePvpMove(pvpGame.game_id, pvpPlayerToken, from, to, promotion);
        setPvpGame(state);
      }
    } catch (reason: unknown) {
      if (activeMode === "engine" && engineSnapshot) {
        setEngineGame(engineSnapshot);
      }
      const msg = (reason as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? String(reason));
    } finally {
      moveInFlightRef.current = false;
      setThinking(false);
    }
  }, [activeGame, activeMode, engineGame, pvpGame, pvpPlayerToken, thinking]);

  const handleSwitchEngine = useCallback(async (engineId: string) => {
    if (!engineGame) {
      return;
    }
    setSwitchPending(true);
    setError(null);
    try {
      const state = await switchEngine(engineGame.game_id, engineId, getEngineOptions(engineId));
      setEngineGame(state);
      setSelectedCompareMove(null);
      setSelectedEngine(engineId);
    } catch (reason: unknown) {
      setError(String(reason));
    } finally {
      setSwitchPending(false);
    }
  }, [engineGame, getEngineOptions]);

  const handleCompare = useCallback(async () => {
    if (!engineGame) {
      return;
    }
    setCompareLoading(true);
    setError(null);
    try {
      const results = await compareEngines(engineGame.game_id);
      setCompareResults(results);
      setSelectedCompareMove(null);
      setRightTab("compare");
    } catch (reason: unknown) {
      setError(String(reason));
    } finally {
      setCompareLoading(false);
    }
  }, [engineGame]);

  const handleRetryConnection = useCallback(async () => {
    setError(null);
    setBackendStatus("checking");
    await Promise.allSettled([loadHealth(), loadEngines(), loadAuthRuntimeConfig()]);
  }, [loadAuthRuntimeConfig, loadEngines, loadHealth]);

  const handleRequestMagicLink = useCallback(async (email: string, displayName?: string) => {
    setAuthPending(true);
    setError(null);
    try {
      return await requestMagicLink(email, displayName);
    } catch (reason: unknown) {
      setError(String(reason));
      throw reason;
    } finally {
      setAuthPending(false);
    }
  }, []);

  const handleVerifyMagicLink = useCallback(async (token: string) => {
    setAuthPending(true);
    setError(null);
    try {
      const session = await verifyMagicLink(token);
      persistSession(session);
      return session;
    } catch (reason: unknown) {
      setError(String(reason));
      throw reason;
    } finally {
      setAuthPending(false);
    }
  }, [persistSession]);

  const handleGoogleCredential = useCallback(async (googleToken: string) => {
    setAuthPending(true);
    setError(null);
    try {
      persistSession(await loginWithGoogle(googleToken));
    } catch (reason: unknown) {
      setError(String(reason));
      throw reason;
    } finally {
      setAuthPending(false);
    }
  }, [persistSession]);

  const handleLogout = useCallback(async () => {
    try {
      await logoutAuth(accessToken ?? undefined);
    } finally {
      clearSession();
    }
  }, [accessToken, clearSession]);

  const handleRunBenchmarks = useCallback(async (engineIds?: string[]) => {
    setBenchmarkLoading(true);
    setError(null);
    try {
      setLatestBenchmark(await runBenchmarks(engineIds, true));
      await loadToolingReports();
      setRightTab("tools");
    } catch (reason: unknown) {
      setError(String(reason));
    } finally {
      setBenchmarkLoading(false);
    }
  }, [loadToolingReports]);

  const handleBuildOpenings = useCallback(async (payload: {
    pgnText: string;
    maxPlies: number;
    minElo?: number;
    activate: boolean;
  }) => {
    setOpeningLoading(true);
    setError(null);
    try {
      setLastOpeningResult(await buildOpeningBook(payload));
      setRightTab("tools");
    } catch (reason: unknown) {
      setError(String(reason));
    } finally {
      setOpeningLoading(false);
    }
  }, []);

  const timeoutFlag = clockState?.flagged ?? null;

  const gameOver = activeGame
    ? activeGame.status.startsWith("checkmate") || activeGame.status.startsWith("draw")
    : false;
  const gameOverWithClock = gameOver || timeoutFlag !== null;
  const isMyTurn = activeGame
    ? activeGame.turn === activeGame.player_color && !gameOverWithClock && (!("waiting_for_opponent" in activeGame) || !activeGame.waiting_for_opponent)
    : false;
  const boardDisabled = !activeGame || !isMyTurn || thinking || gameOverWithClock;

  const lastMove = activeGame && activeGame.move_history.length > 0
    ? activeGame.move_history[activeGame.move_history.length - 1]
    : null;

  const parsedMoves = useMemo(() => {
    if (!activeGame) return [] as Array<{ uci: string; san: string; flags: string }>;
    const replay = new Chess();
    const results: Array<{ uci: string; san: string; flags: string }> = [];
    for (const uci of activeGame.move_history) {
      const from = uci.slice(0, 2);
      const to = uci.slice(2, 4);
      const promotion = uci.length > 4 ? uci[4] : undefined;
      const moved = replay.move({ from, to, promotion });
      if (!moved) {
        results.push({ uci, san: uci, flags: "" });
        continue;
      }
      results.push({ uci, san: moved.san, flags: moved.flags });
    }
    return results;
  }, [activeGame]);

  const moveNotationText = useMemo(() => {
    const rows: string[] = [];
    for (let i = 0; i < parsedMoves.length; i += 2) {
      const moveNo = Math.floor(i / 2) + 1;
      const white = parsedMoves[i]?.san ?? "";
      const black = parsedMoves[i + 1]?.san ?? "";
      rows.push(`${moveNo}. ${white}${black ? ` ${black}` : ""}`);
    }
    return rows.join("\n");
  }, [parsedMoves]);

  const handleCopyMoves = useCallback(async () => {
    if (!moveNotationText) return;
    try {
      await navigator.clipboard.writeText(moveNotationText);
      setCopyStatus("copied");
      window.setTimeout(() => setCopyStatus("idle"), 1200);
    } catch {
      setCopyStatus("failed");
      window.setTimeout(() => setCopyStatus("idle"), 1600);
    }
  }, [moveNotationText]);

  const handleCopyJoinCode = useCallback(async () => {
    if (!pvpGame?.join_code) return;
    try {
      await navigator.clipboard.writeText(pvpGame.join_code);
      setCopyStatus("copied");
      window.setTimeout(() => setCopyStatus("idle"), 1200);
    } catch {
      setCopyStatus("failed");
      window.setTimeout(() => setCopyStatus("idle"), 1600);
    }
  }, [pvpGame]);

  useEffect(() => {
    if (!activeGame) return;

    const currentCount = activeGame.move_history.length;
    const previousCount = previousMoveCountRef.current;

    if (currentCount > previousCount && parsedMoves.length > 0) {
      const latest = parsedMoves[parsedMoves.length - 1];
      if (activeGame.status.startsWith("checkmate")) {
        const winner = activeGame.status.split(":")[1];
        const didPlayerWin = winner === activeGame.player_color;
        void playSoundEvent(didPlayerWin ? "win" : "lose");
      } else if (activeGame.status === "check") {
        void playSoundEvent("check");
      } else if (latest.flags.includes("c") || latest.flags.includes("e")) {
        void playSoundEvent("capture");
      } else {
        void playSoundEvent("move");
      }
    }

    if (
      activeGame.status.startsWith("checkmate") &&
      previousStatusRef.current !== activeGame.status &&
      activeGame.status.split(":")[1] === activeGame.player_color
    ) {
      setShowCelebration(true);
      window.setTimeout(() => setShowCelebration(false), 3500);
    }

    previousMoveCountRef.current = currentCount;
    previousTurnRef.current = activeGame.turn;
    previousStatusRef.current = activeGame.status;
  }, [activeGame, parsedMoves, playSoundEvent]);

  useEffect(() => {
    if (!activeGame || !isEngineGame || gameOverWithClock || !clockEnabled) {
      return;
    }

    const intervalId = window.setInterval(() => {
      setClockState((previous) => {
        if (!previous || previous.flagged) {
          return previous;
        }
        const turn = activeGame.turn;
        if (turn === "white") {
          const nextWhite = previous.whiteMs - CLOCK_TICK_MS;
          if (nextWhite <= 0) {
            return { ...previous, whiteMs: 0, flagged: "white" };
          }
          return { ...previous, whiteMs: nextWhite };
        }

        const nextBlack = previous.blackMs - CLOCK_TICK_MS;
        if (nextBlack <= 0) {
          return { ...previous, blackMs: 0, flagged: "black" };
        }
        return { ...previous, blackMs: nextBlack };
      });
    }, CLOCK_TICK_MS);

    return () => window.clearInterval(intervalId);
  }, [activeGame, clockEnabled, gameOverWithClock, isEngineGame]);

  useEffect(() => {
    if (!clockState || !activeGame || !isEngineGame) {
      return;
    }

    const currentCount = activeGame.move_history.length;
    const previousCount = previousClockMoveCountRef.current;
    if (currentCount <= previousCount) {
      previousClockMoveCountRef.current = currentCount;
      previousClockTurnRef.current = activeGame.turn;
      return;
    }

    const movedPlies = currentCount - previousCount;
    const incrementMs = clockState.incrementMs;
    if (incrementMs <= 0) {
      return;
    }

    let mover: "white" | "black" = previousClockTurnRef.current;
    setClockState((previous) => {
      if (!previous || previous.flagged) {
        return previous;
      }
      const next = { ...previous };
      for (let i = 0; i < movedPlies; i += 1) {
        if (mover === "white") {
          next.whiteMs += incrementMs;
          mover = "black";
        } else {
          next.blackMs += incrementMs;
          mover = "white";
        }
      }
      return next;
    });
    previousClockMoveCountRef.current = currentCount;
    previousClockTurnRef.current = activeGame.turn;
  }, [activeGame, clockState, isEngineGame]);

  const statusLabel = (() => {
    if (!activeGame) return "";
    if (timeoutFlag) {
      return `Time out — ${timeoutFlag === "white" ? "Black" : "White"} wins!`;
    }
    if ("waiting_for_opponent" in activeGame && activeGame.waiting_for_opponent) {
      return `Waiting for opponent to join room ${activeGame.join_code}`;
    }
    if (activeGame.status === "ongoing") return isMyTurn ? "Your turn" : isEngineGame ? "Engine thinking…" : "Opponent turn";
    if (activeGame.status === "check") return isMyTurn ? "You are in check!" : "Other side is in check";
    if (activeGame.status.startsWith("checkmate:white")) return "Checkmate — White wins!";
    if (activeGame.status.startsWith("checkmate:black")) return "Checkmate — Black wins!";
    if (activeGame.status.startsWith("draw")) return `Draw (${activeGame.status.split(":")[1]})`;
    return activeGame.status;
  })();

  const modeTabs: Array<{ id: StartMode; label: string }> = [
    { id: "engine", label: "Play vs Engine" },
    { id: "pvp", label: "Play vs Player" },
  ];

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>♟ stockreptile</h1>
        <p>A chess teaching tool with swappable engines, PvP rooms, and training tools</p>
      </header>

      <div className={`health-banner health-banner-${backendStatus}`}>
        <span className="health-indicator" aria-hidden="true" />
        <span className="health-banner-text">
          {backendStatus === "online"
            ? `Backend connected: ${BASE_URL}`
            : backendStatus === "offline"
            ? `Backend unreachable: ${BASE_URL}`
            : `Checking backend: ${BASE_URL}`}
        </span>
        {authUser && <span className="pill">{authUser.display_name}</span>}
        {backendStatus !== "online" && (
          <button className="health-banner-button" onClick={() => void handleRetryConnection()}>
            Retry
          </button>
        )}
      </div>

      <main className="main-content">
        <section className="board-section">
          {!activeGame && (
            <div className="panel new-game-panel stack-md">
              <h2>Start a game</h2>
              <div className="segmented-toggle">
                {modeTabs.map((tab) => (
                  <button
                    key={tab.id}
                    className={`tab-btn ${startMode === tab.id ? "active" : ""}`}
                    onClick={() => setStartMode(tab.id)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {startMode === "engine" ? (
                <div className="new-game-controls">
                  <label>
                    Play as:
                    <select
                      value={playerColor}
                      onChange={(e) => setPlayerColor(e.target.value as "white" | "black" | "random")}
                    >
                      <option value="white">White</option>
                      <option value="black">Black</option>
                      <option value="random">Random</option>
                    </select>
                  </label>
                  <label className="check-label">
                    <input
                      type="checkbox"
                      checked={clockEnabled}
                      onChange={(e) => setClockEnabled(e.target.checked)}
                    />
                    <span>Enable chess clock</span>
                  </label>
                  {clockEnabled && (
                    <label>
                      Time control:
                      <select value={selectedClockPresetId} onChange={(e) => setSelectedClockPresetId(e.target.value)}>
                        <optgroup label="Bullet">
                          {CLOCK_PRESETS.filter((preset) => preset.category === "bullet").map((preset) => (
                            <option key={preset.id} value={preset.id}>Bullet {preset.label}</option>
                          ))}
                        </optgroup>
                        <optgroup label="Blitz">
                          {CLOCK_PRESETS.filter((preset) => preset.category === "blitz").map((preset) => (
                            <option key={preset.id} value={preset.id}>Blitz {preset.label}</option>
                          ))}
                        </optgroup>
                        <optgroup label="Rapid">
                          {CLOCK_PRESETS.filter((preset) => preset.category === "rapid").map((preset) => (
                            <option key={preset.id} value={preset.id}>Rapid {preset.label}</option>
                          ))}
                        </optgroup>
                      </select>
                    </label>
                  )}
                  {selectedEngine === "v1" && (
                    <label>
                      Greedy plies:
                      <select value={greedyPlies} onChange={(e) => setGreedyPlies(Number(e.target.value))}>
                        {Array.from({ length: 10 }, (_, i) => i + 1).map((depth) => (
                          <option key={depth} value={depth}>{depth}</option>
                        ))}
                      </select>
                    </label>
                  )}
                  <button className="btn btn-primary" onClick={() => void handleNewGame()} disabled={engines.length === 0}>
                    New Game
                  </button>
                </div>
              ) : (
                <PvPPanel user={authUser} pending={pvpPending} onCreate={handleCreatePvp} onJoin={handleJoinPvp} />
              )}
            </div>
          )}

          {activeGame && (
            <>
              <div className="status-bar">
                <span className={`status-label ${gameOverWithClock ? "game-over" : ""}`}>{statusLabel}</span>
                <div className="status-actions">
                  {isEngineGame ? (
                    <button className="btn btn-compare" onClick={() => void handleCompare()} disabled={gameOverWithClock || compareLoading}>
                      {compareLoading ? "…" : "Compare engines"}
                    </button>
                  ) : (
                    pvpGame?.join_code && (
                      <button className="btn btn-secondary" onClick={() => void handleCopyJoinCode()}>
                        {copyStatus === "copied" ? "Copied" : "Copy join code"}
                      </button>
                    )
                  )}
                  <button className="btn btn-secondary" onClick={isEngineGame ? handleReturnToStart : handleLeavePvp}>
                    {isEngineGame ? "New Game" : "Leave Room"}
                  </button>
                </div>
              </div>

              {clockState && isEngineGame && (
                <div className="clock-strip">
                  <div className={`clock-card ${activeGame.turn === "white" && !timeoutFlag ? "active" : ""}`}>
                    <span className="clock-name">White</span>
                    <span className="clock-time">{formatClock(clockState.whiteMs)}</span>
                  </div>
                  <div className={`clock-card ${activeGame.turn === "black" && !timeoutFlag ? "active" : ""}`}>
                    <span className="clock-name">Black</span>
                    <span className="clock-time">{formatClock(clockState.blackMs)}</span>
                  </div>
                </div>
              )}

              {pvpGame && (
                <div className="panel compact-panel stack-xs">
                  <div className="inline-actions">
                    <strong>Room {pvpGame.join_code}</strong>
                    <span className="muted">White: {pvpGame.players.white ?? "open"} | Black: {pvpGame.players.black ?? "open"}</span>
                  </div>
                </div>
              )}

              <Board
                fen={activeGame.fen}
                playerColor={(activeGame.player_color as "white" | "black") ?? "white"}
                legalMoves={isMyTurn ? activeGame.legal_moves : []}
                onMove={handleMove}
                disabled={boardDisabled}
                lastMove={lastMove}
                highlightedMove={selectedCompareMove}
              />

              <div className="move-history">
                <div className="move-history-header">
                  <strong>Move notation (SAN)</strong>
                  <button className="btn btn-secondary" onClick={() => void handleCopyMoves()} disabled={!moveNotationText}>
                    {copyStatus === "copied" ? "Copied" : copyStatus === "failed" ? "Copy failed" : "Copy PGN moves"}
                  </button>
                </div>
                <pre className="move-history-text">{moveNotationText || "No moves yet."}</pre>
              </div>
            </>
          )}

          {error && <p className="error-msg">{error}</p>}
        </section>

        <aside className="right-panel">
          <div className="tabs">
            {(["engine", "compare", "training", "tools", "account"] as RightTab[]).map((tab) => (
              <button
                key={tab}
                className={`tab-btn ${rightTab === tab ? "active" : ""}`}
                onClick={() => setRightTab(tab)}
              >
                {tab === "engine"
                  ? "Engine"
                  : tab === "compare"
                  ? "Compare"
                  : tab === "training"
                  ? "Training"
                  : tab === "tools"
                  ? "Tools"
                  : "Account"}
              </button>
            ))}
          </div>

          {rightTab === "engine" && (
            <EngineSelector
              engines={engines}
              selectedId={engineGame?.engine_id ?? selectedEngine}
              onChange={setSelectedEngine}
              onSwitch={handleSwitchEngine}
              greedyPlies={greedyPlies}
              onGreedyPliesChange={setGreedyPlies}
              v4Options={v4Options}
              onV4OptionsChange={setV4Options}
              gameActive={!!engineGame && activeMode === "engine" && !gameOverWithClock}
              pendingSwitch={switchPending}
            />
          )}

          {rightTab === "compare" && (
            <EngineComparison
              results={compareResults}
              loading={compareLoading}
              onCompare={handleCompare}
              gameActive={!!engineGame && activeMode === "engine" && !gameOverWithClock}
              selectedMove={selectedCompareMove}
              onSelectMove={setSelectedCompareMove}
            />
          )}

          {rightTab === "training" && <TrainingPanel />}

          {rightTab === "tools" && (
            <ToolingPanel
              latestBenchmark={latestBenchmark}
              benchmarkHistory={benchmarkHistory}
              benchmarkLoading={benchmarkLoading}
              openingLoading={openingLoading}
              lastOpeningResult={lastOpeningResult}
              onRunBenchmarks={handleRunBenchmarks}
              onBuildOpenings={handleBuildOpenings}
            />
          )}

          {rightTab === "account" && (
            <AuthPanel
              config={authConfig}
              user={authUser}
              pending={authPending}
              onRequestMagicLink={handleRequestMagicLink}
              onVerifyMagicLink={handleVerifyMagicLink}
              onGoogleCredential={handleGoogleCredential}
              onLogout={handleLogout}
            />
          )}
        </aside>
      </main>

      {showCelebration && (
        <div className="celebration-overlay" aria-hidden="true">
          {Array.from({ length: 24 }, (_, i) => (
            <span
              key={i}
              className="confetti"
              style={{ "--x": `${(i * 4.1) % 100}%`, "--delay": `${(i % 8) * 0.09}s` } as CSSProperties}
            />
          ))}
        </div>
      )}
    </div>
  );
}
