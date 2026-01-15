# pmo_hub/core/admin/tarefas.py
from django.contrib import messages
from django.db.models import Q
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, mark_safe
from simple_history.admin import SimpleHistoryAdmin


class TarefasAdmin(SimpleHistoryAdmin):
    search_fields = ("nome", "demanda__titulo")
    list_filter = ("concluida", "criado_em", "demanda__titulo", "responsaveis")
    list_display = (
        "nome",
        "link_demanda",
        "botao_pendencia",
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
    actions = ["concluir_tarefas_em_massa"]

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
        nomes = ", ".join([u.username for u in obj.responsaveis.all()])
        if not nomes:
            return mark_safe('<span class="text-muted">Nenhum</span>')
        return nomes

    get_responsaveis.short_description = "Responsáveis"

    def botao_pendencia(self, obj):
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

        if not obj.pendencia:
            html = f"<a href=\"{url_pending}\" onclick=\"window.open(this.href, 'popup', 'width=600,height=500'); return false;\" "
            html += f'style="color: {icon_color};" title="Registrar Pendência">'
            html += '<i class="fa-solid fa-triangle-exclamation"></i></a>'
        else:
            html = f'<i title="Pendência registrada">{obj.pendencia}</i>'

        return mark_safe(html)

    botao_pendencia.admin_order_field = "pendencia"
    botao_pendencia.short_description = "Pendência"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "timeline/",
                self.admin_site.admin_view(self.timeline_view),
                name="tarefas-timeline",
            ),
        ]
        return custom_urls + urls

    def timeline_view(self, request):
        context = dict(self.admin_site.each_context(request))
        # Passamos a URL da rota que acabamos de criar no urls.py
        context["gantt_data_url"] = "/gantt-data/"
        return TemplateResponse(request, "admin/timeline.html", context)

    def concluir_tarefas_em_massa(self, request, queryset):
        not_concluded = queryset.filter(concluida=True)
        with_pending = queryset.filter(~Q(pendencia=""), resolvida=False)
        for_conclude = queryset.filter(
            (~Q(pendencia="") & Q(resolvida=True) | Q(pendencia="")),
            concluida=False,
        )

        if not_concluded.exists():
            self.message_user(
                request,
                f"{not_concluded.count()} tarefas já estavam concluídas e foram ignoradas.",
                messages.WARNING,
            )
        if with_pending.exists():
            for tarefa in with_pending:
                self.message_user(
                    request,
                    f"Tarefa {tarefa.nome} não pode ser concluída por pendência: {tarefa.pendencia}",
                    messages.ERROR,
                )
        if for_conclude.exists():
            for_conclude.update(concluida=True, concluido_em=timezone.now())
            self.message_user(
                request,
                f"{for_conclude.count()} tarefas concluídas com sucesso.",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                "Nenhuma tarefa pôde ser concluída. Verifique as pendências.",
                messages.INFO,
            )

    concluir_tarefas_em_massa.short_description = "Concluir tarefas selecionadas"
