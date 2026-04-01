import os
import sys
import traceback

from google.cloud import bigquery, resourcemanager_v3, storage
from loguru import logger

from .models import GCPAsset, GCPLocation, GCPProject, GCPTableBlob

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
def etl_project_task(message: str, type: str = "info"):
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
    obj, _ = GCPLocation.objects.get_or_create(name=loc_code.upper())
    return obj


# def parse_iso(iso_str):
#     if not iso_str:
#         return None
#     try:
#         return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
#     except:
#         return None


# def ingest_bigquery_metadata(data):
#     """Importação simplificada via JSON para Assets BQ."""
#     count = 0
#     for entry in data:
#         uri = entry.get("id")
#         if not uri:
#             continue
#         ds_ref = entry.get("datasetReference", {})
#         GCPAsset.objects.update_or_create(
#             uri=uri,
#             defaults={
#                 "asset_type": "BQ",
#                 "project_id": ds_ref.get("projectId", "unknown"),
#                 "name": ds_ref.get("datasetId", uri.split(":")[-1]),
#                 "location": get_location_obj(entry.get("location")),
#             },
#         )
#         count += 1
#     return count


# def ingest_gcs_metadata(data):
#     """Importação simplificada via JSON para Assets GCS."""
#     count = 0
#     for entry in data:
#         name = entry.get("name")
#         if not name:
#             continue
#         GCPAsset.objects.update_or_create(
#             uri=f"gs://{name}/",
#             defaults={
#                 "asset_type": "GCS",
#                 "project_id": entry.get("project_number", "unknown"),
#                 "name": name,
#                 "location": get_location_obj(entry.get("location")),
#             },
#         )
#         count += 1
#     return count


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

        GCPTableBlob.objects.update_or_create(
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

        GCPTableBlob.objects.update_or_create(
            table_catalog=bucket_name,
            table_schema=prefix,
            table_name=prefix.split("/")[-1] or prefix,
            defaults=defaults,
        )

        etl_storage_task(f"Insert GCPTableBlob {defaults}")


def scheduled_job_wrapper(func):
    """Decorator para garantir rastreabilidade no DjangoJobExecution."""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.bind(task="SYSTEM").error(
                f"Erro fatal no Job: {traceback.format_exc()}"
            )
            raise e

    return wrapper


def get_all_accessible_projects():
    """Lista IDs de projetos ativos via Resource Manager API."""
    try:
        client = resourcemanager_v3.ProjectsClient()
        search_request = resourcemanager_v3.SearchProjectsRequest(query="state:ACTIVE")
        projects = client.search_projects(request=search_request)
        # Filtra apenas projetos que contenham 'eqtl' no ID
        return [
            p.project_id.lower() for p in projects if "eqtl" in p.project_id.lower()
        ]
    except Exception as e:
        logger.error(f"Falha ao listar via Resource Manager: {e}")
        return [os.getenv("GOOGLE_CLOUD_PROJECT")]


@scheduled_job_wrapper
def sync_all_from_gcp():
    """Sincronização global refatorada para usar a descoberta do Resource Manager."""

    # resolution_content: Agora iteramos sobre a lista REAL de projetos acessíveis
    target_project_ids = get_all_accessible_projects()

    etl_project_task(
        f"Iniciando varredura em: {', '.join(pid for pid in target_project_ids if pid)}"
    )

    for project_id in target_project_ids:
        try:
            # Forçamos o cliente do BQ a olhar para o projeto específico da iteração
            bq_client = bigquery.Client(project=project_id)
            # Atualiza ou cria o objeto do projeto no Django
            project_obj, _ = GCPProject.all_objects.update_or_create(
                project_id=project_id,
                defaults={"name": project_id.lower()},
            )

            etl_project_task(f"Processando Projeto: {project_id}")

            # --- BQ DATASETS ---
            for dataset_item in list(bq_client.list_datasets()):
                ds = bq_client.get_dataset(dataset_item.dataset_id)
                etl_bigquery_task(f"Dataset carregado: {ds.full_dataset_id}")

                asset_defaults = {
                    "asset_types": "BQ",
                    "project": project_obj,
                    "name": ds.dataset_id,
                    "location": get_location_obj(ds.location),
                    "uri": f"bq://{project_id}/{ds.dataset_id}",
                }

                asset, _ = GCPAsset.objects.update_or_create(
                    project=project_obj,
                    name=ds.dataset_id,
                    defaults=asset_defaults,
                )

                # --- BQ TABLES ---
                for t_item in bq_client.list_tables(ds):
                    t = bq_client.get_table(t_item)

                    is_part = False
                    p_cols = []
                    if t.time_partitioning:
                        is_part = True
                        p_cols.append(t.time_partitioning.field or "_PARTITIONTIME")
                    if t.range_partitioning:
                        is_part = True
                        p_cols.append(t.range_partitioning.field)

                    table_defaults = {
                        "asset": asset,
                        "table_type": t.table_type,
                        "is_partitioned": is_part,
                        "partitions_fields": p_cols if p_cols else None,
                        "creation_time": t.created,
                        "ddl": t.view_query,
                        "metadata_raw": {
                            "description": t.description,
                            "num_rows": t.num_rows,
                            "num_bytes": t.num_bytes,
                            "location": t.location,
                        },
                    }

                    GCPTableBlob.objects.update_or_create(
                        table_name=t.table_id,
                        defaults=table_defaults,
                    )

        except Exception as e:
            etl_project_task(
                f"Erro ao processar projeto {project_id}: {str(e)}", "error"
            )
            # Continuamos para o próximo projeto em caso de erro em um específico
            continue

        # # --- GCS BUCKETS ---
        # try:
        #     s_client = storage.Client(project=project_id)

        #     etl_storage_task(f"Detalhes storage - {s_client}")

        #     for bucket in list(s_client.list_buckets()):
        #         defaults = {
        #             "asset_type": "GCS",
        #             "project_id": project_name,
        #             "name": bucket.name,
        #             "location": get_location_obj(bucket.location),
        #         }

        #         asset, _ = GCPAsset.objects.update_or_create(
        #             uri=f"gs://{bucket.name}/",
        #             defaults=defaults,
        #         )

        #         etl_storage_task(f"Insert GCPAsset - {defaults}")

        #         # Chamar descoberta lógica de Blobs
        #         discover_gcs_logical_tables(bucket.name, project_id, asset)
        # except exceptions.Forbidden as e:
        #     # Verifica se é VPC Service Controls
        #     if "vpcServiceControls" in str(e):
        #         etl_storage_task(
        #             f"Acesso bloqueado por VPC-SC no projeto {project_id}. Pulando...",
        #             "warning",
        #         )
        #     else:
        #         etl_storage_task(
        #             f"Erro de permissão (403) no projeto {project_id}: {e}", "error"
        #         )
        # except Exception:
        #     etl_storage_task(f"Insert GCPAsset - {traceback.format_exc()}", "error")

    return True
