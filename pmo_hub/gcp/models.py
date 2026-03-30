import json

import croniter
from cron_descriptor import ExpressionDescriptor, Options
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.safestring import mark_safe
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer


# --- Validação de cronjob ---
def validate_cron(value):
    """Valida se a string é uma expressão cron válida."""
    if not croniter.croniter.is_valid(value):
        raise ValidationError(f"'{value}' não é uma expressão cron válida.")


# --- Managers & QuerySets para Soft Delete ---
class GCPQuerySet(models.QuerySet):
    """
    QuerySet customizado para interceptar deleções em massa.
    Garante que Model.objects.filter(...).delete() não remova fisicamente os dados.
    """

    def delete(self):
        # Transforma o delete físico em um update lógico de status
        return super().update(logical_exclusion=True)

    def hard_delete(self):
        # Método de escape para limpeza real do banco de dados quando necessário
        return super().delete()


class GCPManager(models.Manager):
    """
    Manager padrão para filtrar registros ativos.
    Utilizado em todas as consultas padrão do sistema (Objects).
    """

    def get_queryset(self):
        # Filtra automaticamente para omitir registros com exclusão lógica ativa
        return GCPQuerySet(self.model, using=self._db).filter(logical_exclusion=False)


# --- Modelo Base Abstrato ---
class GCPBaseModel(models.Model):
    """
    Arquitetura Base para Ativos GCP.
    Implementa Auditoria, Normalização (Upper) e Soft Delete Recursivo.
    """

    logical_exclusion = models.BooleanField(
        default=False,
        verbose_name="Excluído",
    )
    to_make_exclude = models.BooleanField(
        default=False,
        verbose_name="Solicitar deleção",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de criação",
    )
    update = models.DateTimeField(
        auto_now=True,
        verbose_name="Data de atualização",
    )

    # Manager padrão oculta os deletados; all_objects permite auditoria completa
    objects = GCPManager()
    all_objects = models.Manager()

    # Campos que serão convertidos para MAIÚSCULAS no save()
    UPPER_FIELDS = []
    LOWER_FIELDS = []

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Garante a integridade dos dados (Case-Insensitivity)
        antes da persistência no banco.
        """
        for field in self.UPPER_FIELDS:
            val = getattr(self, field, None)
            if val and isinstance(val, str):
                setattr(self, field, val.upper())
        for field in self.LOWER_FIELDS:
            val = getattr(self, field, None)
            if val and isinstance(val, str):
                setattr(self, field, val.lower())
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Implementa o Soft Delete na instância e propaga para a linhagem descendente.
        """
        self.logical_exclusion = True
        self.save()

        # Percorre os QuerySets de filhos definidos em cada modelo
        for child_queryset in self.get_logical_children():
            # Dispara o GCPQuerySet.delete() em massa para os filhos
            child_queryset.delete()

    def hard_delete(self, *args, **kwargs):
        """Remove fisicamente o registro do banco de dados."""
        super().delete(*args, **kwargs)

    def get_logical_children(self):
        """
        Hook para definição de dependências de linhagem nos modelos filhos.
        """
        return []


# --- Modelos de Negócio ---
class GCPLocation(GCPBaseModel):
    """
    Representa as regiões da GCP (ex: us-central1, southamerica-east1).
    """

    UPPER_FIELDS = ["name"]
    name = models.CharField(max_length=255, unique=True, verbose_name="name")

    class Meta:
        verbose_name = "Localização GCP"
        verbose_name_plural = "Localizações GCP"

    def __str__(self):
        return self.name


class GCPDevProject(GCPBaseModel):
    """
    Entidade de Projetos de Desenvolvimento que consomem os dados da linhagem.
    """

    UPPER_FIELDS = ["name"]
    name = models.CharField(
        max_length=256,
        primary_key=True,
        verbose_name="Nome do Projeto de Desenvolvimento",
    )
    description = models.TextField(
        verbose_name="Descrição do projeto",
    )
    responsable_users = models.ManyToManyField(
        "core.Contato",
        related_name="dev_projects_responsable_users",
        verbose_name="Time da área de negócios",
    )

    class Meta:
        verbose_name = "Projeto de desenvolvimento"
        verbose_name_plural = "Projetos de desenvolvimento"

    def __str__(self):
        return self.name


class GCPProject(GCPBaseModel):
    """
    Representa os Projetos Oficiais da Google Cloud Platform.
    """

    LOWER_FIELDS = ["name"]
    project_id = models.CharField(
        max_length=256,
        unique=True,
        verbose_name="Id do projeto",
    )
    name = models.CharField(
        max_length=256,
        unique=True,
        verbose_name="Nome do Projeto",
    )

    class Meta:
        verbose_name = "Projeto GCP"
        verbose_name_plural = "Projetos GCP"
        unique_together = ("project_id", "name")

    def __str__(self):
        return self.name

    def get_logical_children(self):
        # A deleção de um projeto oculta todos os seus Assets (Datasets/Buckets)
        return [self.assets.all()]


class GCPAsset(GCPBaseModel):
    """
    Contêineres de dados da GCP: Datasets (BigQuery) ou Buckets (GCS).
    """

    ASSET_TYPES = [
        ("BQ", "BigQuery Dataset"),
        ("GCS", "Cloud Storage Bucket"),
    ]
    project = models.ForeignKey(
        GCPProject,
        on_delete=models.CASCADE,
        related_name="assets",
        to_field="name",
    )
    name = models.CharField(
        max_length=256,
        verbose_name="Nome (Dataset/Bucket)",
    )
    asset_types = models.CharField(
        max_length=10,
        choices=ASSET_TYPES,
        verbose_name="Tipo de Ativo",
    )
    location = models.ForeignKey(
        GCPLocation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    uri = models.CharField(
        max_length=512,
        unique=True,
        verbose_name="URI",
    )

    class Meta:
        verbose_name = "Ativo GCP"
        verbose_name_plural = "Ativos GCP"
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project.project_id}.{self.name}" if self.project else self.name

    def get_logical_children(self):
        # A deleção de um Asset oculta todas as Tabelas ou Blobs contidos
        return [self.tables.all()]


class GCPTableBlob(GCPBaseModel):
    """
    Grão mais fino da linhagem: Tabelas, Views ou Arquivos (Blobs).
    """

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
        help_text="Nome do Dataset/Bucket em que está a tabela ou blob.",
    )
    project_dev = models.ManyToManyField(
        GCPDevProject,
        blank=True,
        related_name="tabelas",
        verbose_name="Projetos de desenvolvimento",
        help_text="Projetos que utilizam está fonte",
    )
    table_name = models.CharField(
        max_length=256,
        verbose_name="Nome da Tabela",
        help_text="Nome da tabela (Este campo é chave única composta junto com projeto e dataset/bucket)",
    )
    table_type = models.CharField(
        max_length=50,
        choices=TABLE_TYPES,
        blank=True,
        verbose_name="Tipo",
        help_text="Indica qual o tipo da fonte",
    )
    is_partitioned = models.BooleanField(
        default=False,
        verbose_name="Particionada?",
        help_text="Indica se este item tem particionamento",
    )
    partitions_fields = models.CharField(
        max_length=256,
        blank=True,
        null=True,
        verbose_name="Colunas particionadas",
        help_text="Indica os campos que compõe a partição",
    )
    partitions_found = models.JSONField(
        default=list,
        blank=True,
        null=True,
        verbose_name="Partições Detectadas",
        help_text="Partições encontradas através de importação (JSON)",
    )
    ddl = models.TextField(
        null=True,
        blank=True,
        verbose_name="DDL da tabela",
        help_text="Código DDL de Tabelas do BigQuery",
    )
    metadata_raw = models.JSONField(
        default=dict,
        blank=True,
        null=True,
        help_text="RAW da Importação do Item",
    )
    creation_time = models.DateField(
        null=True,
        blank=True,
        verbose_name="Data de criação",
        help_text="Data de criação do item no Google Cloud",
    )

    class Meta:
        verbose_name = "Tabela/Blob"
        verbose_name_plural = "Tabelas/Blobs"
        unique_together = ("asset", "table_name")

    @property
    def metadata_formatted(self):
        """
        resolution_content: Converte o texto bruto em JSON identado e aplica
        syntax highlighting estilo Monokai (padrão VS Code).
        """
        if not self.metadata_raw:
            return "-"

        try:
            # Garante que o conteúdo é um JSON válido e aplica indentação de 4 espaços
            data = json.loads(self.metadata_raw)
            formatted_json = json.dumps(
                data, indent=4, sort_keys=True, ensure_ascii=False
            )

            # Configura o formatador Pygments. 'noclasses=True' injeta o CSS inline
            # para facilitar a renderização imediata, mas usaremos CSS externo para o container.
            formatter = HtmlFormatter(style="monokai", noclasses=True)
            lexer = JsonLexer()

            return mark_safe(highlight(formatted_json, lexer, formatter))
        except Exception:
            # Fallback caso o conteúdo não seja um JSON válido
            return self.metadata_raw

    def __str__(self):
        return f"{self.asset.name}.{self.table_name}"

    def get_logical_children(self):
        # A deleção de uma tabela oculta processos de ETL onde ela é origem ou destin
        return [self.etls_saida.all(), self.etls_entrada.all()]


class GCPETL(GCPBaseModel):
    """
    Mapeia a movimentação de dados entre Tabelas/Blobs.
    """

    TIPO_CHOICES = [
        ("EXTRACTION", "Extração"),
        ("TRANSFORM", "Transformação"),
        ("LOAD", "Carga"),
    ]

    name = models.CharField(
        max_length=512,
        verbose_name="Processo",
        unique=True,
        blank=True,
    )
    etl_types = models.JSONField(
        default=list,
        verbose_name="Tipos",
    )
    source = models.ManyToManyField(
        GCPTableBlob,
        related_name="etls_saida",
        blank=True,
        verbose_name="Tabela's/Blob's Fontes",
    )
    destin = models.ForeignKey(
        GCPTableBlob,
        on_delete=models.CASCADE,
        related_name="etls_entrada",
        verbose_name="Tabela de destino",
        null=True,
        blank=True,
    )
    cronjob = models.CharField(
        max_length=20,
        validators=[validate_cron],
        help_text="Insira uma expressão cron (ex: 0 5 * * 1)",
        verbose_name="Agendamento (Cron)",
        blank=True,
        null=True,
    )
    creation_time = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Processo ETL"
        verbose_name_plural = "Processos ETL"

    @property
    def cron_description(self):
        if self.cronjob:
            try:
                options = Options()
                options.locale_code = "pt_PT"
                return ExpressionDescriptor(self.cronjob, options=options)
            except Exception:
                return "Expressão inválida"
        return "-"

    def save(self, *args, **kwargs):
        if self.destin and self.destin.asset:
            self.name = f"{self.destin.asset.project.name}.{self.destin.asset.name}.{self.destin.table_name}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
