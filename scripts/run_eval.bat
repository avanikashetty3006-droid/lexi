@echo off
REM Full evaluation. The backend must already be running (scripts\run_backend.bat).
REM Order matters: dev run -> tune on dev -> test run. Test is never used for tuning.
cd /d "%~dp0.."
call backend\.venv\Scripts\activate.bat
pip install -q -r evaluation\requirements.txt
python evaluation\validate_dataset.py || goto :end
python evaluation\run_eval.py --split dev || goto :end
python evaluation\baseline_eval.py --split dev || goto :end
python evaluation\tune_threshold.py || goto :end
python evaluation\run_eval.py --split test || goto :end
python evaluation\baseline_eval.py --split test || goto :end
echo.
echo Done. Open the dashboard with scripts\run_dashboard.bat
:end
