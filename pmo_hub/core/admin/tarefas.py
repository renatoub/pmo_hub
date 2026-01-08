from django.urls import reverse
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin


class TarefasAdmin(SimpleHistoryAdmin):
    search_fields = ("nome", "demanda__titulo")
    list_filter = ("concluida", "criado_em", "demanda__titulo", "responsaveis")
    list_display = (
        "nome",
        "link_demanda",
        "pendencia",
        "concluida",
        "criado_em",
        "concluido_em",
    )
    readonly_fields = (
        "pendencia",
        "pendencia_data",
        "pendencia_resolvida_em",
        "responsabilidade_pendencia",
        "criado_em",
        "atualizado_em",
        "concluido_em",
    )

    def link_demanda(self, obj):
        if obj.demanda:
            url = reverse("admin:core_demanda_change", args=[obj.demanda.id])
            return format_html('<a href="{}">{}</a>', url, obj.demanda.titulo)
        return "Sem demanda"

    link_demanda.short_description = "Demanda"
    link_demanda.admin_order_field = "demanda"

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("demanda")
            .prefetch_related("responsaveis")
        )

    def get_responsaveis(self, obj):
        # Usando 'responsaveis' conforme a melhoria do modelo anterior
        return ", ".join([u.username for u in obj.responsaveis.all()])

    get_responsaveis.short_description = "Responsáveis"
