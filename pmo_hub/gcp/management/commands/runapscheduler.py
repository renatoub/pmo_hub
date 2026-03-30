import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from django_apscheduler.models import DjangoJob

from gcp.jobs import sync_job

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
        db_path = settings.DATABASES["default"]["NAME"]
        self.stdout.write(f"Caminho do Banco: {db_path}")

        # Se for apenas registro, usamos o BackgroundScheduler para não travar
        if options["register_only"]:
            self.stdout.write("Modo: Apenas Registro (CI/CD)...")
            scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
            scheduler.add_jobstore(DjangoJobStore(), "default")

            # Iniciamos o scheduler em background para ativar a persistência
            scheduler.start()

            # Registramos os jobs
            scheduler.add_job(
                sync_job,
                trigger=CronTrigger(hour=3, minute=0),
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

            # Pequena pausa para garantir que os jobs foram salvos no SQLite
            time.sleep(2)

            # Verificação final no banco
            count = DjangoJob.objects.count()
            if count > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"Sucesso! {count} jobs persistidos no banco.")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        "Erro crítico: O banco continua reportando 0 jobs após tentativa de registro."
                    )
                )

            scheduler.shutdown()
            return

        # Modo Normal (Servidor rodando)
        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # Garantimos que os jobs estejam lá ao iniciar
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

        try:
            self.stdout.write("Iniciando loop do agendador...")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            self.stdout.write("Agendador encerrado.")
