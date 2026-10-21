@echo off
cd /d "%~dp0"
title Verifica Stock
where python >nul 2>nul && (python server.py) || (py server.py)
if errorlevel 1 (
  echo.
  echo No se pudo iniciar. Comprueba que Python 3 este instalado: https://www.python.org/downloads/
  pause
)
