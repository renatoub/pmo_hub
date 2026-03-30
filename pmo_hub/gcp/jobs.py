import logging
from gcp.services import sync_all_from_gcp
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

logger = logging.getLogger(__name__)


def sync_job():
    logger.info("Iniciando Sincronização Mensal com GCP...")
    try:
        sync_all_from_gcp()
        logger.info("Sincronização com GCP concluída com sucesso.")
    except Exception as e:
        logger.error(f"Erro durante a sincronização com GCP: {str(e)}")


@util.close_old_connections
def delete_old_job_executions(max_age=604_800):
    """Apaga execuções antigas do banco (padrão 1 semana)."""
    DjangoJobExecution.objects.delete_old_job_executions(max_age)
