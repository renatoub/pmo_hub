import json
import os
import shutil
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from lineage.services import ingest_bigquery_metadata, ingest_gcs_metadata

class Command(BaseCommand):
    help = 'Importa metadados do BigQuery e GCS a partir de arquivos JSON (localizados na raiz)'

    def handle(self, *args, **options):
        # Configuração de diretórios
        storage_dir = os.path.join(settings.BASE_DIR, 'storage', 'metadata_imports')
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

        bq_file = os.path.join(settings.BASE_DIR, 'bigquery_metadata.json')
        gcs_file = os.path.join(settings.BASE_DIR, 'buckets.json')

        if os.path.exists(bq_file):
            self.stdout.write(self.style.SUCCESS(f'Processando BigQuery: {bq_file}'))
            with open(bq_file, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
            count = ingest_bigquery_metadata(data)
            self.backup_file(bq_file, storage_dir, 'bq_metadata')
            self.stdout.write(self.style.SUCCESS(f'Importados {count} ativos do BigQuery'))
        else:
            self.stdout.write(self.style.WARNING(f'Arquivo BigQuery não encontrado: {bq_file}'))

        if os.path.exists(gcs_file):
            self.stdout.write(self.style.SUCCESS(f'Processando GCS: {gcs_file}'))
            # Note: Checking encoding as GCS sometimes exported as utf-16 from some tools
            try:
                with open(gcs_file, 'r', encoding='utf-16') as f:
                    data = json.load(f)
            except UnicodeError:
                with open(gcs_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            count = ingest_gcs_metadata(data)
            self.backup_file(gcs_file, storage_dir, 'gcs_metadata')
            self.stdout.write(self.style.SUCCESS(f'Importados {count} ativos do GCS'))
        else:
            self.stdout.write(self.style.WARNING(f'Arquivo GCS não encontrado: {gcs_file}'))

    def backup_file(self, source_path, storage_dir, prefix):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{prefix}_{timestamp}.json"
        dest_path = os.path.join(storage_dir, filename)
        shutil.copy2(source_path, dest_path)
        return dest_path
