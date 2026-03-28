import logging
from django.conf import settings
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from django.core.management.base import BaseCommand
from django_apscheduler.jobstores import DjangoJobStore
from lineage.jobs import sync_job, delete_old_job_executions
from django_apscheduler.models import DjangoJob

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
        db_path = settings.DATABASES['default']['NAME']
        self.stdout.write(f"Conectado ao banco: {db_path}")

        scheduler = BlockingScheduler(timezone=settings.TIME_ZONE)
        scheduler.add_jobstore(DjangoJobStore(), "default")

        # 1. Registrar Sincronização Mensal
        scheduler.add_job(
            sync_job,
            trigger=CronTrigger(day=1, hour=3, minute=0),
            id="sync_gcp_metadata_monthly",
            max_instances=1,
            replace_existing=True,
        )
        self.stdout.write("Tentativa de registro: sync_gcp_metadata_monthly")

        # 2. Registrar Limpeza Semanal
        scheduler.add_job(
            delete_old_job_executions,
            trigger=CronTrigger(day_of_week="mon", hour="00", minute="00"),
            id="delete_old_job_executions",
            max_instances=1,
            replace_existing=True,
        )
        self.stdout.write("Tentativa de registro: delete_old_job_executions")

        # Verificação direta no banco
        count = DjangoJob.objects.count()

        if options["register_only"]:
            if count > 0:
                self.stdout.write(self.style.SUCCESS(f"Sucesso! {count} jobs confirmados no banco de dados."))
            else:
                self.stdout.write(self.style.WARNING("Alerta: Os jobs foram enviados mas o banco ainda reporta 0 registros."))
                self.stdout.write("Dica: Verifique se as migrações do 'django_apscheduler' foram aplicadas neste banco.")
            return

        try:
            self.stdout.write("Iniciando loop do agendador...")
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()
            self.stdout.write("Agendador encerrado.")
