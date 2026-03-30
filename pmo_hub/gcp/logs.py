import os
import sys

from loguru import logger

# 1. Definição de Caminhos (Padrão Windows)
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Limpa handlers padrão
logger.remove()

# Console (Stdout) - Importante para monitoramento em tempo real no servidor
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
)

logger.add(
    os.path.join(LOG_DIR, "projects_step.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    filter=lambda record: record["extra"].get("task") == "PROJECTS",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,
)

logger.add(
    os.path.join(LOG_DIR, "bigquery_step.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    filter=lambda record: record["extra"].get("task") == "BIGQUERY",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,
)

logger.add(
    os.path.join(LOG_DIR, "storage_step.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    filter=lambda record: record["extra"].get("task") == "STORAGE",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,
)
