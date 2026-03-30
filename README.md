# stockreptile ♟

A chess-playing web app designed as a **teaching tool** for AI/algorithms courses.
Play against progressively smarter engines (v0–v4) and compare what each version
recommends at any point in the game.

## Architecture

```
stockreptile/
├── backend/               Python / FastAPI
│   ├── engines/           One file per engine version
│   │   ├── base.py        ChessEngine abstract base class
│   │   ├── v0_random.py   ✅ Random legal move
│   │   ├── v1_search.py   🔧 Greedy 1-ply + material eval  (TODOs for students)
│   │   ├── v2_minimax.py  🔧 Minimax + alpha-beta pruning  (TODOs for students)
│   │   ├── v3_qlearning.py🔧 Q-learning self-play          (TODOs for students)
│   │   └── v4_openings.py 🔧 Opening book + v2 fallback   (TODOs for students)
│   ├── game.py            Game session management
│   ├── main.py            FastAPI app + WebSocket training endpoint
│   └── tests/             pytest suite (69 tests)
└── frontend/              React + TypeScript + Vite
	└── src/
		├── components/
		│   ├── Board.tsx
		│   ├── EngineSelector.tsx
		│   ├── EngineComparison.tsx
		│   └── TrainingPanel.tsx
		└── services/api.ts
```

## Quick Start

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
```

### Environment Setup

Use the template at `.env.example` and copy values into local env files.

```bash
# from repo root
cp .env.example .env
cp .env.example backend/.env
cp .env.example frontend/.env
```

Variable guide:
- `GOOGLE_CLIENT_ID`: enables Google sign-in (backend validation + frontend account panel visibility).
- `VITE_API_URL`: sets the frontend API target; if empty, frontend auto-detects local backend.
- `VITE_GOOGLE_CLIENT_ID`: optional compatibility fallback read by backend if `GOOGLE_CLIENT_ID` is unset.

Security note:
- Keep real `.env` files local only. They are ignored by git; commit only `.env.example`.

### Tests
```bash
cd backend && source .venv/bin/activate
pytest tests/ -v
```

### Engine Tooling
```bash
cd backend
source .venv/bin/activate

# Build weighted opening JSON from PGN data
python scripts/build_openings_json.py \
	--pgn /path/to/games.pgn \
	--output data/openings.generated.json \
	--polyglot-output data/openings.generated.bin \
	--max-games 20000 \
	--max-plies 16 \
	--min-elo 1800

# Benchmark implemented engines on a fixed FEN suite
python scripts/benchmark_engines.py \
	--output-json data/benchmarks/latest.json \
	--history-jsonl data/benchmarks/history.jsonl
```

Notes:
- The generated JSON uses FEN-prefix to weighted UCI moves and can be used directly by v4.
- The same build script can also emit a Polyglot `.bin` book for direct v4 consumption.
- Polyglot `.bin` books are now supported by v4 when provided via engine options (`book_path`) or when available at `backend/data/openings.bin`.
- Benchmarks can be persisted as a latest JSON snapshot and/or appended to a JSONL history for regression tracking.

### In-App Features
- Account tab: optional magic-link sign-in and Google sign-in when `GOOGLE_CLIENT_ID` is configured.
- PvP mode: create or join a two-player room with a shareable join code.
- Engine tab: v1 plies control and v4 opening-book controls for fallback depth, minimum weight, weighted selection, and custom book path.
- Tools tab: run engine benchmarks from the UI and build opening books from pasted PGN without using the CLI scripts directly.

## Engine versions

| Version | Name | Status | Concepts |
|---------|------|--------|----------|
| v0 | Random Mover | ✅ Complete | Baseline |
| v1 | Greedy 1-ply | 🔧 Student TODO | Evaluation, 1-ply search |
| v2 | Minimax + Alpha-Beta | 🔧 Student TODO | Game trees, pruning, PST |
| v3 | Q-Learning | 🔧 Student TODO | RL, Q-table, ε-greedy |
| v4 | Opening Book + Minimax | 🔧 Student TODO | Databases, hybrid strategies |

## For students: see [STUDENT_GUIDE.md](STUDENT_GUIDE.md)

## Search Notes

The current v2 search now layers several practical search improvements on top of the earlier evaluator work:
- Iterative deepening at the root
- Quiescence search at leaf nodes
- Transposition-table reuse across the current search
- Tactical move ordering for stronger alpha-beta pruning