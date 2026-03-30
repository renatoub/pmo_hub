# pmo_hub/gcp/models.py
# Autor: Renato Ubaldo Moreira e Moraes
import random
import re

from django import forms
from django.contrib import admin
from django.db.models import Count
from django.shortcuts import redirect, render
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .inlines import GCPTableBlobInline
from .models import (
    GCPETL,
    GCPAsset,
    GCPDevProject,
    GCPLocation,
    GCPProject,
    GCPTableBlob,
)


def get_random_color():
    """Retorna uma cor hexadecimal de uma paleta pré-definida para badges."""
    colors = [
        "#447e9b",
        "#264653",
        "#2a9d8f",
        "#e76f51",
        "#6d597a",
        "#355070",
        "#b56576",
        "#588157",
        "#3d5a80",
        "#98c1d9",
        "#003049",
        "#d62828",
        "#f77f00",
        "#118ab2",
        "#073b4c",
    ]
    return random.choice(
        colors,
    )


class GCPBaseAdmin(admin.ModelAdmin):
    """
    Admin Base com suporte a Soft Delete visual, recursividade de impacto
    e controle de permissões por nível de usuário.
    """

    base_fields = ["to_make_exclude"]
    admin_only_fields = ["logical_exclusion"]

    list_filter = ("to_make_exclude",)

    def get_queryset(self, request):
        """Filtra a listagem para exibir apenas registros não marcados para exclusão."""
        return super().get_queryset(request).filter(logical_exclusion=False)

    def has_delete_permission(self, request, obj=None):
        """Habilita o botão de delete para permitir o fluxo de delete_view customizado."""
        return True

    def delete_view(self, request, object_id, extra_context=None):
        """
        Sobrescreve a view de deleção para processar o Soft Delete recursivo
        e extrair metadados para o template.
        """
        obj = self.get_object(request, object_id)
        if not obj:
            return redirect("admin:index")

        impacted_items_raw = []

        def collect_impact(item):
            children_qsets = item.get_logical_children()
            for qs in children_qsets:
                for child in qs:
                    if not child.to_make_exclude and child not in impacted_items_raw:
                        impacted_items_raw.append(child)
                        collect_impact(child)

        collect_impact(obj)

        # a restrição de acesso a atributos iniciados com underscore no template.
        impacted_items = [
            {
                "repr": str(item),
                "verbose_name": item._meta.verbose_name,
            }
            for item in impacted_items_raw
        ]

        if request.method == "POST":
            obj.delete()
            self.message_user(request, f"'{obj}' ocultado com sucesso.")
            return redirect(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_changelist",
            )

        context = {
            **self.admin_site.each_context(request),
            "object": obj,
            "impacted_items": impacted_items,
            "opts": self.model._meta,
        }
        return render(request, "admin/gcp/delete_confirmation.html", context)

    def get_fields(self, request, obj=None):
        """Remove campos sensíveis da visão de usuários que não são superusuários."""
        all_fields = super().get_fields(request, obj)
        fields_list = list(all_fields) if all_fields else []

        if not getattr(request.user, "is_superuser", False):
            return [f for f in fields_list if f not in self.admin_only_fields]

        return fields_list

    def get_readonly_fields(self, request, obj=None):
        """Trava a edição de campos de controle para usuários comuns."""
        readonly = super().get_readonly_fields(request, obj)

        if not getattr(request.user, "is_superuser", False) and obj.to_make_exclude:
            # Adiciona os campos de controle à lista de apenas-leitura
            return list(readonly) + ["to_make_exclude"]

        return list(readonly)


class GCPProjectForm(forms.ModelForm):
    class Meta:
        model = GCPProject
        fields = "__all__"

    def clean_name(self):
        # resolution_content: Normalização para Upper e validação contra all_objects (incluindo excluídos)
        name = self.cleaned_data.get("name")
        if name:
            name = name.upper()

        existing = (
            GCPProject.all_objects.filter(name=name)
            .exclude(pk=self.instance.pk)
            .first()
        )
        if existing:
            status = "EXCLUÍDO (Soft Delete)" if existing.logical_exclusion else "ATIVO"
            raise forms.ValidationError(
                f"O nome de projeto '{name}' já existe e está com status: {status}."
            )
        return name

    def clean_project_id(self):
        # resolution_content: Validação de unicidade para project_id contra all_objects
        project_id = self.cleaned_data.get("project_id")

        existing = (
            GCPProject.all_objects.filter(project_id=project_id)
            .exclude(pk=self.instance.pk)
            .first()
        )
        if existing:
            status = "EXCLUÍDO (Soft Delete)" if existing.logical_exclusion else "ATIVO"
            raise forms.ValidationError(
                f"O ID de projeto '{project_id}' já está em uso por um registro {status}."
            )
        return project_id


class GCPETLForm(forms.ModelForm):
    etl_types = forms.MultipleChoiceField(
        choices=GCPETL.TIPO_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Tipo",
    )

    class Meta:
        model = GCPETL
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.etl_types:
            self.initial["etl_types"] = self.instance.etl_types


@admin.register(GCPDevProject)
class GCPDevProjectsAdmin(GCPBaseAdmin):
    list_display = (
        "name",
        "to_make_exclude",
        "display_responsibles",
    )
    search_fields = ("name",)
    filter_horizontal = ("responsable_users",)

    @admin.display(
        description="Responsáveis (Negócio)",
    )
    def display_responsibles(self, obj):
        users = obj.responsable_users.all()
        if not users:
            return "-"

        html = "".join(
            [
                f'<span style="background:{get_random_color()}; color:white; padding:2px 6px; '
                f"border-radius:4px; margin-right:5px; font-size:10px; display:inline-block; "
                f'margin-bottom:2px;">{user}</span>'
                for user in users
            ],
        )
        return format_html("{}", mark_safe(html))


@admin.register(GCPLocation)
class GCPLocationAdmin(GCPBaseAdmin):
    list_display = ("name",)

    # @admin.display(description="Ativos Vinculados")
    # def display_projects(self, obj):
    #     project = obj.project.all()
    #     if not project.exists():
    #         return "-"

    #     html = "".join(
    #         [
    #             f'<span style="background:{get_random_color()}; color:white; '
    #             f"padding:2px 6px; border-radius:4px; margin-right:5px; "
    #             f'font-size:10px; display:inline-block; margin-bottom:2px;">{proj.name}</span>'
    #             for proj in project
    #         ],
    #     )
    #     return format_html("{}", mark_safe(html))

    # def get_queryset(self, request):
    #     return super().get_queryset(request).prefetch_related("project")


@admin.register(GCPProject)
class GCPProjectAdmin(GCPBaseAdmin):
    form = GCPProjectForm
    list_display = ("name", "display_assets")

    @admin.display(description="Ativos Vinculados")
    def display_assets(self, obj):
        assets = obj.assets.all()
        if not assets.exists():
            return "-"

        html = "".join(
            [
                f'<span style="background:{get_random_color()}; color:white; '
                f"padding:2px 6px; border-radius:4px; margin-right:5px; "
                f'font-size:10px; display:inline-block; margin-bottom:2px;">{asset.name}</span>'
                for asset in assets
            ],
        )
        return format_html("{}", mark_safe(html))

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("assets")


@admin.register(GCPAsset)
class GCPAssetAdmin(GCPBaseAdmin):
    list_display = (
        "name",
        "location",
        "project",
        "asset_types",
        "display_qnt_tabelas",
    )
    inlines = [GCPTableBlobInline]
    search_fields = (
        "name",
        "project__projeto_id",
    )

    def get_queryset(self, request):
        """
        resolution_content: Uso de annotate para criar um campo virtual 'tables_count'
        no nível do banco de dados, permitindo ordenação real.
        """
        queryset = super().get_queryset(request)
        # Criamos a anotação 'tables_count' realizando o JOIN e COUNT no SQL
        queryset = queryset.annotate(tables_count=Count("tables"))
        return queryset

    @admin.display(description="Qnt. Itens", ordering="tables_count")
    def display_qnt_tabelas(self, obj):
        """
        resolution_content: Acessa o atributo anotado. Se não existir (ex: erro no join),
        faz o fallback para o count individual.
        """
        return getattr(obj, "tables_count", obj.tables.count())

    def get_readonly_fields(self, request, obj=None):
        readonly = super().get_readonly_fields(request, obj)
        if not getattr(request.user, "is_superuser", False):
            return list(readonly) + ["project", "name"]
        return list(readonly)


@admin.register(GCPTableBlob)
class GCPTableBlobAdmin(GCPBaseAdmin):
    list_display = (
        "table_name",
        "asset",
        "table_type",
        "display_dev_projects",
        "display_partitioned_columns",
        "update",
    )
    list_filter = (
        "table_name",
        "asset",
        "table_type",
    )
    readonly_fields = (
        "partitions_found",
        "metadata_formatted",
    )
    # filter_horizontal = ("project_dev",)
    search_fields = ("table_name", "asset__name")
    exclude = ("metadata_raw",)

    @admin.display(description="Projetos de Dev")
    def display_dev_projects(self, obj):
        projects = obj.project_dev.all().values_list("name", flat=True)
        if not projects:
            return "-"

        html = "".join(
            [
                f'<span style="background:{get_random_color()}; color:white; padding:2px 6px; border-radius:4px; margin-right:5px; font-size:10px;">{name}</span>'
                for name in projects
            ],
        )
        return format_html("{}", mark_safe(html))

    @admin.display(description="Metadados (JSON Formated)")
    def metadata_formatted(self, obj):
        # resolution_content: Renderiza o HTML seguro gerado pelo model
        return obj.metadata_formatted

    # Adicionamos um estilo CSS customizado para o bloco de código
    class Media:
        css = {"all": ("css/json_admin.css",)}

    @admin.display(description="Colunas particionadas")
    def display_partitioned_columns(self, obj):
        if not obj.partitions_fields or obj.partitions_fields == "[]":
            return "-"

        columns = [
            col.strip()
            for col in re.sub(r"[\[\]']", "", obj.partitions_fields).split(",")
            if col.strip()
        ]

        html = "".join(
            [
                f'<span style="background:{get_random_color()}; color:white; '
                f"padding:2px 6px; border-radius:4px; margin-right:5px; "
                f'display:inline-block; margin-bottom:2px;">{col}</span>'
                for col in columns
            ],
        )
        return format_html("{}", mark_safe(html))

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("project_dev", "asset")


@admin.register(GCPETL)
class GCPETLAdmin(GCPBaseAdmin):
    form = GCPETLForm

    list_display = (
        "name",
        "destin",
        "display_cron_human",
    )
    readonly_fields = ("name",)
    autocomplete_fields = ("source", "destin")

    # resolution_content: Injeção do JS customizado para o campo cron
    class Media:
        js = ("js/cron_helper.js",)

    @admin.display(description="Descrição do Agendamento")
    def display_cron_human(self, obj):
        return obj.cron_description
