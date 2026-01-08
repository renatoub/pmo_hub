@echo off
cd C:\EQTONE\pmo_hub\pmo_hub_%BRANCH%

@REM echo --- Fazendo Backup ---
@REM copy pmo_hub\db.sqlite3 ..\pmo_hub.sqlite3
@REM call uv run python .\pmo_hub\manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > ..\pmo_hub_datadump.json

@REM echo --- Atualizando codigo (Git Pull) ---
@REM :: Garante que estamos na main e baixa as novidades
@REM git checkout main
@REM git pull origin main

@REM echo --- Aplicando Migrations ---
@REM :: Executa o migrate antes de subir o servidor
@REM call uv run python pmo_hub\manage.py migrate

echo --- Iniciando Servidor ---
call uv run python pmo_hub\manage.py runserver 0.0.0.0:%PORT%