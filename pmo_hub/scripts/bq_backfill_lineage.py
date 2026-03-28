# scripts/bq_backfill_lineage.py
import requests
from google.cloud import bigquery
from datetime import datetime

# Configurações da sua API Django
API_URL = "http://localhost:8000/lineage-api/ingest/"
PROJECT_ID = "eqtl-prj-dev-dlk-bronze"
REGION = "southamerica-east1"


def run_bq_backfill():
    client = bigquery.Client(project=PROJECT_ID)

    # Query para buscar metadados de jobs que alteraram dados
    query = f"""
        SELECT
            job_id,
            query,
            start_time,
            end_time,
            state,
            project_id,
            user_email
        FROM `{REGION}`.INFORMATION_SCHEMA.JOBS_BY_PROJECT
        WHERE job_type = 'QUERY'
          AND statement_type IN ('INSERT', 'MERGE', 'CREATE_TABLE_AS_SELECT', 'UPDATE')
          AND state = 'DONE'
        ORDER BY creation_time DESC
        LIMIT 100
    """

    print(f"Buscando histórico de jobs no BigQuery ({REGION})...")
    query_job = client.query(query)

    for row in query_job:
        try:
            # Obtém detalhes técnicos do Job (tabelas referenciadas)
            job = client.get_job(row.job_id)

            sources = []
            if job.referenced_tables:
                for t in job.referenced_tables:
                    sources.append(f"bq://{t.project}.{t.dataset_id}.{t.table_id}")

            targets = []
            if job.destination:
                t = job.destination
                targets.append(f"bq://{t.project}.{t.dataset_id}.{t.table_id}")

            payload = {
                "job_id": row.job_id,
                "service_type": "BIGQUERY_JOB",
                "script_code": row.query,
                "executed_at": row.end_time.isoformat(),
                "status": row.state,
                "source_uris": sources,
                "target_uris": targets,
            }

            response = requests.post(API_URL, json=payload)
            if response.status_code in [201, 200]:
                print(f"✅ Job {row.job_id} registrado.")
            else:
                print(f"❌ Erle ao registrar {row.job_id}: {response.text}")

        except Exception as e:
            print(f"⚠️ Erro ao processar Job {row.job_id}: {str(e)}")


if __name__ == "__main__":
    run_bq_backfill()
