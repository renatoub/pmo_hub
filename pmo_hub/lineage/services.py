import json
import os
from datetime import datetime, timezone
from google.cloud import bigquery, storage
from .models import GCPAsset, GCPTable, GCPLocation

def parse_ms(ms_str):
    if not ms_str: return None
    try:
        return datetime.fromtimestamp(int(ms_str) / 1000.0, tz=timezone.utc)
    except:
        return None

def parse_iso(iso_str):
    if not iso_str: return None
    try:
        # GCP format: 2025-05-29T21:29:26+0000 or similar
        return datetime.strptime(iso_str.replace('+0000', '+00:00'), '%Y-%m-%dT%H:%M:%S%z')
    except:
        try:
            return datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        except:
            return None

def parse_bool(val):
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.upper() in ["YES", "TRUE", "1"]
    return False

def get_location_obj(loc_code):
    if not loc_code: return None
    obj, _ = GCPLocation.objects.get_or_create(
        codigo=loc_code,
        defaults={'nome': loc_code.upper()}
    )
    return obj

def ingest_bigquery_metadata(data):
    count = 0
    for entry in data:
        uri = entry.get('id')
        if not uri:
            continue
        
        ds_ref = entry.get('datasetReference', {})
        project_id = ds_ref.get('projectId') or "unknown"
        name = ds_ref.get('datasetId') or uri.split(':')[-1]
        
        location_obj = get_location_obj(entry.get('location'))

        creation_time = parse_ms(entry.get('creationTime'))
        update_time = parse_ms(entry.get('lastModifiedTime'))

        access_config = entry.get('access', [])
        labels = entry.get('labels', {})

        GCPAsset.objects.update_or_create(
            uri=uri,
            defaults={
                'asset_type': 'BQ',
                'project_id': project_id,
                'name': name,
                'location': location_obj,
                'creation_time': creation_time,
                'update_time': update_time,
                'access_config': access_config,
                'labels': labels,
            }
        )
        count += 1
    return count

def ingest_gcs_metadata(data):
    count = 0
    for entry in data:
        name = entry.get('name')
        if not name:
            continue
        
        uri = entry.get('storage_url') or f"gs://{name}/"
        location_obj = get_location_obj(entry.get('location'))
        project_id = "unknown" # GCS usually project-specific
        
        creation_time = parse_iso(entry.get('creation_time'))
        update_time = parse_iso(entry.get('update_time'))

        labels = entry.get('labels', {})
        lifecycle_rules = entry.get('lifecycle_config', {}).get('rule', [])
        policies = {
            'soft_delete_policy': entry.get('soft_delete_policy'),
            'iam_configuration': entry.get('iam_configuration'),
            'default_storage_class': entry.get('default_storage_class'),
        }

        GCPAsset.objects.update_or_create(
            uri=uri,
            defaults={
                'asset_type': 'GCS',
                'project_id': project_id,
                'name': name,
                'location': location_obj,
                'creation_time': creation_time,
                'update_time': update_time,
                'labels': labels,
                'lifecycle_rules': lifecycle_rules,
                'policies': policies,
            }
        )
        count += 1
    return count

def ingest_tables_metadata(data, asset=None):
    """
    Importa metadados de tabelas/blobs.
    Se asset for None, tenta encontrar o Asset pelo table_catalog e table_schema.
    """
    count = 0
    for entry in data:
        table_name = entry.get('table_name') or entry.get('name')
        if not table_name:
            continue

        catalog = entry.get('table_catalog', '')
        schema = entry.get('table_schema', '')
        
        # Se asset não fornecido, busca pela chave composta (project_id, name)
        if not asset and catalog and schema:
            asset = GCPAsset.objects.filter(project_id=catalog, name=schema).first()

        creation_time_str = entry.get('creation_time')
        creation_time = None
        if creation_time_str:
            # Tenta vários formatos comuns
            for fmt in ['%Y-%m-%d %H:%M:%S.%f%z', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S']:
                try:
                    ts_str = creation_time_str.replace(' UTC', '+0000')
                    creation_time = datetime.strptime(ts_str, fmt)
                    break
                except:
                    continue
            
            if not creation_time:
                creation_time = parse_iso(creation_time_str)

        GCPTable.objects.update_or_create(
            table_catalog=catalog,
            table_schema=schema,
            table_name=table_name,
            defaults={
                'asset': asset,
                'table_type': entry.get('table_type', 'BASE TABLE'),
                'ddl': entry.get('ddl', ''),
                'is_insertable_into': parse_bool(entry.get('is_insertable_into', 'NO')),
                'is_typed': parse_bool(entry.get('is_typed', 'NO')),
                'creation_time': creation_time,
                'metadata_raw': entry,
            }
        )
        count += 1
    return count

def sync_all_from_gcp():
    """
    Função principal que utiliza as APIs do GCP para sincronizar ativos e tabelas de TODOS os projetos.
    """
    master_client = bigquery.Client()
    storage_client = storage.Client()
    
    # 1. Obter todos os projetos acessíveis
    projects = list(master_client.list_projects())
    
    for project_item in projects:
        project_id = project_item.project_id
        print(f"Sincronizando projeto: {project_id}")
        
        # Cliente específico para o projeto (ajuda com permissões e escopo)
        bq_client = bigquery.Client(project=project_id)
        
        # --- BigQuery ---
        try:
            datasets = list(bq_client.list_datasets())
            for dataset_item in datasets:
                ds = bq_client.get_dataset(dataset_item.dataset_id)
                asset_uri = f"{ds.project}:{ds.dataset_id}"
                
                asset, _ = GCPAsset.objects.update_or_create(
                    uri=asset_uri,
                    defaults={
                        'asset_type': 'BQ',
                        'project_id': ds.project,
                        'name': ds.dataset_id,
                        'location': get_location_obj(ds.location),
                        'creation_time': ds.created,
                        'update_time': ds.modified,
                        'labels': ds.labels,
                    }
                )
                
                # Tabelas do Dataset
                tables = list(bq_client.list_tables(ds))
                for table_item in tables:
                    try:
                        full_table = bq_client.get_table(table_item)
                        GCPTable.objects.update_or_create(
                            table_catalog=full_table.project,
                            table_schema=full_table.dataset_id,
                            table_name=full_table.table_id,
                            defaults={
                                'asset': asset,
                                'table_type': full_table.table_type,
                                'ddl': getattr(full_table, 'ddl', ''),
                                'is_insertable_into': True,
                                'creation_time': full_table.created,
                                'metadata_raw': {
                                    'description': full_table.description,
                                    'num_rows': full_table.num_rows,
                                    'num_bytes': full_table.num_bytes,
                                }
                            }
                        )
                    except Exception as e:
                        print(f"Erro ao obter tabela {table_item.table_id}: {str(e)}")
        except Exception as e:
            print(f"Erro ao listar datasets do projeto {project_id}: {str(e)}")

        # --- Cloud Storage (Buckets do projeto) ---
        try:
            # list_buckets pode ser filtrado por projeto
            buckets = list(storage_client.list_buckets(project=project_id))
            for bucket in buckets:
                asset, _ = GCPAsset.objects.update_or_create(
                    uri=f"gs://{bucket.name}/",
                    defaults={
                        'asset_type': 'GCS',
                        'project_id': project_id,
                        'name': bucket.name,
                        'location': get_location_obj(bucket.location),
                        'creation_time': bucket.time_created,
                        'update_time': bucket.updated,
                        'labels': bucket.labels,
                    }
                )
                
                # Blobs limitados para evitar lentidão
                blobs = list(storage_client.list_blobs(bucket, max_results=50))
                for blob in blobs:
                    GCPTable.objects.update_or_create(
                        table_catalog=bucket.name,
                        table_schema="blobs",
                        table_name=blob.name,
                        defaults={
                            'asset': asset,
                            'table_type': 'BLOB',
                            'creation_time': blob.time_created,
                            'metadata_raw': {
                                'size': blob.size,
                                'content_type': blob.content_type,
                            }
                        }
                    )
        except Exception as e:
            print(f"Erro ao listar buckets do projeto {project_id}: {str(e)}")

    return True
