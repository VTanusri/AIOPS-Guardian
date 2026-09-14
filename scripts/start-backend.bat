@echo off
cd /d "%~dp0..\backend"
set PYTHONPATH=.
set LLM_PROVIDER=auto
".venv\Scripts\uvicorn.exe" app.main:app --reload --host 127.0.0.1 --port 8000
