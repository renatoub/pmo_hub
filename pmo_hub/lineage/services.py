import json
import os
import re
import logging
from datetime import datetime, timezone
from google.cloud import bigquery, storage
from google.api_core import exceptions
from .models import GCPProject, GCPAsset, GCPTable, GCPLocation

# Configuração do Logger conforme o padrão do usuário
logger = logging.getLogger(__name__)

def get_location_obj(loc_code):
    if not loc_code: return None
    obj, _ = GCPLocation.objects.get_or_create(
        codigo=loc_code,
        defaults={'nome': loc_code.upper()}
    )
    return obj

def ingest_bigquery_metadata(data):
    """Importação simplificada via JSON para Assets BQ."""
    count = 0
    for entry in data:
        uri = entry.get('id')
        if not uri: continue
        ds_ref = entry.get('datasetReference', {})
        pid = ds_ref.get('projectId', 'unknown')
        
        # Garante que o projeto exista
        project_obj, _ = GCPProject.objects.get_or_create(project_id=pid)
        
        GCPAsset.objects.update_or_create(
            project=project_obj,
            name=ds_ref.get('datasetId', uri.split(':')[-1]),
            defaults={
                'asset_type': 'BQ',
                'location': get_location_obj(entry.get('location')),
                'uri': uri
            }
        )
        count += 1
    return count

def ingest_gcs_metadata(data):
    """Importação simplificada via JSON para Assets GCS."""
    count = 0
    for entry in data:
        name = entry.get('name')
        if not name: continue
        pid = entry.get('project_number', 'unknown')
        
        project_obj, _ = GCPProject.objects.get_or_create(project_id=pid)
        
        GCPAsset.objects.update_or_create(
            project=project_obj,
            name=name,
            defaults={
                'asset_type': 'GCS',
                'location': get_location_obj(entry.get('location')),
                'uri': f"gs://{name}/"
            }
        )
        count += 1
    return count

def discover_gcs_partitions(bucket_name, project_id, asset_obj):
    """
    Agrupa blobs do GCS em 'Tabelas Lógicas' e detecta particionamento Hive.
    """
    try:
        client = storage.Client(project=project_id)
        logger.info(f"STORAGE - Detalhes storage - {client}")
        bucket = client.bucket(bucket_name)
        blobs = list(client.list_blobs(bucket, max_results=1000))
        
        logical_tables = {} 

        for blob in blobs:
            path_parts = blob.name.split('/')
            parts_before_partition = []
            partition_info = {}

            for part in path_parts:
                if '=' in part:
                    key, val = part.split('=', 1)
                    partition_info[key] = val
                elif any(part.endswith(ext) for ext in ['.parquet', '.csv', '.json', '.avro']):
                    break
                else:
                    parts_before_partition.append(part)
            
            root_prefix = "/".join(parts_before_partition)
            if not root_prefix: continue

            if root_prefix not in logical_tables:
                logical_tables[root_prefix] = {"cols": set(), "vals": set(), "sample": blob}
            
            for k, v in partition_info.items():
                logical_tables[root_prefix]["cols"].add(k)
                logical_tables[root_prefix]["vals"].add(f"{k}={v}")

        for prefix, info in logical_tables.items():
            GCPTable.objects.update_or_create(
                asset=asset_obj,
                table_name=prefix.split('/')[-1] or prefix,
                defaults={
                    'table_type': 'BLOB',
                    'is_partitioned': len(info["cols"]) > 0,
                    'partition_columns': list(info["cols"]),
                    'partitions_found': sorted(list(info["vals"])),
                    'creation_time': info["sample"].time_created,
                }
            )
    except exceptions.Forbidden:
        logger.warning(f"STORAGE - Acesso bloqueado por VPC-SC no projeto {project_id}. Pulando...")
    except Exception as e:
        logger.error(f"STORAGE - Erro ao processar buckets: {str(e)}")

def sync_all_from_gcp():
    """
    Sincronização guiada pelos projetos cadastrados no banco de dados.
    """
    projects = GCPProject.objects.filter(excluido_logicamente=False)
    
    for project_obj in projects:
        pid = project_obj.project_id
        logger.info(f"BIGQUERY - Detalhes projeto - project_id={pid}")
        
        # --- BIGQUERY ---
        try:
            bq_client = bigquery.Client(project=pid)
            for ds_item in bq_client.list_datasets():
                ds = bq_client.get_dataset(ds_item.dataset_id)
                asset, _ = GCPAsset.objects.update_or_create(
                    project=project_obj,
                    name=ds.dataset_id,
                    defaults={
                        'asset_type': 'BQ',
                        'location': get_location_obj(ds.location),
                        'uri': f"{pid}:{ds.dataset_id}"
                    }
                )
                
                for t_item in bq_client.list_tables(ds):
                    t = bq_client.get_table(t_item)
                    
                    # Detecção de Particionamento BQ
                    is_part = False
                    p_cols = []
                    if t.time_partitioning:
                        is_part = True
                        p_cols.append(t.time_partitioning.field or "_PARTITIONTIME")
                    if t.range_partitioning:
                        is_part = True
                        p_cols.append(t.range_partitioning.field)

                    GCPTable.objects.update_or_create(
                        asset=asset,
                        table_name=t.table_id,
                        defaults={
                            'table_type': t.table_type,
                            'is_partitioned': is_part,
                            'partition_columns': p_cols,
                            'creation_time': t.created,
                        }
                    )
        except Exception as e:
            logger.error(f"BIGQUERY - Erro no projeto {pid}: {str(e)}")

        # --- STORAGE ---
        try:
            s_client = storage.Client(project=pid)
            for bucket in s_client.list_buckets():
                asset, _ = GCPAsset.objects.update_or_create(
                    project=project_obj,
                    name=bucket.name,
                    defaults={
                        'asset_type': 'GCS',
                        'location': get_location_obj(bucket.location),
                        'uri': f"gs://{bucket.name}/"
                    }
                )
                discover_gcs_partitions(bucket.name, pid, asset)
        except Exception as e:
            logger.error(f"STORAGE - Erro no projeto {pid}: {str(e)}")

    return True

def ingest_tables_metadata(data):
    """Importação manual via JSON mantendo suporte a tipos e partições."""
    count = 0
    for entry in data:
        # Lógica de mapeamento via projeto e dataset
        p_id = entry.get('project_id') or entry.get('table_catalog')
        ds_id = entry.get('dataset_id') or entry.get('table_schema')
        t_name = entry.get('table_name')
        
        if not all([p_id, ds_id, t_name]): continue

        asset = GCPAsset.objects.filter(project__project_id=p_id, name=ds_id).first()
        if not asset: continue

        GCPTable.objects.update_or_create(
            asset=asset,
            table_name=t_name,
            defaults={
                'table_type': entry.get('table_type', 'TABLE'),
                'is_partitioned': entry.get('is_partitioned', False),
                'partition_columns': entry.get('partition_columns', []),
                'partitions_found': entry.get('partitions_found', []),
                'metadata_raw': entry,
            }
        )
        count += 1
    return count
