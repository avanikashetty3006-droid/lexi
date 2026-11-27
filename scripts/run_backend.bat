@echo off
REM Starts the Lexi backend on http://localhost:8000 (needs .env with an API key in the repo root)
cd /d "%~dp0..\backend"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
