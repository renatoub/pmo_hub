import os
import sys
import traceback
from datetime import datetime

from google.api_core import exceptions
from google.cloud import bigquery, storage
from loguru import logger

from .models import GCPAsset, GCPLocation, GCPTable

# 1. Definição de Caminhos (Padrão Windows)
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# Limpa handlers padrão
logger.remove()

# Console (Stdout) - Importante para monitoramento em tempo real no servidor
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
)

# Configuração dos Sinks (Arquivos)
# Adicionado 'enqueue=True' para evitar conflitos de escrita (Race Conditions) no Windows
# Adicionado 'rotation' para evitar que o arquivo cresça indefinidamente no servidor
logger.add(
    os.path.join(LOG_DIR, "projects_step.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    filter=lambda record: record["extra"].get("task") == "PROJECTS",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,
)

logger.add(
    os.path.join(LOG_DIR, "bigquery_step.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    filter=lambda record: record["extra"].get("task") == "BIGQUERY",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,
)

logger.add(
    os.path.join(LOG_DIR, "storage_step.log"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {extra[name]} - {message}",
    filter=lambda record: record["extra"].get("task") == "STORAGE",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,
)


# 2. Funções mantendo sua assinatura original
def etl_projects_task(message: str, type: str = "info"):
    # .bind injeta o contexto para o filtro e para o format
    log = logger.bind(task="PROJECTS", name="PROJECTS")
    getattr(log, type.lower(), log.info)(message)


def etl_bigquery_task(message: str, type: str = "info"):
    log = logger.bind(task="BIGQUERY", name="BIGQUERY")
    getattr(log, type.lower(), log.info)(message)


def etl_storage_task(message: str, type: str = "info"):
    log = logger.bind(task="STORAGE", name="STORAGE")
    metodo = getattr(log, type.lower(), log.info)
    metodo(message)


def get_location_obj(loc_code):
    if not loc_code:
        return None
    obj, _ = GCPLocation.objects.get_or_create(
        codigo=loc_code, defaults={"nome": loc_code.upper()}
    )
    return obj


def parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except:
        return None


def ingest_bigquery_metadata(data):
    """Importação simplificada via JSON para Assets BQ."""
    count = 0
    for entry in data:
        uri = entry.get("id")
        if not uri:
            continue
        ds_ref = entry.get("datasetReference", {})
        GCPAsset.objects.update_or_create(
            uri=uri,
            defaults={
                "asset_type": "BQ",
                "project_id": ds_ref.get("projectId", "unknown"),
                "name": ds_ref.get("datasetId", uri.split(":")[-1]),
                "location": get_location_obj(entry.get("location")),
            },
        )
        count += 1
    return count


def ingest_gcs_metadata(data):
    """Importação simplificada via JSON para Assets GCS."""
    count = 0
    for entry in data:
        name = entry.get("name")
        if not name:
            continue
        GCPAsset.objects.update_or_create(
            uri=f"gs://{name}/",
            defaults={
                "asset_type": "GCS",
                "project_id": entry.get("project_number", "unknown"),
                "name": name,
                "location": get_location_obj(entry.get("location")),
            },
        )
        count += 1
    return count


def ingest_tables_metadata(data):
    """Importação via JSON para Tabelas (usado no upload manual)."""
    count = 0
    for entry in data:
        catalog = entry.get("table_catalog", "")
        schema = entry.get("table_schema", "")
        name = entry.get("table_name", "")
        if not name:
            continue

        asset = GCPAsset.objects.filter(project_id=catalog, name=schema).first()

        GCPTable.objects.update_or_create(
            table_catalog=catalog,
            table_schema=schema,
            table_name=name,
            defaults={
                "asset": asset,
                "table_type": entry.get("table_type", "TABLE"),
                "metadata_raw": entry,
            },
        )
        count += 1
    return count


def discover_gcs_logical_tables(bucket_name, project_id, asset_obj):
    """
    Agrupa blobs do GCS em 'Tabelas Lógicas' e detecta partições Hive (key=val).
    """
    client = storage.Client(project=project_id)
    bucket = client.bucket(bucket_name)
    blobs = list(client.list_blobs(bucket, max_results=500))

    try:
        etl_storage_task(f"Detalhes bucket - {str(bucket)}")
        etl_storage_task(f"Detalhes blobs - {list(blobs)}")
    except Exception:
        etl_storage_task(f"{traceback.format_exc()}", "error")

    logical_tables = {}  # { "prefix": { "files": [], "partitions": { "col": [vals] } } }

    for blob in blobs:
        path_parts = blob.name.split("/")
        # Tenta identificar o nome da tabela (primeiro nível que não é partição)
        root_prefix = ""
        parts_before_partition = []
        partition_info = {}

        for part in path_parts:
            if "=" in part:
                key, val = part.split("=", 1)
                partition_info[key] = val
            elif (
                part.endswith(".parquet")
                or part.endswith(".csv")
                or part.endswith(".json")
            ):
                # Fim do caminho
                break
            else:
                parts_before_partition.append(part)

        root_prefix = "/".join(parts_before_partition)
        if not root_prefix:
            continue

        if root_prefix not in logical_tables:
            logical_tables[root_prefix] = {
                "cols": set(),
                "vals": set(),
                "sample_blob": blob,
            }

        for k, v in partition_info.items():
            logical_tables[root_prefix]["cols"].add(k)
            logical_tables[root_prefix]["vals"].add(f"{k}={v}")

    for prefix, info in logical_tables.items():
        defaults = {
            "asset": asset_obj,
            "table_type": "BLOB",
            "is_partitioned": len(info["cols"]) > 0,
            "partition_columns": list(info["cols"]),
            "partitions_found": sorted(list(info["vals"])),
            "creation_time": info["sample_blob"].time_created,
        }

        GCPTable.objects.update_or_create(
            table_catalog=bucket_name,
            table_schema=prefix,
            table_name=prefix.split("/")[-1] or prefix,
            defaults=defaults,
        )

        etl_storage_task(f"Insert GCPTable - {defaults}")


def sync_all_from_gcp():
    """Sincronização global via APIs do Google."""
    master_client = bigquery.Client()
    projects = list(master_client.list_projects())

    for proj in projects:
        pid = proj.friendly_name
        bq_client = bigquery.Client(project=pid)

        try:
            etl_bigquery_task(
                f"Detalhes projeto - project_id={proj.project_id} | friendly_name={proj.friendly_name}"
            )
        except Exception:
            etl_bigquery_task(f"{traceback.format_exc()}", "error")

        if "EQTL" not in str(pid.upper()):
            continue

        # --- BQ DATASETS ---
        try:
            for ds_item in bq_client.list_datasets():
                etl_bigquery_task(f"Entrou em ds_item {ds_item}")
                ds = bq_client.get_dataset(ds_item.dataset_id)

                defaults = {
                    "asset_type": "BQ",
                    "project_id": pid,
                    "name": ds.dataset_id,
                    "location": get_location_obj(ds.location),
                }

                asset, _ = GCPAsset.objects.update_or_create(
                    uri=f"{pid}:{ds.dataset_id}",
                    defaults=defaults,
                )

                etl_bigquery_task(f"Insert GCPAsset - {defaults}")

                # --- BQ TABLES ---
                for t_item in bq_client.list_tables(ds):
                    t = bq_client.get_table(t_item)

                    etl_bigquery_task(f"Detalhes get_table - {t}")

                    # Detecção de tipo refinada
                    t_type = t.table_type  # TABLE, VIEW, EXTERNAL, MATERIALIZED_VIEW

                    etl_bigquery_task(f"Tipo da tabela - {t_type}")

                    # Detecção de Particionamento BQ
                    is_part = False
                    p_cols = []
                    if t.time_partitioning:
                        is_part = True
                        p_cols.append(t.time_partitioning.field or "_PARTITIONTIME")
                    if t.range_partitioning:
                        is_part = True
                        p_cols.append(t.range_partitioning.field)

                    defaults = {
                        "asset": asset,
                        "table_type": t_type,
                        "is_partitioned": is_part,
                        "partition_columns": p_cols,
                        "creation_time": t.created,
                        "metadata_raw": {
                            "description": t.description,
                            "num_rows": t.num_rows,
                            "location": t.location,
                        },
                    }

                    GCPTable.objects.update_or_create(
                        table_catalog=pid,
                        table_schema=ds.dataset_id,
                        table_name=t.table_id,
                        defaults=defaults,
                    )

                    etl_bigquery_task(f"Insert GCPTable - {defaults}")

        except Exception:
            etl_bigquery_task(f"Insert GCPAsset - {traceback.format_exc()}", "error")

        # --- GCS BUCKETS ---
        try:
            s_client = storage.Client(project=pid)

            etl_storage_task(f"Detalhes storage - {s_client}")

            for bucket in s_client.list_buckets():
                defaults = {
                    "asset_type": "GCS",
                    "project_id": pid,
                    "name": bucket.name,
                    "location": get_location_obj(bucket.location),
                }

                asset, _ = GCPAsset.objects.update_or_create(
                    uri=f"gs://{bucket.name}/",
                    defaults=defaults,
                )

                etl_storage_task(f"Insert GCPAsset - {defaults}")

                # Chamar descoberta lógica de Blobs
                discover_gcs_logical_tables(bucket.name, pid, asset)
        except exceptions.Forbidden as e:
            # Verifica se é VPC Service Controls
            if "vpcServiceControls" in str(e):
                etl_storage_task(
                    f"Acesso bloqueado por VPC-SC no projeto {pid}. Pulando...",
                    "warning",
                )
            else:
                etl_storage_task(
                    f"Erro de permissão (403) no projeto {pid}: {e}", "error"
                )
        except Exception:
            etl_storage_task(f"Insert GCPAsset - {traceback.format_exc()}", "error")

    return True
