@echo off
rem Opens BitCraft in a new, large terminal window. Usage: bitcraft [run | demo | here | status] [options]
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%ROOT%"
"%PY%" -m bitcraft.cli %*
