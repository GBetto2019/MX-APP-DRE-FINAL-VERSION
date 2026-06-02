@echo off
chcp 65001 > nul

echo Iniciando MX DRE-IA...
echo.

:: Backend FastAPI na porta 8000
echo [1/2] Subindo Backend (FastAPI)...
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
start "DRE Backend - porta 8000" cmd /k "cd /d %~dp0 && python -m uvicorn app.main:app --reload --port 8000"

:: Aguarda 3 segundos antes de subir o frontend
timeout /t 3 /nobreak > nul

:: Frontend Next.js na porta 3000
echo [2/2] Subindo Frontend (Next.js)...
start "DRE Frontend - porta 3000" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Aguardando servidores iniciarem...
timeout /t 8 /nobreak > nul

echo.
echo ============================================
echo  Acesse:
echo  Frontend: http://localhost:3000
echo  API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo Feche as outras janelas para parar os servidores.
pause
