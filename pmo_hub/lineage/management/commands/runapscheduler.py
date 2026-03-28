import logging

from django.conf import settings

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJobExecution
from django_apscheduler import util

from lineage.services import sync_all_from_gcp

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


class Command(BaseCommand):
    help = "Inicia o APScheduler para tarefas do Lineage."

    def handle(self, *args, **options):
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # Agendamento Mensal (Dia 1 de cada mês às 03:00)
        scheduler.add_job(
            sync_job,
            trigger=CronTrigger(day=1, hour=3, minute=0),
            id="sync_gcp_metadata_monthly",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Agendado: sync_gcp_metadata_monthly (Mensal - Dia 1)")

        # Limpeza semanal de logs de execução
        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        logger.info("Agendado: delete_old_job_executions (Semanal)")

        try:
            logger.info("Iniciando scheduler...")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Parando scheduler...")
            scheduler.shutdown()
            logger.info("Scheduler parado.")
