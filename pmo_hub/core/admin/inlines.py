# pmo_hub/core/admin/inlines.py
import os

from adminsortable2.admin import (
    SortableInlineAdminMixin,
)
from django.contrib import admin
from django.db import models
from django.forms import Textarea
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from ..models import AnexoDemanda, Demanda, Pendencia, Tarefas
from .forms import AnexoForm


class AnexoDemandaInline(admin.TabularInline):
    model = AnexoDemanda
    form = AnexoForm
    extra = 1
    fields = ["nome_arquivo", "arquivo"]
    readonly_fields = ["nome_arquivo"]

    def nome_arquivo(self, obj):
        if obj.id and obj.arquivo:
            return format_html(
                '<a href="{}" target="_blank">{}</a>',
                obj.arquivo.url,
                os.path.basename(obj.arquivo.name),
            )
        else:
            return mark_safe("-")


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


class TarefasInline(SortableInlineAdminMixin, admin.TabularInline):
    model = Tarefas
    extra = 0
    default_order_field = "prioridade"

    template = "admin/core/tarefas/tabular_custom.html"

    fields = (
        "nome",
        "responsaveis",
        "get_priority_display",
        "horas_estimadas",
        "concluida",
        "edit_tarefas",
    )

    readonly_fields = (
        "get_priority_display",
        "edit_tarefas",
    )
    can_delete = False

    formfield_overrides = {
        models.TextField: {
            "widget": Textarea(attrs={"rows": 2, "style": "resize:true;"})
        },
    }

    # LÓGICA DO FILTRO
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Se NÃO tiver o parâmetro show_all_tasks=1, filtra os concluídos fora
        if request.GET.get("show_all_tasks") != "1":
            qs = qs.filter(concluida=False)
        return qs

    def get_priority_display(self, obj):
        # Mostra "-" para itens concluídos (prioridade 0) visualmente
        if obj.prioridade == 0:
            return "-"
        return obj.prioridade

    get_priority_display.short_description = "Prioridade"
    get_priority_display.admin_order_field = "prioridade"

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        # Remove o botão de '+' do campo responsaveis
        if "responsaveis" in formset.form.base_fields:
            formset.form.base_fields["responsaveis"].widget.can_add_related = False
        return formset

    def edit_tarefas(self, obj):
        if not obj or not obj.pk:
            return mark_safe(
                '<i class="fa-solid fa-pen-to-square" style="color: #ccc;"></i>'
            )

        url_change = reverse("admin:core_tarefas_change", args=[obj.pk])
        url_pending = reverse("adicionar_pendencia_tarefa", args=[obj.pk])

        # Se já existir pendência e não estiver resolvida, destaca o ícone
        icon_color = "#ffbf00"  # Amarelo padrão
        if obj.pendencia and not obj.resolvida:
            icon_color = "#d33"  # Vermelho se houver pendência ativa

        if obj.pendencia:
            pendencia_html = f'<i class="fa-solid fa-triangle-exclamation" title="{obj.pendencia}" style="color: {icon_color};"></i>'
        else:
            pendencia_html = f"<a href=\"{url_pending}\" onclick=\"window.open(this.href, 'popup', 'width=600,height=500'); return false;\" "
            pendencia_html += (
                f'style="color: {icon_color};" title="Registrar pendência">'
            )
            pendencia_html += '<i class="fa-solid fa-triangle-exclamation"></i></a>'

        return format_html(
            '<a href="{}" style="color: #2196F3; margin-right: 12px;" title="Editar completa">'
            '<i class="fa-solid fa-pen-to-square"></i></a>{}',
            url_change,
            mark_safe(pendencia_html),
        )

    edit_tarefas.short_description = "Ações rápidas"
