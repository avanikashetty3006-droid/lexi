# Lexi

An ambiguity-aware chatbot. It asks instead of guessing, and shows why.
Resurrect 2026: problem 6 (ambiguity), with human-agent interaction (3) and a lite meaning-map visualizer (5).

## Run it (Windows, Command Prompt)
1. Copy `.env.example` to `.env` in the repo root and put your API key in it. Never commit `.env`.
2. Backend:  `scripts\run_backend.bat`   (http://localhost:8000, check `/health`)
3. Frontend: `scripts\run_frontend.bat`  (http://localhost:5173). In `frontend\.env` set `VITE_USE_MOCK=false` to use the real backend.

## Run the evaluation
With the backend running: `scripts\run_eval.bat`, then `scripts\run_dashboard.bat`.
Rules: tune the threshold on **dev** only, run **test** once, and report only numbers the scripts computed.
After a run, fill the human columns in `evaluation\results\*_review.csv` and re-score with
`python evaluation\run_eval.py --split test --rescore`.

## Layout
- `backend/`: engine (FastAPI). `frontend/`: chat UI (React). `evaluation/`: dataset, metrics, dashboard, study.
- `docs/`: `contract.md` (API), `report.md`, `user-study.md`, `demo-script.md`.

## Team rules
Each person works only in their own folder and branch (`engine`, `app`, `eval`). Merge to `main` by pull request at hours 6, 12 and 18. The API contract changes only after telling the team.
