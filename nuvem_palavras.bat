@echo off
cd /d "%~dp0"

set VENV=C:\envs\venv-nuvem_palavras

if not exist "%VENV%\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado: %VENV%
    pause
    exit /b
)

"%VENV%\Scripts\python.exe" -m streamlit run app.py

pause