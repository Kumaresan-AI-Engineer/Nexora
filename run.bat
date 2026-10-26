@echo off
setlocal
cd /d "%~dp0"
title PharmaSource launcher

echo ==============================================
echo   PharmaSource - starting backend + frontend
echo ==============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python 3.11+ was not found on PATH. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js 20+ was not found on PATH. Install it from https://nodejs.org/
  pause
  exit /b 1
)

rem --- Backend environment -------------------------------------------------------
if not exist "backend\.venv\Scripts\python.exe" (
  echo [1/5] Creating Python virtual environment...
  python -m venv backend\.venv
  if errorlevel 1 (
    echo [ERROR] Could not create the virtual environment.
    pause
    exit /b 1
  )
)

if not exist "backend\.venv\.deps_installed" (
  echo [2/5] Installing backend dependencies - first run only, may take a few minutes...
  backend\.venv\Scripts\python -m pip install -q --disable-pip-version-check -r backend\requirements.txt
  if errorlevel 1 (
    echo [ERROR] Backend dependency install failed.
    pause
    exit /b 1
  )
  echo ok> "backend\.venv\.deps_installed"
)

if not exist "backend\.env" (
  echo [3/5] Creating backend\.env with local defaults - SQLite database and demo mode on
  copy "backend\.env.example" "backend\.env" >nul
  powershell -NoProfile -Command "(Get-Content 'backend\.env') -replace '^DATABASE_URL=.*','DATABASE_URL=sqlite:///./pharmasource.db' -replace '^DEMO_MODE=.*','DEMO_MODE=true' | Set-Content 'backend\.env'"
  echo       Edit backend\.env to add OPENAI_API_KEY / GEMINI_API_KEY and model names, or TAVILY_API_KEY.
)

rem --- Database ------------------------------------------------------------------
echo [4/5] Applying database migrations...
pushd backend
.venv\Scripts\python -m alembic upgrade head
if errorlevel 1 (
  popd
  echo [ERROR] Database migration failed. Check DATABASE_URL in backend\.env
  pause
  exit /b 1
)
popd

rem --- Frontend dependencies -----------------------------------------------------
if not exist "frontend\node_modules" (
  echo [5/5] Installing frontend dependencies - first run only...
  pushd frontend
  call npm install
  if errorlevel 1 (
    popd
    echo [ERROR] npm install failed.
    pause
    exit /b 1
  )
  popd
)

rem --- Launch --------------------------------------------------------------------
rem Clear Vite's dependency pre-bundle cache so a stale cache can never cause "Invalid hook call".
if exist "frontend\node_modules\.vite\deps" rmdir /s /q "frontend\node_modules\.vite\deps"

echo Starting API on http://localhost:8000 and web app on http://localhost:5173
start "PharmaSource API" cmd /k "cd /d %~dp0backend && .venv\Scripts\python -m uvicorn app.main:app_factory --factory --reload --port 8000"
start "PharmaSource Web" cmd /k "cd /d %~dp0frontend && npm run dev -- --port 5173"

ping -n 8 127.0.0.1 >nul
if not defined NOBROWSER start "" http://localhost:5173

echo.
echo Both servers are running in their own windows. Close those windows to stop them.
endlocal
