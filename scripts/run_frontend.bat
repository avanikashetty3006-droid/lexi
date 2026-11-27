@echo off
REM Starts the Lexi frontend on http://localhost:5173
cd /d "%~dp0..\frontend"
call npm install
call npm run dev
