from django.db import models


class LineageManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(excluido_logicamente=False)


class LineageBaseModel(models.Model):
    excluido_logicamente = models.BooleanField(default=False, verbose_name="Excluído")
    marcado_para_exclusao_fisica = models.BooleanField(
        default=False, verbose_name="Apagar"
    )
    objects = LineageManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, *args, **kwargs):
        self.excluido_logicamente = True
        self.save()
        for child in self.get_logical_children():
            child.delete()

    def get_logical_children(self):
        return []


class ProjetoDesenvolvimento(LineageBaseModel):
    nome = models.CharField(max_length=255, unique=True, verbose_name="Nome do Projeto")
    descricao = models.TextField(blank=True, verbose_name="Descrição")

    class Meta:
        verbose_name = "Projeto de Desenvolvimento"
        verbose_name_plural = "Projetos de Desenvolvimento"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class GCPProject(LineageBaseModel):
    project_id = models.CharField(
        max_length=128, unique=True, verbose_name="ID do Projeto GCP"
    )
    display_name = models.CharField(
        max_length=255, blank=True, verbose_name="Nome de Exibição"
    )

    class Meta:
        verbose_name = "Projeto GCP"
        verbose_name_plural = "Projetos GCP"
        ordering = ["project_id"]

    def __str__(self):
        return self.project_id


class GCPLocation(LineageBaseModel):
    codigo = models.CharField(max_length=100, unique=True, verbose_name="Código")
    nome = models.CharField(max_length=255, verbose_name="Nome")

    class Meta:
        verbose_name = "Localização GCP"
        verbose_name_plural = "Localizações GCP"

    def __str__(self):
        return f"{self.nome} ({self.codigo})"


class GCPAsset(LineageBaseModel):
    ASSET_TYPES = [("BQ", "BigQuery Dataset"), ("GCS", "Cloud Storage Bucket")]
    project = models.ForeignKey(
        GCPProject,
        on_delete=models.CASCADE,
        related_name="assets",
        verbose_name="Projeto",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=256, verbose_name="Nome (Dataset/Bucket)")
    query = models.TextField(blank=True, verbose_name="Query")
    asset_type = models.CharField(
        max_length=10, choices=ASSET_TYPES, verbose_name="Tipo"
    )
    location = models.ForeignKey(
        GCPLocation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Localização",
    )
    uri = models.CharField(max_length=512, unique=True, verbose_name="URI")
    last_imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ativo GCP"
        verbose_name_plural = "Ativos GCP"
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project.project_id}.{self.name}" if self.project else self.name

    def get_logical_children(self):
        return list(self.tables.all())


class GCPTable(LineageBaseModel):
    TABLE_TYPES = [
        ("TABLE", "Tabela Nativa"),
        ("EXTERNAL", "Tabela Externa"),
        ("VIEW", "View"),
        ("MATERIALIZED_VIEW", "View Materializada"),
        ("BLOB", "Blob/Folder GCS"),
    ]
    asset = models.ForeignKey(
        GCPAsset,
        on_delete=models.CASCADE,
        related_name="tables",
        verbose_name="Ativo",
        null=True,
        blank=True,
    )
    table_name = models.CharField(max_length=256, verbose_name="Nome da Tabela")
    table_type = models.CharField(
        max_length=50, choices=TABLE_TYPES, blank=True, verbose_name="Tipo"
    )
    is_partitioned = models.BooleanField(default=False, verbose_name="Particionada?")
    partition_columns = models.JSONField(
        default=list, blank=True, verbose_name="Colunas de Partição"
    )
    partitions_found = models.JSONField(
        default=list, blank=True, verbose_name="Partições Detectadas"
    )
    creation_time = models.DateTimeField(null=True, blank=True)
    metadata_raw = models.JSONField(default=dict, blank=True)
    projetos = models.ManyToManyField(
        ProjetoDesenvolvimento, blank=True, related_name="tabelas"
    )

    class Meta:
        verbose_name = "Tabela/Blob"
        verbose_name_plural = "Tabelas/Blobs"
        unique_together = ("asset", "table_name")

    def __str__(self):
        return f"{self.asset.name}.{self.table_name}" if self.asset else self.table_name

    def get_logical_children(self):
        return list(self.etls_saida.all()) + list(self.etls_entrada.all())


class GCPETL(LineageBaseModel):
    TIPO_CHOICES = [
        ("EXTRACTION", "Extração"),
        ("TRANSFORM", "Transformação"),
        ("LOAD", "Carga"),
    ]
    nome_processo = models.CharField(
        max_length=512, verbose_name="Processo", unique=True, blank=True
    )
    tipos_etl = models.JSONField(default=list, verbose_name="Tipos")
    fontes = models.ManyToManyField(
        GCPTable, related_name="etls_saida", blank=True, verbose_name="Fontes"
    )
    destino = models.ForeignKey(
        GCPTable,
        on_delete=models.CASCADE,
        related_name="etls_entrada",
        verbose_name="Destino",
        null=True,
        blank=True,
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.destino and self.destino.asset:
            self.nome_processo = f"{self.destino.asset.name}.{self.destino.table_name}"
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Processo ETL"
        verbose_name_plural = "Processos ETL"

    def __str__(self):
        return self.nome_processo
