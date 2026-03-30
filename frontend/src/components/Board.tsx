/**
 * Board component.
 *
 * Wraps react-chessboard (v4+) and handles click-to-move, drag-and-drop,
 * legal-move highlighting, last-move highlighting, and pawn promotion.
 *
 * react-chessboard v4 uses a single `options` prop object.
 */

import { useState, useCallback, type CSSProperties } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";
import type { Square } from "chess.js";

interface BoardProps {
  fen: string;
  playerColor: "white" | "black";
  legalMoves: string[];         // UCI strings from backend, e.g. ["e2e4", ...]
  onMove: (from: string, to: string, promotion?: string) => void;
  disabled?: boolean;
  lastMove?: string | null;     // UCI of the last move played, for highlighting
  highlightedMove?: string | null; // optional preview move highlight from compare panel
}

export default function Board({
  fen,
  playerColor,
  legalMoves,
  onMove,
  disabled = false,
  lastMove,
  highlightedMove,
}: BoardProps) {
  const [selectedSquare, setSelectedSquare] = useState<Square | null>(null);
  const [promotionDialog, setPromotionDialog] = useState<{
    from: Square;
    to: Square;
  } | null>(null);

  const legalDests = useCallback(
    (from: Square): Square[] =>
      legalMoves
        .filter((uci) => uci.startsWith(from))
        .map((uci) => uci.slice(2, 4) as Square),
    [legalMoves]
  );

  // Build square highlight styles
  const squareStyles: Record<string, CSSProperties> = {};

  if (lastMove && lastMove.length >= 4) {
    const from = lastMove.slice(0, 2);
    const to = lastMove.slice(2, 4);
    squareStyles[from] = { backgroundColor: "rgba(255, 213, 79, 0.5)" };
    squareStyles[to] = { backgroundColor: "rgba(255, 213, 79, 0.5)" };
  }

  if (highlightedMove && highlightedMove.length >= 4) {
    const from = highlightedMove.slice(0, 2);
    const to = highlightedMove.slice(2, 4);
    squareStyles[from] = {
      ...squareStyles[from],
      outline: "2px solid rgba(25, 118, 210, 0.85)",
      outlineOffset: "-2px",
    };
    squareStyles[to] = {
      ...squareStyles[to],
      backgroundColor: "rgba(25, 118, 210, 0.34)",
      outline: "2px solid rgba(25, 118, 210, 0.85)",
      outlineOffset: "-2px",
    };
  }

  if (selectedSquare) {
    squareStyles[selectedSquare] = { backgroundColor: "rgba(20, 85, 30, 0.4)" };
    legalDests(selectedSquare).forEach((sq) => {
      squareStyles[sq] = {
        background: "radial-gradient(circle, rgba(0,0,0,.18) 30%, transparent 30%)",
        borderRadius: "50%",
      };
    });
  }

  function isPawnPromotion(from: Square, to: Square): boolean {
    const chess = new Chess(fen);
    const piece = chess.get(from);
    if (!piece || piece.type !== "p") return false;
    return (piece.color === "w" && to[1] === "8") ||
           (piece.color === "b" && to[1] === "1");
  }

  function handleSquareClick({ square }: { piece: unknown; square: string }) {
    if (disabled) return;
    const sq = square as Square;

    if (selectedSquare === null) {
      const chess = new Chess(fen);
      const piece = chess.get(sq);
      const ourColor = playerColor === "white" ? "w" : "b";
      if (piece && piece.color === ourColor) setSelectedSquare(sq);
      return;
    }

    if (sq === selectedSquare) { setSelectedSquare(null); return; }

    const dests = legalDests(selectedSquare);
    if (dests.includes(sq)) {
      if (isPawnPromotion(selectedSquare, sq)) {
        setPromotionDialog({ from: selectedSquare, to: sq });
        setSelectedSquare(null);
        return;
      }
      onMove(selectedSquare, sq);
      setSelectedSquare(null);
    } else {
      const chess = new Chess(fen);
      const piece = chess.get(sq);
      const ourColor = playerColor === "white" ? "w" : "b";
      setSelectedSquare(piece && piece.color === ourColor ? sq : null);
    }
  }

  function handlePieceDrop({
    sourceSquare,
    targetSquare,
  }: {
    piece: unknown;
    sourceSquare: string;
    targetSquare: string | null;
  }): boolean {
    if (disabled || !targetSquare) return false;
    const src = sourceSquare as Square;
    const tgt = targetSquare as Square;
    const dests = legalDests(src);
    if (!dests.includes(tgt)) return false;
    if (isPawnPromotion(src, tgt)) {
      setPromotionDialog({ from: src, to: tgt });
      return true;
    }
    onMove(src, tgt);
    setSelectedSquare(null);
    return true;
  }

  function handlePromotion(piece: string) {
    if (!promotionDialog) return;
    onMove(promotionDialog.from, promotionDialog.to, piece);
    setPromotionDialog(null);
  }

  return (
    <div style={{ position: "relative", width: "100%", maxWidth: 560 }}>
      <Chessboard
        options={{
          position: fen,
          boardOrientation: playerColor,
          onSquareClick: handleSquareClick,
          onPieceDrop: handlePieceDrop,
          squareStyles,
          allowDragging: !disabled,
          animationDurationInMs: 150,
        }}
      />

      {promotionDialog && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "rgba(0,0,0,0.6)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 12,
            zIndex: 10,
          }}
        >
          <p style={{ color: "#fff", fontWeight: 600 }}>Promote pawn to:</p>
          <div style={{ display: "flex", gap: 12 }}>
            {["q", "r", "b", "n"].map((p) => (
              <button
                key={p}
                onClick={() => handlePromotion(p)}
                style={{ fontSize: 28, padding: "8px 14px", borderRadius: 8, cursor: "pointer", background: "#fff", border: "2px solid #555" }}
              >
                {{ q: "♛", r: "♜", b: "♝", n: "♞" }[p]}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
