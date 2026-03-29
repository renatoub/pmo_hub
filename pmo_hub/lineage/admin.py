import json
from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import path
from django.utils.html import format_html
from django.http import JsonResponse

from .models import (
    GCPProject, GCPAsset, GCPTable, ProjetoDesenvolvimento, 
    GCPLocation, GCPETL
)
from .services import ingest_bigquery_metadata, ingest_gcs_metadata, ingest_tables_metadata

class LineageBaseAdmin(admin.ModelAdmin):
    list_filter = ("marcado_para_exclusao_fisica",)
    def get_queryset(self, request):
        return super().get_queryset(request).filter(excluido_logicamente=False)
    def has_delete_permission(self, request, obj=None): return True
    
    def delete_view(self, request, object_id, extra_context=None):
        obj = self.get_object(request, object_id)
        if not obj: return redirect('admin:index')
        impacted_items = []
        def collect_impact(item):
            children = item.get_logical_children()
            for child in children:
                if not child.excluido_logicamente and child not in impacted_items:
                    impacted_items.append(child)
                    collect_impact(child)
        collect_impact(obj)
        if request.method == 'POST':
            obj.delete()
            self.message_user(request, f"'{obj}' ocultado com sucesso.")
            return redirect(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_changelist")
        context = {**self.admin_site.each_context(request), "object": obj, "impacted_items": impacted_items, "opts": self.model._meta}
        return render(request, "admin/lineage/delete_confirmation.html", context)

@admin.register(GCPProject)
class GCPProjectAdmin(LineageBaseAdmin):
    list_display = ("project_id", "display_name", "marcado_para_exclusao_fisica")
    search_fields = ("project_id", "display_name")

@admin.register(ProjetoDesenvolvimento)
class ProjetoDesenvolvimentoAdmin(LineageBaseAdmin):
    list_display = ("nome", "marcado_para_exclusao_fisica")
    search_fields = ("nome",)

@admin.register(GCPLocation)
class GCPLocationAdmin(LineageBaseAdmin):
    list_display = ("nome", "codigo")

class GCPETLForm(forms.ModelForm):
    tipos_etl = forms.MultipleChoiceField(
        choices=GCPETL.TIPO_CHOICES, widget=forms.CheckboxSelectMultiple, required=False
    )
    class Meta:
        model = GCPETL
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.tipos_etl:
            self.initial['tipos_etl'] = self.instance.tipos_etl

@admin.register(GCPETL)
class GCPETLAdmin(LineageBaseAdmin):
    form = GCPETLForm
    list_display = ("nome_processo", "destino", "marcado_para_exclusao_fisica")
    readonly_fields = ("nome_processo",)
    autocomplete_fields = ("fontes", "destino")

@admin.register(GCPAsset)
class GCPAssetAdmin(LineageBaseAdmin):
    list_display = ("name", "project", "asset_type", "location")
    list_filter = ("project", "asset_type", "location", "marcado_para_exclusao_fisica")
    search_fields = ("name", "project__project_id")

class GCPTableForm(forms.ModelForm):
    project = forms.ModelChoiceField(queryset=GCPProject.objects.all(), label="Projeto GCP", required=False)
    class Meta:
        model = GCPTable
        fields = '__all__'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.asset:
            self.initial['project'] = self.instance.asset.project

@admin.register(GCPTable)
class GCPTablesAdmin(LineageBaseAdmin):
    form = GCPTableForm
    list_display = ("table_name", "get_asset_name", "get_project_id", "table_type", "view_lineage_link", "is_partitioned")
    list_filter = ("asset__project", "table_type", "is_partitioned", "marcado_para_exclusao_fisica")
    search_fields = ("table_name", "asset__name")
    
    def get_project_id(self, obj): return obj.asset.project.project_id if obj.asset else "-"
    get_project_id.short_description = "Projeto"
    def get_asset_name(self, obj): return obj.asset.name if obj.asset else "-"
    get_asset_name.short_description = "Dataset/Bucket"

    def view_lineage_link(self, obj):
        return format_html('<a class="btn btn-sm btn-primary" href="lineage-view/"><i class="fas fa-sitemap"></i></a>')
    view_lineage_link.short_description = "Linhagem"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("<path:object_id>/lineage-view/", self.admin_site.admin_view(self.table_lineage_view), name="gcptable_lineage_view"),
            path("global-map-view/", self.admin_site.admin_view(self.global_lineage_view), name="gcptable_global_map"),
            path("ajax/load-assets/", self.admin_site.admin_view(self.load_assets), name="ajax_load_assets"),
        ]
        return custom_urls + urls

    def load_assets(self, request):
        project_id = request.GET.get('project_id')
        assets = GCPAsset.objects.filter(project_id=project_id).values('id', 'name')
        return JsonResponse(list(assets), safe=False)

    class Media:
        js = ("admin/js/vendor/jquery/jquery.js", "lineage/js/chained_assets.js")

    def table_lineage_view(self, request, object_id):
        target_table = get_object_or_404(GCPTable, id=object_id)
        def get_nodes(table, direction, depth):
            if depth <= 0: return []
            nodes = []
            if direction == 'parents':
                etls = table.etls_entrada.filter(excluido_logicamente=False)
                for etl in etls:
                    for f in etl.fontes.all():
                        nodes.append({'table': f, 'etl': etl, 'parents': get_nodes(f, 'parents', depth - 1)})
            else:
                etls = table.etls_saida.filter(excluido_logicamente=False)
                for etl in etls:
                    if etl.destino:
                        nodes.append({'table': etl.destino, 'etl': etl, 'children': get_nodes(etl.destino, 'children', depth - 1)})
            return nodes

        context = {
            **self.admin_site.each_context(request),
            "title": f"Linhagem: {target_table.table_name}",
            "target": target_table,
            "parents": get_nodes(target_table, 'parents', 2),
            "children": get_nodes(target_table, 'children', 2),
        }
        return render(request, "admin/lineage/table_lineage.html", context)

    def global_lineage_view(self, request):
        etls = GCPETL.objects.filter(excluido_logicamente=False).prefetch_related('fontes').select_related('destino')
        return render(request, "admin/lineage/global_lineage.html", {**self.admin_site.each_context(request), "etls": etls})
