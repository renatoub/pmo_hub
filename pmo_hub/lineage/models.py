from django.db import models


class ProjetoDesenvolvimento(models.Model):
    nome = models.CharField(max_length=255, unique=True, verbose_name="Nome do Projeto")
    descricao = models.TextField(blank=True, verbose_name="Descrição")

    class Meta:
        verbose_name = "Projeto de Desenvolvimento"
        verbose_name_plural = "Projetos de Desenvolvimento"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class GCPLocation(models.Model):
    codigo = models.CharField(max_length=100, unique=True, verbose_name="Código da Região (ex: us-central1)")
    nome = models.CharField(max_length=255, verbose_name="Nome Amigável")

    class Meta:
        verbose_name = "Localização GCP"
        verbose_name_plural = "Localizações GCP"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class GCPAsset(models.Model):
    ASSET_TYPES = [
        ("BQ", "BigQuery Dataset"),
        ("GCS", "Cloud Storage Bucket"),
    ]

    uri = models.CharField(
        max_length=512, unique=True, primary_key=True, verbose_name="URI (ID Único)"
    )
    asset_type = models.CharField(
        max_length=10, choices=ASSET_TYPES, verbose_name="Tipo de Ativo"
    )
    project_id = models.CharField(max_length=128, verbose_name="ID do Projeto GCP")
    location = models.ForeignKey(
        GCPLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Localização",
    )
    name = models.CharField(max_length=256, verbose_name="Nome")

    # Flexible Metadata
    labels = models.JSONField(default=dict, blank=True, verbose_name="Rótulos (Labels)")
    access_config = models.JSONField(
        default=list, blank=True, verbose_name="Configuração de Acesso (IAM)"
    )
    lifecycle_rules = models.JSONField(
        default=list, blank=True, verbose_name="Regras de Ciclo de Vida"
    )
    policies = models.JSONField(default=dict, blank=True, verbose_name="Políticas")

    # Audit Fields
    creation_time = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Criação"
    )
    update_time = models.DateTimeField(
        null=True, blank=True, verbose_name="Última Atualização no GCP"
    )
    last_imported_at = models.DateTimeField(
        auto_now=True, verbose_name="Data da Última Importação"
    )

    class Meta:
        verbose_name = "Ativo GCP"
        verbose_name_plural = "Ativos GCP"
        unique_together = ("project_id", "name")
        ordering = ["project_id", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_asset_type_display()})"


class GCPTable(models.Model):
    TABLE_TYPES = [
        ("BASE TABLE", "Base Table"),
        ("VIEW", "View"),
        ("EXTERNAL", "External Table"),
        ("MATERIALIZED VIEW", "Materialized View"),
        ("BLOB", "Storage Blob/File"),
    ]

    # Mantendo a FK opcional para possibilitar Inlines no Admin, 
    # embora a chave de negócio seja table_catalog + table_schema
    asset = models.ForeignKey(
        GCPAsset,
        on_delete=models.CASCADE,
        related_name="tables",
        verbose_name="Ativo Pai",
        null=True, blank=True
    )
    table_name = models.CharField(max_length=256, verbose_name="Nome da Tabela/Blob")
    table_schema = models.CharField(
        max_length=256, blank=True, verbose_name="Schema/Dataset"
    )
    table_catalog = models.CharField(
        max_length=256, blank=True, verbose_name="Catálogo/Projeto"
    )
    table_type = models.CharField(
        max_length=50, choices=TABLE_TYPES, blank=True, verbose_name="Tipo"
    )

    # Metadata Fields
    ddl = models.TextField(blank=True, verbose_name="DDL / Definição")
    is_insertable_into = models.BooleanField(default=False, verbose_name="Inserível?")
    is_typed = models.BooleanField(default=False, verbose_name="Tipada?")
    creation_time = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Criação"
    )

    # Relations
    projetos = models.ManyToManyField(
        ProjetoDesenvolvimento,
        blank=True,
        related_name="tabelas",
        verbose_name="Projetos de Desenvolvimento",
    )

    metadata_raw = models.JSONField(
        default=dict, blank=True, verbose_name="Metadados Brutos"
    )

    class Meta:
        verbose_name = "Tabela/Blob"
        verbose_name_plural = "Tabelas/Blobs"
        unique_together = ("table_catalog", "table_schema", "table_name")
        ordering = ["table_name"]

    def __str__(self):
        return f"{self.table_name} ({self.table_schema})"
