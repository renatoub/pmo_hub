# gcp/management/commands/runapscheduler.py

import logging
import time
import traceback

from apscheduler import events
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management.base import BaseCommand
from django_apscheduler import util
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJob

from gcp.jobs import sync_job

# Configuração de log local do comando
logger = logging.getLogger(__name__)


# resolution_content
def error_listener(event):
    """
    Listener que captura falhas em jobs e garante o log do traceback.
    O django-apscheduler usa isso para preencher o campo 'exception' no banco.
    """
    if event.exception:
        logger.error(f"Job {event.job_id} falhou: {event.exception}")
        logger.error(traceback.format_exc())


class Command(BaseCommand):
    help = "Inicia o APScheduler para tarefas do Lineage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--register-only",
            action="store_true",
            help="Apenas registra os jobs no banco de dados e encerra.",
        )

    def handle(self, *args, **options):
        db_path = settings.DATABASES["default"]["NAME"]
        self.stdout.write(f"Caminho do Banco: {db_path}")

        # Configuração do Scheduler
        if options["register_only"]:
            self.stdout.write("Modo: Apenas Registro (CI/CD)...")
            scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        else:
            scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)

        scheduler.add_jobstore(DjangoJobStore(), "default")

        # resolution_content
        # Adiciona o listener de eventos de erro ANTES de iniciar
        scheduler.add_listener(error_listener, events.EVENT_JOB_ERROR)

        # Garante que conexões antigas do Django sejam fechadas (evita erros de DB)
        scheduler.add_listener(
            util.close_old_connections,
            events.EVENT_JOB_EXECUTED | events.EVENT_JOB_ERROR,
        )

        # Registro do Job principal
        scheduler.add_job(
            sync_job,
            trigger=CronTrigger(day_of_week="sun", hour=3, minute=0),
            id="sync_gcp_metadata",
            max_instances=1,
            replace_existing=True,
            misfire_grace_time=3600,
        )

        # scheduler.add_job(
        #     delete_old_job_executions,
        #     trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
        #     id="delete_old_job_executions",
        #     max_instances=1,
        #     replace_existing=True,
        # )

        if options["register_only"]:
            scheduler.start()
            self.stdout.write("Sincronizando jobs com o banco...")
            time.sleep(2)  # Tempo para o JobStore persistir

            count = DjangoJob.objects.count()
            if count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Sucesso! {count} jobs persistidos.")
                )
            else:
                self.stdout.write(self.style.ERROR("Erro: Nenhum job persistido."))

            scheduler.shutdown()
            return

        # Modo Normal
        try:
            self.stdout.write("Iniciando loop do agendador...")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            self.stdout.write("Agendador encerrado.")
