@echo off
cd C:\EQTONE\pmo_hub\pmo_hub_%BRANCH%

echo --- Fazendo Backup ---
copy pmo_hub\db.sqlite3 ..\pmo_hub.sqlite3
call uv run python .\pmo_hub\manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 2 > ..\pmo_hub_datadump.json

echo --- Atualizando codigo (Git Pull) ---
:: Garante que estamos na main e baixa as novidades
git checkout main
git pull origin main

echo --- Aplicando Migrations ---
:: Executa o migrate antes de subir o servidor
call uv run python pmo_hub\manage.py migrate

echo --- Iniciando Servidor ---
call uv run python pmo_hub\manage.py runserver 0.0.0.0:%PORT%