@echo off
cd C:\EQTONE\pmo_hub\pmo_hub_%BRANCH%

echo --- Iniciando Servidor ---
call uv run python pmo_hub\manage.py runserver 0.0.0.0:%PORT%