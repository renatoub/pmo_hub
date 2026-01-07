import os

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

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
        return format_html(
            '<a class="button" href="{}" target="_blank" style="background-color: #28a745; color: white; padding: 5px 15px; border-radius: 20px; text-decoration: none;">📥 DOWNLOAD</a>',
            obj.arquivo.url,
        )

    def demanda_link(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse(
                f"admin:{obj.demanda._meta.app_label}_demanda_change",
                args=[obj.demanda.id],
            ),
            obj.demanda.titulo,
        )

    def nome_arquivo(self, obj):
        return os.path.basename(obj.arquivo.name)


class RotulosAdmin(admin.ModelAdmin):
    form = RotuloForm
    list_display = ("nome", "exibir_cor")
    search_fields = ["nome"]

    def exibir_cor(self, obj):
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; border-radius: 4px; border: 1px solid #000;"></div>',
            obj.cor_hex,
        )

    exibir_cor.short_description = "Cor"
