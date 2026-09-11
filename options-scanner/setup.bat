@echo off
rem One-shot Windows setup: installs dependencies, asks for tastytrade
rem credentials (only if .env doesn't exist), validates, launches dashboard.
setlocal EnableDelayedExpansion
cd /d "%~dp0"
set PY=python
where python >nul 2>nul || set PY=py

echo Installing dependencies (first run can take a few minutes)...
%PY% -m pip install --quiet -r requirements.txt

if exist .env goto check
echo.
echo Enter your tastytrade API credentials (from developer.tastytrade.com):
set /p TT_SECRET=CLIENT SECRET:
set /p TT_TOKEN=REFRESH TOKEN:
> .env echo TASTYTRADE_CLIENT_SECRET=!TT_SECRET!
>> .env echo TASTYTRADE_REFRESH_TOKEN=!TT_TOKEN!
echo Saved to .env (stays on this computer; git-ignored).

:check
echo.
echo Validating tastytrade connection...
%PY% -m scanner.tastytrade_check
if errorlevel 1 goto fail
%PY% -m streamlit run app.py
goto :eof

:fail
echo Validation failed - fix the values in .env (or delete .env and rerun), or
echo run with free Yahoo data: %PY% -m streamlit run app.py
pause
