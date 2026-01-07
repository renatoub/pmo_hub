from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from ..models import AnexoDemanda, Demanda, Pendencia, Tarefas
from .forms import AnexoForm


class AnexoDemandaInline(admin.TabularInline):
    model = AnexoDemanda
    form = AnexoForm
    extra = 1
    fields = ["arquivo", "link_download"]
    readonly_fields = ["link_download"]

    def link_download(self, obj):
        if obj.id and obj.arquivo:
            return format_html(
                '<a href="{}" target="_blank">📄 Baixar</a>', obj.arquivo.url
            )
        return "-"


class PendenciaInline(admin.TabularInline):
    model = Pendencia
    extra = 0
    fields = ("descricao", "criado_em", "resolvida", "get_dias")
    readonly_fields = ("descricao", "criado_em", "get_dias")
    can_delete = False

    def get_dias(self, obj):
        if not obj.criado_em:
            return "-"
        fim = (
            obj.resolvido_em if (obj.resolvida and obj.resolvido_em) else timezone.now()
        )
        delta = (fim - obj.criado_em).days
        return f"{delta} dias"

    get_dias.short_description = "Permanência"


class SubitemInline(admin.TabularInline):
    model = Demanda
    extra = 0
    fields = ["tema", "titulo", "situacao", "responsavel", "data_prazo"]
    show_change_link = True


class TarefasInline(admin.TabularInline):
    model = Tarefas
    extra = 0
    fields = ("nome", "descricao", "responsaveis", "pendencia", "concluida")
    readonly_fields = ("pendencia", "pendencia_data", "responsabilidade_pendencia")
    can_delete = False
