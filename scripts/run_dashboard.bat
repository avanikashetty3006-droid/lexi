@echo off
cd /d "%~dp0.."
call backend\.venv\Scripts\activate.bat
streamlit run evaluation\dashboard\app.py
