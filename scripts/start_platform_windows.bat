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
if defined STRATEGY_STUDIO_PROXY (
    set "SCHEDULER_ARGS=--proxy %STRATEGY_STUDIO_PROXY%"
)

echo 正在启动平台前后端进程...
echo API: %API_BASE_URL%
echo Frontend: http://%FRONTEND_HOST%:%FRONTEND_PORT%

py -3.13 -c "import uvicorn, fastapi, sqlalchemy, psycopg" >nul 2>nul
if errorlevel 1 (
    echo 后端 Python 依赖未安装完成。
    echo 请先执行: py -3.13 -m pip install -r requirements.txt
    exit /b 1
)

netstat -ano | findstr /R /C:":%FRONTEND_PORT% .*LISTENING" >nul
if not errorlevel 1 (
    echo 前端端口 %FRONTEND_PORT% 已被占用，请先关闭已有前端进程后再执行本脚本。
    exit /b 1
)

start "Strategy Studio API" cmd /k "cd /d ""%ROOT_DIR%"" && py -3.13 main.py api --host %API_HOST% --port %API_PORT% --replace-existing"
start "Strategy Studio Worker" cmd /k "cd /d ""%ROOT_DIR%"" && py -3.13 main.py worker --poll-interval 5"
start "Strategy Studio Scheduler" cmd /k "cd /d ""%ROOT_DIR%"" && py -3.13 main.py scheduler %SCHEDULER_ARGS%"
start "Strategy Studio Frontend" cmd /k "cd /d ""%ROOT_DIR%\frontend"" && set NEXT_PUBLIC_API_BASE_URL=%API_BASE_URL% && npx next dev --hostname %FRONTEND_HOST% --port %FRONTEND_PORT%"

echo 已发起 4 个窗口：API、Worker、Scheduler、Frontend。
endlocal
