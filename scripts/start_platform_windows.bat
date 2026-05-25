@echo off
setlocal

set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

set "API_HOST=127.0.0.1"
set "API_PORT=8000"
set "FRONTEND_HOST=127.0.0.1"
set "FRONTEND_PORT=3000"
set "API_BASE_URL=http://%API_HOST%:%API_PORT%"

set "SCHEDULER_ARGS="
if defined ETF_STRATEGY_PROXY (
    set "SCHEDULER_ARGS=--proxy %ETF_STRATEGY_PROXY%"
)

echo 正在启动平台前后端进程...
echo API: %API_BASE_URL%
echo Frontend: http://%FRONTEND_HOST%:%FRONTEND_PORT%

start "ETF Strategy API" cmd /k "cd /d ""%ROOT_DIR%"" && py -3.13 main.py api --host %API_HOST% --port %API_PORT%"
start "ETF Strategy Worker" cmd /k "cd /d ""%ROOT_DIR%"" && py -3.13 main.py worker --poll-interval 5"
start "ETF Strategy Scheduler" cmd /k "cd /d ""%ROOT_DIR%"" && py -3.13 main.py scheduler %SCHEDULER_ARGS%"
start "ETF Strategy Frontend" cmd /k "cd /d ""%ROOT_DIR%\frontend"" && set NEXT_PUBLIC_API_BASE_URL=%API_BASE_URL% && npm run dev -- --hostname %FRONTEND_HOST% --port %FRONTEND_PORT%"

echo 已发起 4 个窗口：API、Worker、Scheduler、Frontend。
endlocal
