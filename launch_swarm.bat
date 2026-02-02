@echo off
SETLOCAL EnableDelayedExpansion

TITLE Home AI Lab - Swarm Launcher

echo ==================================================
echo    INITIALIZING HOME AI LAB SWARM
echo ==================================================
echo.

:: 1. Check Docker
echo 🔍 Checking Docker status...
docker info >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo    [ERROR] Docker is NOT running. Please start Docker Desktop.
    pause
    exit /b 1
)
echo    [OK] Docker is running.

:: 2. Paths
SET "ROOT=%~dp0"
SET "EXEC_PLANE=%ROOT%execution_plane"

IF NOT EXIST "%EXEC_PLANE%" (
    echo    [ERROR] execution_plane directory not found at %EXEC_PLANE%
    pause
    exit /b 1
)

:: 3. Deploy
pushd "%EXEC_PLANE%"
echo ==================================================
echo    DEPLOYING EXECUTION PLANE
echo ==================================================

echo 📉 Stopping existing services...
docker compose down --remove-orphans

echo 🏗️  Rebuilding Swarm Infrastructure...
docker compose up -d --build

IF %ERRORLEVEL% NEQ 0 (
    echo    [ERROR] Deployment Failed.
    popd
    pause
    exit /b 1
)
popd

:: 4. Launch ComfyUI
echo ==================================================
echo    LAUNCHING COMFYUI (Creature Forge)
echo ==================================================
SET "COMFY_DIR=C:\Users\panca\Documents\GitHub\Creature_Forge"
SET "COMFY_BAT=start_unified_nightly.bat"

IF EXIST "%COMFY_DIR%\%COMFY_BAT%" (
    echo 🎨 Starting ComfyUI via Creature Forge...
    echo    [NOTE] Switching to Creature Forge directory...
    pushd "%COMFY_DIR%"
    :: Assuming custom script handles args, but appending --listen just in case it passes them through
    start /min "ComfyUI" "%COMFY_BAT%" --listen
    popd
    echo    [OK] ComfyUI started in background.
) ELSE (
    echo    [WARN] Launch script not found at %COMFY_DIR%\%COMFY_BAT%
    echo           Please ensure ComfyUI is running manually.
)

:: 5. Health Check
echo ==================================================
echo    SYSTEM CHECKS
echo ==================================================
echo ⏳ Giving services 10 seconds to warm up...
timeout /t 10 /nobreak >nul

:: Check Brain IP
SET "BRAIN_IP=192.168.1.211"
ping -n 1 %BRAIN_IP% >nul 2>&1
IF %ERRORLEVEL% EQU 0 (
    echo    [OK] Control Plane ^(%BRAIN_IP%^) is Reachable.
) ELSE (
    echo    [WARN] Control Plane ^(%BRAIN_IP%^) is UNREACHABLE.
    echo           Long-term memory features may be disabled.
)

:: 6. Finish
echo ==================================================
echo    MISSION CONTROL ONLINE
echo ==================================================
echo ✅ Swarm is ready.
echo.
echo Dashboard URLs:
echo    🖥️  Agent UI:        http://localhost:8501
echo    📊 Mission Control: http://localhost:80/d/mission-control-uid
echo    🔧 API Metrics:     http://localhost:8000/metrics
echo.

:: Auto-Open
start "" "http://localhost:8501"
start "" "http://localhost:80/d/mission-control-uid"

echo.
echo ==================================================
echo    RUNNING - PRESS 'Q' TO STOP ALL SYSTEMS
echo ==================================================
:loop
choice /c q /n /m "Press 'Q' to shutdown swarm and forge >"
if errorlevel 1 goto shutdown
goto loop

:shutdown
echo.
echo 🛑 Shutting down Creature Forge...
taskkill /FI "WINDOWTITLE eq Creature Forge Unified*" /T /F >nul 2>&1

echo 🛑 Shutting down Swarm Containers...
pushd "%EXEC_PLANE%"
docker compose down
popd

echo ✅ All systems offline.
timeout /t 3
exit
