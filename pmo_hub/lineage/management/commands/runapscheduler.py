import logging
from django.conf import settings
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from lineage.jobs import sync_job, delete_old_job_executions

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Inicia o APScheduler para tarefas do Lineage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--register-only",
            action="store_true",
            help="Apenas registra os jobs no banco de dados e encerra.",
        )

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
        self.stdout.write(self.style.SUCCESS("Agendado: sync_gcp_metadata_monthly"))

        # Limpeza semanal de logs de execução
        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        self.stdout.write(self.style.SUCCESS("Agendado: delete_old_job_executions"))

        if options["register_only"]:
            self.stdout.write(self.style.SUCCESS("Jobs registrados com sucesso no banco de dados. Encerrando."))
            return

        try:
            self.stdout.write("Iniciando scheduler...")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Parando scheduler...")
            scheduler.shutdown()
