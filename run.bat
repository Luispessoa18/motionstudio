@echo off
rem Sobe o Motion Studio em http://localhost:8000 (versao Windows do run.sh)
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo Criando ambiente virtual e instalando dependencias...
  python -m venv .venv || goto :erro
  .venv\Scripts\python -m pip install -r requirements.txt || goto :erro
  .venv\Scripts\python -m playwright install chromium || goto :erro
)

if "%HOST%"=="" set HOST=0.0.0.0
if "%PORT%"=="" set PORT=8000

echo Motion Studio em http://localhost:%PORT%
.venv\Scripts\python -m uvicorn app.main:app --host %HOST% --port %PORT%
goto :eof

:erro
echo Falha ao preparar o ambiente. Confira se o Python 3.12 esta instalado e no PATH.
pause
exit /b 1
