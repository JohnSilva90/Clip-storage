@echo off
REM ===== Clip Storage: liga o servidor no Windows =====
chcp 65001 >nul
cd /d %~dp0

REM 1) FFmpeg
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERRO] FFmpeg nao encontrado. Rode no PowerShell:  winget install Gyan.FFmpeg
  echo Depois feche e abra de novo e rode este arquivo outra vez.
  goto :fim
)

REM 2) Python 3.12 (as bibliotecas de IA ainda nao funcionam no 3.14)
py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo.
  echo [ERRO] Python 3.12 nao encontrado. Rode no PowerShell:  winget install Python.Python.3.12
  echo Depois rode este arquivo outra vez.
  goto :fim
)

REM 3) Ambiente virtual com o Python 3.12 (recria se foi feito com outra versao)
if exist .venv\pyvenv.cfg (
  findstr /c:"version = 3.12" .venv\pyvenv.cfg >nul || (
    echo Recriando o ambiente com o Python 3.12...
    rmdir /s /q .venv
  )
)
if not exist .venv (
  echo Criando o ambiente Python pela primeira vez...
  py -3.12 -m venv .venv
)
call .venv\Scripts\activate

REM 4) Bibliotecas
echo Instalando/verificando as bibliotecas (na primeira vez demora alguns minutos)...
python -m pip install -q --upgrade pip
python -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao instalar as bibliotecas principais. Tire um print desta janela.
  goto :fim
)
python -m pip install -q -r requirements-ia.txt
REM O YouTube muda sempre: mantem o yt-dlp atualizado
python -m pip install -q -U yt-dlp
where deno >nul 2>nul
if errorlevel 1 echo [AVISO] Para importar links do YouTube, instale o Deno:  winget install DenoLand.Deno
if errorlevel 1 echo [AVISO] Nao instalei o faster-whisper: os cortes vao sair sem legenda.

if not exist .env copy configuracao-exemplo.txt .env >nul

REM 5) Liga o servidor e abre o navegador alguns segundos depois
echo.
echo  ==============================================
echo   Clip Storage rodando em http://localhost:8000
echo   Nao feche esta janela enquanto estiver usando.
echo  ==============================================
echo.
start "" cmd /c "timeout /t 6 >nul & start http://localhost:8000"
python -m uvicorn app.main:app --reload

:fim
echo.
pause
