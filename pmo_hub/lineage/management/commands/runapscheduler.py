import logging
from django.conf import settings
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from lineage.jobs import sync_job, delete_old_job_executions
from django.db import transaction, connection

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
        # Log para depuração de caminho
        db_path = settings.DATABASES['default']['NAME']
        self.stdout.write(f"Editando banco de dados em: {db_path}")

        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # Usamos uma transação atômica para garantir o registro no SQLite
        with transaction.atomic():
            # Agendamento Mensal (Dia 1 de cada mês às 03:00)
            scheduler.add_job(
                sync_job,
                trigger=CronTrigger(day=1, hour=3, minute=0),
                id="sync_gcp_metadata_monthly",
                max_instances=1,
                replace_existing=True,
            )

            # Limpeza semanal de logs de execução
            scheduler.add_job(
                delete_old_job_executions,
                trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
                id="delete_old_job_executions",
                max_instances=1,
                replace_existing=True,
            )

        if options["register_only"]:
            from django_apscheduler.models import DjangoJob
            count = DjangoJob.objects.count()
            self.stdout.write(self.style.SUCCESS(f"Sucesso! {count} jobs registrados permanentemente no banco."))
            return

        try:
            self.stdout.write("Iniciando scheduler loop...")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.stdout.write("Parando scheduler...")
            scheduler.shutdown()
