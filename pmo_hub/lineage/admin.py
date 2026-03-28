import json

from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.html import format_html

from .models import GCPAsset, GCPTable, ProjetoDesenvolvimento, GCPLocation
from .services import (
    ingest_bigquery_metadata,
    ingest_gcs_metadata,
    ingest_tables_metadata,
)


class JsonImportForm(forms.Form):
    import_type = forms.ChoiceField(
        choices=[
            ("assets_bq", "Datasets BigQuery"),
            ("assets_gcs", "Buckets Cloud Storage"),
            ("tables", "Tabelas / Blobs (Metadados Detalhados)"),
        ],
        label="Tipo de Importação",
    )
    json_file = forms.FileField(label="Arquivo JSON")


@admin.register(ProjetoDesenvolvimento)
class ProjetoDesenvolvimentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "descricao")
    search_fields = ("nome",)


@admin.register(GCPLocation)
class GCPLocationAdmin(admin.ModelAdmin):
    list_display = ("nome", "codigo")
    search_fields = ("nome", "codigo")


class GCPTableInline(admin.TabularInline):
    model = GCPTable
    extra = 0
    fields = (
        "table_name",
        "table_type",
        "is_insertable_into",
        "is_typed",
        "projetos",
        "creation_time",
    )
    filter_horizontal = ("projetos",)
    autocomplete_fields = ("projetos",)


@admin.register(GCPTable)
class GCPTablesAdmin(admin.ModelAdmin):
    list_display = (
        "table_name",
        "table_schema",
        "table_catalog",
        "table_type",
        "is_insertable_into",
        "is_typed",
        "creation_time",
    )
    list_filter = ("table_type", "is_insertable_into", "is_typed", "table_schema")
    search_fields = ("table_name", "table_schema", "table_catalog")
    autocomplete_fields = ("projetos",)


@admin.register(GCPAsset)
class GCPAssetAdmin(admin.ModelAdmin):
    list_display = ("name", "project_id", "asset_type", "location", "last_imported_at")
    list_filter = ("project_id", "asset_type", "location")
    search_fields = ("name", "uri", "project_id")
    readonly_fields = (
        "last_imported_at",
        "formatted_labels",
        "formatted_access",
        "formatted_lifecycle",
        "formatted_policies",
    )

    inlines = [GCPTableInline]

    actions = ["generate_report"]
    change_list_template = "admin/lineage/gcpasset_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "import-metadata-file/",
                self.admin_site.admin_view(self.import_metadata_view),
                name="import-gcp-metadata-file",
            ),
        ]
        return custom_urls + urls

    def import_metadata_view(self, request):
        if request.method == "POST":
            form = JsonImportForm(request.POST, request.FILES)
            if form.is_valid():
                import_type = form.cleaned_data["import_type"]
                json_file = request.FILES["json_file"]
                try:
                    data = json.load(json_file)
                    if import_type == "assets_bq":
                        count = ingest_bigquery_metadata(data)
                        self.message_user(
                            request,
                            f"Sucesso: {count} datasets BigQuery importados.",
                            messages.SUCCESS,
                        )
                    elif import_type == "assets_gcs":
                        count = ingest_gcs_metadata(data)
                        self.message_user(
                            request,
                            f"Sucesso: {count} buckets GCS importados.",
                            messages.SUCCESS,
                        )
                    elif import_type == "tables":
                        count = ingest_tables_metadata(data)
                        self.message_user(
                            request,
                            f"Sucesso: {count} tabelas/blobs importados.",
                            messages.SUCCESS,
                        )

                    return redirect("admin:lineage_gcpasset_changelist")
                except Exception as e:
                    self.message_user(
                        request, f"Erro ao processar JSON: {str(e)}", messages.ERROR
                    )
        else:
            form = JsonImportForm()

        context = {
            **self.admin_site.each_context(request),
            "form": form,
            "title": "Importar Metadados via JSON",
        }
        return render(request, "admin/lineage/import_json.html", context)

    fieldsets = (
        (
            "Informações Básicas",
            {"fields": ("uri", "asset_type", "project_id", "name", "location")},
        ),
        (
            "Datas e Auditoria",
            {"fields": ("creation_time", "update_time", "last_imported_at")},
        ),
        (
            "Metadados Estruturados",
            {
                "fields": (
                    "formatted_labels",
                    "formatted_access",
                    "formatted_lifecycle",
                    "formatted_policies",
                ),
                "description": "Visualização amigável dos metadados técnicos do ativo.",
            },
        ),
        (
            "Dados Brutos (JSON)",
            {
                "fields": ("labels", "access_config", "lifecycle_rules", "policies"),
                "classes": ("collapse",),
            },
        ),
    )

    def formatted_json(self, data):
        if not data:
            return "Nenhum dado disponível."
        return format_html(
            '<pre style="background: #f8f9fa; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace;">{}</pre>',
            json.dumps(data, indent=2, ensure_ascii=False),
        )

    def formatted_labels(self, obj):
        return self.formatted_json(obj.labels)

    formatted_labels.short_description = "Labels / Tags"

    def formatted_access(self, obj):
        return self.formatted_json(obj.access_config)

    formatted_access.short_description = "Configuração de Acesso"

    def formatted_lifecycle(self, obj):
        return self.formatted_json(obj.lifecycle_rules)

    formatted_lifecycle.short_description = "Regras de Ciclo de Vida"

    def formatted_policies(self, obj):
        return self.formatted_json(obj.policies)

    formatted_policies.short_description = "Políticas Adicionais"

    def generate_report(self, request, queryset):
        opts = self.model._meta
        context = {
            **self.admin_site.each_context(request),
            "title": "Relatório Técnico de Ativos GCP",
            "assets": queryset,
            "opts": opts,
        }
        return TemplateResponse(request, "admin/lineage/asset_report.html", context)

    generate_report.short_description = "📄 Gerar Relatório de Ativos (Impressão)"
