import os

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html, mark_safe

from .forms import RotuloForm, SituacaoForm


class AuxiliarAdmin(admin.ModelAdmin):
    search_fields = ["nome"]


class SituacaoAdmin(admin.ModelAdmin):
    form = SituacaoForm
    list_display = ("nome", "padrao", "pendente")
    search_fields = ["nome"]


class ContatoAdmin(admin.ModelAdmin):
    search_fields = ["nome", "email"]
    list_display = ("nome", "email")


class AnexoDemandaAdmin(admin.ModelAdmin):
    list_display = ("id", "demanda_link", "nome_arquivo", "data_upload", "baixar")

    def baixar(self, obj):
        # Correção: Verificar se o arquivo existe antes de tentar pegar a URL
        if obj.arquivo and hasattr(obj.arquivo, "url"):
            return format_html(
                '<a class="button" href="{}" target="_blank" style="background-color: #28a745; color: white; padding: 5px 15px; border-radius: 20px; text-decoration: none;">📥 DOWNLOAD</a>',
                obj.arquivo.url,
            )
        return mark_safe('<span class="text-muted">Sem arquivo</span>')

    def demanda_link(self, obj):
        # Correção: Proteção para FK nula e uso de str() no título
        if obj.demanda:
            url = reverse(
                f"admin:{obj.demanda._meta.app_label}_demanda_change",
                args=[obj.demanda.id],
            )
            return format_html('<a href="{}">{}</a>', url, str(obj.demanda.titulo))
        return mark_safe('<span class="text-muted">-</span>')

    def nome_arquivo(self, obj):
        if obj.arquivo:
            return os.path.basename(obj.arquivo.name)
        return "-"

    baixar.short_description = "Baixar"


class RotulosAdmin(admin.ModelAdmin):
    form = RotuloForm
    list_display = ("nome", "exibir_cor")
    search_fields = ["nome"]

    def exibir_cor(self, obj):
        if obj.cor_hex:
            return format_html(
                '<div style="width: 30px; height: 20px; background-color: {}; border-radius: 4px; border: 1px solid #000;"></div>',
                obj.cor_hex,
            )
        return mark_safe(
            '<div style="width: 30px; height: 20px; background-color: #eee; border: 1px dashed #ccc;"></div>'
        )

    exibir_cor.short_description = "Cor"
