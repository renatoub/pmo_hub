# scripts/gcs_backfill_assets.py
import requests
from google.cloud import storage

API_URL = "http://localhost:8000/lineage-api/ingest/"
BUCKET_NAME = "seu-bucket-de-dados"


def run_gcs_backfill():
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)

    print(f"Listando objetos no bucket: {BUCKET_NAME}...")
    blobs = bucket.list_blobs(max_results=500)  # Limite para teste

    for blob in blobs:
        uri = f"gcs://{BUCKET_NAME}/{blob.name}"

        # Registramos cada arquivo como um nó de 'Input' sem destino inicial
        # Isso popula a tabela de Assets e cria um registro de entrada
        payload = {
            "job_id": f"discovery-{blob.generation}",
            "service_type": "RUN",
            "script_code": f"Initial discovery of file: {blob.name}",
            "executed_at": blob.updated.isoformat(),
            "status": "SUCCESS",
            "source_uris": [uri],
            "target_uris": [],
        }

        try:
            response = requests.post(API_URL, json=payload)
            if response.status_code in [201, 200]:
                print(f"✅ Arquivo {blob.name} registrado como Asset.")
            else:
                print(f"❌ Erro no Asset {blob.name}: {response.text}")
        except Exception as e:
            print(f"⚠️ Falha na conexão para {blob.name}: {str(e)}")


if __name__ == "__main__":
    run_gcs_backfill()
