@echo off
title AirControl - Gesture Config Launcher
echo Starting AirControl gesture config website...
echo.

REM --- Start backend (Express) in its own window ---
if not exist "gesture-config-web\server\node_modules" (
    echo Installing backend dependencies for the first time, this may take a minute...
    pushd gesture-config-web\server
    call npm install
    popd
)
start "AirControl Backend" cmd /k "cd gesture-config-web\server && npm start"

REM --- Start frontend (Vite) in its own window ---
if not exist "gesture-config-web\client\node_modules" (
    echo Installing frontend dependencies for the first time, this may take a minute...
    pushd gesture-config-web\client
    call npm install
    popd
)
start "AirControl Frontend" cmd /k "cd gesture-config-web\client && npm run dev"

REM --- Give both servers a few seconds to boot, then open the browser ---
echo Waiting for servers to start...
timeout /t 6 /nobreak > nul
start http://localhost:5173

echo.
echo Two new windows opened: one for the backend, one for the frontend.
echo Leave both open while you use the site. Close this window any time.
pause
