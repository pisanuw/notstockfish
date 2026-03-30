# Student Guide — stockreptile

Each engine lives in its own file under `backend/engines/`.
Complete the `TODO` sections in order: v1 → v2 → v3 → v4.

The app will automatically detect which engines are working and show them in the UI.
If your engine raises `NotImplementedError`, it appears greyed-out in the comparison panel — no other files need to be touched.

---

## Running the app locally

```bash
# Terminal 1 – backend
cd backend
source .venv/bin/activate       # or .venv\Scripts\activate on Windows
uvicorn main:app --reload --port 8000

# Terminal 2 – frontend
cd frontend
npm run dev
# Open http://localhost:5173
```

Run the test suite at any time:
```bash
cd backend && pytest tests/ -v
```

---

## v1 — Greedy 1-ply (`engines/v1_search.py`)

The engine evaluates every legal move by looking **one ply ahead** (no recursion) and picks the best.

**TODO 1 – `_piece_value(piece_type)`**
Return a numeric value for each piece type using the `PIECE_VALUES` dict already defined in the file.

**TODO 2 – `evaluate(board)`**
Sum the material for White, subtract the material for Black.
Positive = White is ahead; negative = Black is ahead.
Hint: iterate `board.piece_map()` and use `_piece_value`.

**TODO 3 – `get_move(board)`**
Loop over `board.legal_moves`. For each move:
1. Push the move onto a copy of the board (`board.push` / `board.copy()`).
2. Call `evaluate` on the resulting position.
3. Pop the move back.

Return the move with the best score from the engine's perspective (maximise if White to move, minimise if Black).

---

## v2 — Minimax + Alpha-Beta (`engines/v2_minimax.py`)

The piece-square tables and `evaluate()` are already implemented.

**TODO 1 – `_minimax(board, depth, alpha, beta, maximising)`**
Classic negamax / minimax with alpha-beta pruning.

```
if depth == 0 or game over:
    return evaluate(board)
if maximising:
    value = -∞
    for move in legal_moves:
        push move
        value = max(value, _minimax(board, depth-1, alpha, beta, False))
        pop move
        alpha = max(alpha, value)
        if alpha >= beta: break   # β cutoff
    return value
else:
    # symmetric for minimising player
```

**TODO 2 – `get_move(board)`**
Call `_minimax` on each legal move (start at `self.depth`) and return the move that produced the best value.
Remember: the engine plays White if `board.turn == chess.WHITE`.

---

## v3 — Q-Learning (`engines/v3_qlearning.py`)

**TODO 1 – `_state_key(board)`**
Return a hashable string that uniquely identifies the board position.
`board.fen()` is an easy choice; a compact piece-map string is faster at scale.

**TODO 2 – `_reward(board, move)`**
Push the move, compute a reward, pop it.
Simple reward ideas:
- +1 for checkmate, -1 for being mated
- Capture value (value of captured piece)
- Stalemate → 0

**TODO 3 – `update(state_key, action_key, reward, next_state_key)`**
Standard Q-learning update:

$$Q(s,a) \leftarrow Q(s,a) + \alpha \bigl[r + \gamma \max_{a'} Q(s',a') - Q(s,a)\bigr]$$

Where `alpha=self.alpha`, `gamma=self.gamma`.
Store Q-values in `self.q_table[state_key][action_key]`.

**TODO 4 – `get_move(board)`**
ε-greedy selection:
- With probability `self.epsilon`, pick a random legal move (explore).
- Otherwise, pick the move whose Q-value is highest for the current state (exploit).
- If no Q-values exist for this state, fall back to random.

The WebSocket training endpoint (`/api/train/qlearning`) calls `update()` automatically during self-play — you just need `get_move()` to work for inference.

---

## v4 — Opening Book + Fallback (`engines/v4_openings.py`)

**TODO 1 – `_load_book(path)`**
Read `backend/data/openings.json`.
Expected format:
```json
{
  "<fen_key>": [
    {"move": "e2e4", "weight": 10},
    {"move": "d2d4", "weight": 8}
  ]
}
```
Return the dict (or `{}` if the file doesn't exist).
A FEN key can be the first two fields of `board.fen()` (position + side-to-move) to ignore clocks.

**TODO 2 – `_book_move(board)`**
Look up `self._book_key(board)` in `self.book`.
If found, pick a move weighted by the `"weight"` field (`random.choices` is handy).
Validate that the chosen move is legal before returning it; return `None` if nothing matches.

**TODO 3 – `get_move(board)`**
```python
move = self._book_move(board)
if move is not None:
    return move
return self._fallback.get_move(board)   # MinimaxEngine
```

---

## Tips and gotchas

- **Never modify `base.py` or `__init__.py`** unless you're adding a brand-new engine version.
- `board.push(move)` **mutates** the board in place. Always `board.pop()` or use `board.copy()`.
- Return `chess.Move` objects, not strings. Use `chess.Move.from_uci("e2e4")` to convert.
- Engines that raise `NotImplementedError` from `get_move()` are silently excluded from comparisons — the app won't crash.
- Run `pytest tests/ -v` often; the parametrized tests will exercise your engine automatically once it's detected as implemented.
