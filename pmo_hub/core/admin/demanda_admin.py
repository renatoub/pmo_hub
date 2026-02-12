# pmo_hub/core/admin/demanda_admin.py

import json
import random
from datetime import date, datetime, timedelta

from adminsortable2.admin import SortableAdminBase
from django.contrib import messages
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.models import User
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Max, Prefetch, Q
from django.shortcuts import redirect, render
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from simple_history.admin import SimpleHistoryAdmin

from ..models import AnexoDemanda, Demanda, Pendencia, Situacao, Tarefas, Tema
from .forms import DemandaForm
from .inlines import (
    AnexoDemandaInline,
    SubitemInline,
    TarefasInline,
)


class ResponsavelTarefaFilter(SimpleListFilter):
    title = "Responsável por Tarefa"  # Nome que aparece na barra lateral
    parameter_name = "resp_tarefa"  # Parâmetro na URL

    def lookups(self, request, model_admin):
        # Retorna a lista de usuários que estão atribuídos a pelo menos uma tarefa
        users = (
            User.objects.filter(tarefas_atribuidas__isnull=False)
            .distinct()
            .order_by("first_name", "username")
        )
        return [(user.id, user.get_full_name() or user.username) for user in users]

    def queryset(self, request, queryset):
        # Filtra as demandas que possuem tarefas onde o usuário selecionado está presente
        if self.value():
            return queryset.filter(tarefas__responsaveis__id=self.value()).distinct()
        return queryset


class DemandaAdmin(SortableAdminBase, SimpleHistoryAdmin):
    form = DemandaForm
    inlines = [
        SubitemInline,
        AnexoDemandaInline,
        TarefasInline,
    ]
    list_display = (
        "titulo_expansivel",
        "exibir_tema",
        "status_tag",
        "status_prazo_tag",
        "get_responsaveis",
        "acoes_rapidas",
        "exibir_rotulos",
        "progresso_total",
        "tarefas",
        "data_prazo",
    )
    list_filter = ("tema", "situacao", ResponsavelTarefaFilter, "rotulos")
    filter_horizontal = ("solicitantes",)
    search_fields = ("titulo", "descricao")
    autocomplete_fields = ["parent", "responsavel", "solicitantes", "rotulos"]
    readonly_fields = ["data_fechamento", "get_responsaveis", "situacao"]
    actions = ["definir_situacao_em_massa"]
    save_on_top = True

    fieldsets = (
        (
            "Principal",
            {
                "fields": (
                    "titulo",
                    "parent",
                    "tema",
                    "tipo",
                    "situacao",
                    "pmo",
                    "rotulos",
                )
            },
        ),
        ("Pessoas", {"fields": ("get_responsaveis", "solicitantes")}),
        (
            "Detalhes",
            {
                "fields": (
                    "descricao",
                    "observacao",
                    # "riscos",
                    "objetivo_geral",
                    # "resultados_esperados",
                    "proximos_passos",
                    "conclusao",
                    # "dependencias_externas",
                    # "porcentagem_concluida",
                )
            },
        ),
        ("Datas", {"fields": ("data_inicio", "data_prazo", "data_fechamento")}),
    )

    def titulo_expansivel(self, obj):
        return format_html(
            '<div class="wrapper-demanda">'
            '<span class="toggle-icon" style="cursor:pointer; display:inline-block; transition: transform 0.2s;">▶</span> '
            "<strong>{}</strong>"
            '<div class="desc-content" style="display:none; padding: 10px; background: #f9f9f9; border-left: 3px solid #79aec8; margin-top:5px;">'
            "{}"
            "</div>"
            "</div>",
            obj.titulo,
            obj.descricao or "Sem descrição.",
        )

    titulo_expansivel.short_description = "Demanda"

    def tarefas(self, obj):
        total = obj.tarefas.count()
        concluidas = obj.tarefas.filter(concluida=True).count()
        return f"{concluidas}/{total}" if total else "-"

    tarefas.short_description = "Tarefas"

    def get_queryset(self, request):
        # 1. Carrega o queryset base
        qs = super().get_queryset(request)

        # 2. Otimiza chaves estrangeiras diretas da Demanda
        qs = qs.select_related("tema", "situacao", "responsavel")

        # 3. Otimiza ManyToMany e Relações Reversas (Rótulos e Tarefas)
        return qs.prefetch_related(
            "rotulos",
            Prefetch(
                "tarefas",
                queryset=Tarefas.objects.prefetch_related(
                    Prefetch(
                        "responsaveis",
                        queryset=User.objects.only("first_name", "username"),
                    )
                ),
            ),
        )

    def get_responsaveis(self, obj):
        """
        Exibe os responsáveis de todas as tarefas associadas a esta demanda.
        Usa set comprehension para não repetir nomes.
        """
        cores_hex = [
            "#e74c3c",
            "#27ae60",
            "#2980b9",
            "#8e44ad",
            "#f39c12",
            "#d35400",
            "#16a085",
            "#2c3e50",
            "#c0392b",
            "#27ae60",
            "#34495e",
        ]
        responsaveis = []
        for t in obj.tarefas.all():
            for r in t.responsaveis.all():
                if r.first_name in responsaveis or r.username in responsaveis:
                    continue
                else:
                    responsaveis.append(r.first_name or r.username)

        responsaveis_html = []
        for resp in responsaveis:
            responsaveis_html.append(
                format_html(
                    '<span class="tag-rotulo" style="background-color: {};">{}</span>',
                    random.choice(cores_hex),
                    resp,
                )
            )

        # nomes = {
        #     u.first_name or u.username
        #     for t in obj.tarefas.all()
        #     for u in t.responsaveis.all()
        # }

        if not responsaveis_html:
            return "-"

        # Retorna os nomes em ordem alfabética separados por vírgula
        return mark_safe(" ".join(sorted(responsaveis_html)))

    get_responsaveis.short_description = "Responsáveis das Tarefas"

    def exibir_tema(self, obj):
        if obj.tema:
            return format_html(
                '<span class="tag-rotulo" style="background-color: {};">{}</span>',
                obj.tema.cor_hex,
                obj.tema.nome,
            )
        return "-"

    exibir_tema.short_description = "Tema"
    exibir_tema.admin_order_field = "tema__nome"

    def exibir_rotulos(self, obj):
        tags_html = []
        for rotulo in obj.rotulos.all():
            tags_html.append(
                format_html(
                    '<span class="tag-rotulo" style="background-color: {};">{}</span>',
                    rotulo.cor_hex,
                    rotulo.nome,
                )
            )
        return mark_safe("".join(tags_html)) if tags_html else "-"

    exibir_rotulos.short_description = "Rótulos"

    def get_riscos(self, obj):
        return ", ".join([r.nome for r in obj.riscos.all()])

    get_riscos.short_description = "Riscos"

    def get_resultados_esperados(self, obj):
        return ", ".join([r.nome for r in obj.resultados_esperados.all()])

    get_resultados_esperados.short_description = "Resultados Esperados"

    def definir_situacao_em_massa(self, request, queryset):
        # Se o usuário apenas clicou no botão sem selecionar uma situação (via formulário intermediário)
        if "post" in request.POST:
            situacao_id = request.POST.get("situacao_destino")
            if situacao_id:
                # Verificação de segurança: garantir que a situação escolhida não é pendente
                sit_escolhida = Situacao.objects.get(pk=situacao_id)
                if sit_escolhida.pendente:
                    self.message_user(
                        request,
                        "Erro: Não é permitido mover para situação Pendente via ação em massa.",
                        messages.ERROR,
                    )
                    return

                count = queryset.update(situacao_id=situacao_id)
                self.message_user(
                    request,
                    f"{count} demandas atualizadas para {sit_escolhida.nome}.",
                    messages.SUCCESS,
                )
                return

        # Filtra situações disponíveis (removendo as marcadas como pendente)
        situacoes_validas = Situacao.objects.exclude(pendente=True).order_by("nome")

        context = {
            "demandas": queryset,
            "situacoes": situacoes_validas,
            "action": request.POST.get("action"),
            "select_across": request.POST.get("select_across") == "1",
            "index": request.POST.get("index"),
        }

        # Renderiza uma página intermediária de confirmação para escolher a situação
        return render(request, "admin/core/definir_situacao_massa.html", context)

    definir_situacao_em_massa.short_description = (
        "Alterar Situação dos selecionados (Exceto Pendente)"
    )

    def status_tag(self, obj):
        if not obj.situacao:
            return "-"
        return format_html(
            '<span class="tag-rotulo" style="background-color: {};">{}</span>',
            obj.situacao.cor_hex,
            obj.situacao.nome,
        )

    status_tag.admin_order_field = "situacao__nome"
    status_tag.short_description = "Bucket"

    def status_prazo_tag(self, obj):
        if not obj.data_prazo:
            return "-"
        atrasado = (
            obj.data_prazo < timezone.now().date()
            if obj.data_fechamento is None
            else obj.data_prazo < obj.data_fechamento.date()
        )
        cor = (
            "#e74c3c"
            if atrasado
            else "#27ae60"
            if obj.data_fechamento is None
            else "#2980b9"
        )
        txt = (
            "Fora do Prazo"
            if atrasado and obj.data_fechamento is None
            else "No Prazo"
            if obj.data_fechamento is None
            else "Finalizado no Prazo"
            if not atrasado
            else "Finalizado Fora do Prazo"
        )
        return format_html('<strong style="color: {};">{}</strong>', cor, txt)

    status_prazo_tag.admin_order_field = "data_prazo"
    status_prazo_tag.short_description = "Status do Prazo"

    def changelist_view(self, request, extra_context=None):
        # Guardamos o request atual para usar no método acoes_rapidas
        self._current_request = request
        return super().changelist_view(request, extra_context)

    def acoes_rapidas(self, obj):
        usuario_logado = self._current_request.user if self._current_request else None
        id_do_usuario = usuario_logado.id if usuario_logado else None
        html = []

        # 1. Botão + Sub
        html.append(
            format_html(
                '<a class="btn" href="{}" style="background:#17a2b8; display: inline-block; color:white; padding:2px 5px; font-size:10px; margin-right:3px; border-radius:3px; text-decoration:none;">+ Sub</a>',
                reverse("criar_subatividade", args=[obj.pk]),
            )
        )

        # 2. Botão Assumir
        if obj.responsavel_id != id_do_usuario:
            assumir_url = reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_assumir",
                args=[obj.pk],
            )
            html.append(
                format_html(
                    '<a class="btn" href="{}" style="background:#28a745; display: inline-block; color:white; padding:2px 5px; font-size:10px; margin-right:3px; border-radius:3px; text-decoration:none;">Assumir</a>',
                    assumir_url,
                )
            )

        # 3. Lógica de Transição
        situacao_atual_pendente = obj.situacao.pendente if obj.situacao else False

        if obj.situacao:
            for proxima in obj.situacao.proximas_situacoes.all():
                abrir_em_popup = False

                # CASO A: Indo PARA uma situação de pendência
                if proxima.pendente:
                    url = reverse("registrar_pendencia_form", args=[obj.pk, proxima.id])
                    estilo = "white-space: nowrap !important; border:1px solid #ffc107; color:#856404; background:#fff3cd;"
                    abrir_em_popup = True

                # CASO B: Saindo DE uma pendência
                elif situacao_atual_pendente:
                    tem_tarefas_travadas = (
                        obj.tarefas.filter(resolvida=False)
                        .exclude(pendencia="")
                        .exists()
                    )
                    if tem_tarefas_travadas:
                        url = reverse(
                            "resolver_pendencias_form", args=[obj.pk, proxima.id]
                        )
                        estilo = "white-space: nowrap !important; border:1px solid #28a745; color:#155724; background:#d4edda;"
                        abrir_em_popup = True
                    else:
                        url = reverse("alterar_status", args=[obj.pk, proxima.id])
                        estilo = "white-space: nowrap !important; border:1px solid #ccc; color:#666; background:#f8f9fa;"

                # CASO C: Transição normal
                else:
                    url = reverse("alterar_status", args=[obj.pk, proxima.id])
                    estilo = "white-space: nowrap !important; border:1px solid #ccc; color:#666; background:#fff;"

                # Gerar o atributo JS apenas se necessário
                js_popup = (
                    "onclick=\"window.open(this.href, 'popup', 'width=600,height=550,scrollbars=yes'); return false;\""
                    if abrir_em_popup
                    else ""
                )

                html.append(
                    format_html(
                        '<a href="{}" {} '
                        'style="font-size:10px; padding:1px 4px; border-radius:3px; text-decoration:none; margin-right:2px; {}">'
                        "{}</a>",
                        url,
                        mark_safe(js_popup),
                        estilo,
                        proxima.nome,
                    )
                )

        return mark_safe(" ".join(html))

    acoes_rapidas.short_description = "Ações"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/assumir/",
                self.admin_site.admin_view(self.assumir_demanda),
                name="core_demanda_assumir",
            ),
            path(
                "dashboard/",
                self.admin_site.admin_view(self.admin_dashboard),
                name="core_demanda_dashboard",
            ),
            path(
                "dashboard-pmo/",
                self.admin_site.admin_view(self.kanban_dashboard_view),
                name="core_demanda_dashboard",
            ),
            path(
                "pmo/",
                self.admin_site.admin_view(self.pmo_view),
                name="core_demanda_pmo",
            ),
            # path(
            #     "gantt-data/",
            #     self.admin_site.admin_view(self.get_gantt_data),
            #     name="demanda-gantt-data",
            # ),
            path(
                "gantt-view/",
                self.admin_site.admin_view(self.gantt_view),
                name="demanda-gantt-view",
            ),
        ]

        return custom_urls + urls

    def kanban_dashboard_view(self, request):
        # Lógica original extraída do seu views.py
        hoje = timezone.now().date()

        # Prefetch de rótulos e tarefas para evitar centenas de queries no banco (N+1)
        todas_demandas = (
            Demanda.objects.all()
            .select_related("situacao", "responsavel", "tema")
            .prefetch_related("rotulos", "tarefas")
            .order_by("-criado_em")
        )

        # Ordenação das colunas do Kanban
        desired_order = [
            "Backlog",
            "Priorizada",
            "Em execução",
            "No Farol",
            "Finalizado",
        ]
        all_situacoes = list(Situacao.objects.all())
        situacoes = [
            s
            for name in desired_order
            for s in all_situacoes
            if s.nome.lower() == name.lower()
        ]
        situacoes += [s for s in all_situacoes if s not in situacoes]

        kanban_data = {
            sit: [d for d in todas_demandas if d.situacao_id == sit.id]
            for sit in situacoes
        }

        # Dados para Gráficos
        sit_data = Demanda.objects.values(
            "situacao__nome", "situacao__cor_hex"
        ).annotate(total=Count("id"))
        tema_data = Demanda.objects.values("tema__nome").annotate(total=Count("id"))

        context = {
            **self.admin_site.each_context(
                request
            ),  # Inclui variáveis do Jazzmin/Admin
            "title": "Dashboard Estratégico",
            "kanban_data": kanban_data,
            "demandas": todas_demandas,
            "hoje": hoje,
            "labels_situacao": [
                item["situacao__nome"] or "Sem Situação" for item in sit_data
            ],
            "counts_situacao": [item["total"] for item in sit_data],
            "cores_situacao": [
                item["situacao__cor_hex"] or "#bdc3c7" for item in sit_data
            ],
            "labels_tema": [item["tema__nome"] or "Sem Tema" for item in tema_data],
            "counts_tema": [item["total"] for item in tema_data],
        }
        return TemplateResponse(request, "admin/core/dashboard_pmo.html", context)

    # def get_gantt_data(self, request):
    #     # Filtra demandas que possuem data de início e prazo
    #     queryset = Demanda.objects.exclude(
    #         data_prazo__isnull=True
    #     ).order_status_by_date()  # ou seu queryset padrão

    #     data = []
    #     for d in queryset:
    #         data.append(
    #             {
    #                 "id": str(d.id),
    #                 "name": d.titulo,
    #                 "start": d.data_inicio.isoformat(),
    #                 "end": d.data_prazo.isoformat(),
    #                 "progress": d.situacao,
    #                 "buckets": d.return_buckets,
    #                 "type": str(d.tipo.nome) if d.tipo else "N/A",
    #                 "custom_class": self._get_status_class(d.situacao),
    #             }
    #         )
    #     return JsonResponse(data, safe=False)

    def _get_status_class(self, situacao):
        # Mapeia sua situação para classes CSS do Tailwind/Custom
        if not situacao:
            return "bar-default"
        if situacao.fechado:
            return "bar-done"
        return "bar-progress"

    def gantt_view(self, request):
        hoje = timezone.now().date()
        padrao_inicio = hoje - timedelta(days=hoje.weekday())
        padrao_fim = padrao_inicio + timedelta(days=13)

        str_inicio = request.GET.get("data_inicio")
        str_fim = request.GET.get("data_fim")

        try:
            start_date = (
                datetime.strptime(str_inicio, "%Y-%m-%d").date()
                if str_inicio
                else padrao_inicio
            )
            end_date = (
                datetime.strptime(str_fim, "%Y-%m-%d").date() if str_fim else padrao_fim
            )
        except ValueError:
            start_date, end_date = padrao_inicio, padrao_fim

        delta_days = (end_date - start_date).days + 1
        if delta_days <= 0:
            delta_days = 1

        # --- COLETA DE DADOS PARA O JS ---
        # Buscamos as demandas que se sobrepõem ao período visualizado
        queryset = Demanda.objects.filter(
            data_inicio__lte=end_date, data_prazo__gte=start_date
        ).prefetch_related("rotulos", "situacao", "tema", "tarefas__responsaveis")

        gantt_data = []
        for d in queryset:
            # Extração de responsáveis únicos das tarefas
            resps = []
            for t in d.tarefas.all():
                for r in t.responsaveis.all():
                    nome = r.first_name or r.username
                    if {"nome": nome} not in resps:
                        resps.append({"nome": nome})

            # Cálculo de progresso (concluídas/total)
            tarefas_lista = d.tarefas.all()
            total_t = len(tarefas_lista)
            concluidas = sum(1 for t in tarefas_lista if t.concluida)
            progresso = int((concluidas / total_t) * 100) if total_t > 0 else 0

            gantt_data.append(
                {
                    "id": d.id,
                    "name": d.titulo,
                    "admin_url": reverse(
                        f"admin:{d._meta.app_label}_{d._meta.model_name}_change",
                        args=[d.pk],
                    ),
                    "start": d.data_inicio.isoformat()
                    if d.data_inicio
                    else d.criado_em.date().isoformat(),
                    "end": d.data_prazo.isoformat()
                    if d.data_prazo
                    else d.data_inicio.isoformat(),
                    "progress": progresso,
                    "tema": d.tema.nome if d.tema else "Sem Tema",
                    "bucket": d.situacao.nome if d.situacao else "Sem Bucket",
                    "custom_class": self._get_status_class(d.situacao),
                    "rotulos": [
                        {"nome": r.nome, "cor": r.cor_hex} for r in d.rotulos.all()
                    ],
                    "responsaveis": resps,
                }
            )

        context = {
            **self.admin_site.each_context(request),
            "title": "Gantt Personalizado",
            "start_iso": start_date.isoformat(),
            "end_iso": end_date.isoformat(),
            "delta_days": delta_days,
            "hoje_iso": hoje.isoformat(),
            "gantt_data_json": json.dumps(
                gantt_data, cls=DjangoJSONEncoder
            ),  # Dados serializados para o JS
        }
        return TemplateResponse(request, "admin/gantt_view.html", context)

    def pmo_view(self, request):
        ano_corrente = 2026
        data_minima = date(ano_corrente, 1, 1)  # Início do ano atual

        temas_ids = request.GET.getlist("temas")

        # Query base
        queryset = (
            Demanda.objects.select_related("tema", "responsavel")
            .prefetch_related("riscos")
            .filter(
                Q(data_prazo__year=ano_corrente) | Q(data_inicio__year=ano_corrente)
            )
        )

        if temas_ids:
            queryset = queryset.filter(tema_id__in=temas_ids)

        demandas = queryset.all()

        # Cálculo da data máxima dinâmica
        # Pega o maior valor entre data_prazo e data_fechamento
        datas = queryset.aggregate(
            max_prazo=Max("data_prazo"), max_fechamento=Max("data_fechamento")
        )

        # Lógica para definir a maior data final entre as duas colunas
        max_p = datas["max_prazo"]
        max_f = datas["max_fechamento"].date() if datas["max_fechamento"] else None

        data_maxima = max_p if max_p else data_minima
        if max_f and max_f > data_maxima:
            data_maxima = max_f

        context = {
            **self.admin_site.each_context(request),
            "demandas_globais": demandas,
            "data_min_js": data_minima.strftime("%Y, %m-1, %d"),
            "data_max_js": data_maxima.strftime("%Y, %m-1, %d"),
            "todos_temas": Tema.objects.all().order_by("nome"),
            "temas_selecionados": temas_ids,
        }
        return render(request, "admin/core/pmo.html", context)

    def assumir_demanda(self, request, pk):
        obj = self.get_object(request, pk)
        if obj:
            obj.responsavel = request.user
            obj.save()
            self.message_user(
                request, f"Você assumiu a demanda: {obj.titulo}", messages.SUCCESS
            )
        return redirect(reverse("admin:core_demanda_changelist"))

    def admin_dashboard(self, request):
        return render(request, "admin/core/demanda_dashboard.html")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        desc = form.cleaned_data.get("pendencia_descricao")

        if not Situacao.objects.filter(padrao=True).exists():
            self.message_user(
                request,
                "Aviso: Nenhum bucket foi configurado como padrão.",
                messages.WARNING,
            )

        if desc:
            Pendencia.objects.create(
                demanda=obj, descricao=desc, criado_por=request.user
            )

    def save_formset(self, request, form, formset, change):
        if formset.model == AnexoDemanda:
            instances = formset.save(commit=False)

            for obj in formset.deleted_objects:
                obj.delete()

            for i, inline_form in enumerate(formset.forms):
                if inline_form in formset.deleted_forms:
                    continue

                files = request.FILES.getlist(f"{formset.prefix}-{i}-arquivo")

                if files:
                    instance = inline_form.instance
                    if not instance.demanda_id:
                        instance.demanda = form.instance

                    instance.arquivo = files[0]
                    instance.save()
                    if instance not in formset.new_objects:
                        formset.new_objects.append(instance)

                    for f in files[1:]:
                        novo_anexo = AnexoDemanda.objects.create(
                            demanda=form.instance, arquivo=f
                        )
                        formset.new_objects.append(novo_anexo)
                else:
                    if inline_form.instance.pk and inline_form.has_changed():
                        inline_form.save()
        else:
            super().save_formset(request, form, formset, change)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        # CSS Forçado para corrigir Jazzmin + Sortable
        extra_context["css_fix_sortable"] = """
            <style>
                /* Garante que o container de arrastar tenha tamanho */
                .ui-sortable-handle {
                    display: inline-block !important;
                    width: 20px !important;
                    height: 20px !important;
                    background-color: #ddd !important; /* Fundo cinza para teste */
                    cursor: move !important;
                    text-align: center;
                    margin-right: 5px;
                }
                /* Adiciona um caractere caso a imagem falhe */
                .ui-sortable-handle:after {
                    content: "☰";
                    color: #333;
                    font-weight: bold;
                    line-height: 20px;
                }
                /* Garante que a coluna da prioridade seja visível */
                td.field-prioridade {
                    white-space: nowrap !important;
                    min-width: 50px !important;
                    text-align: left !important;
                }
            </style>
        """
        return super().change_view(request, object_id, form_url, extra_context)

    class Media:
        css = {
            "all": (
                "css/custom_admin.css",
                "css/admin_fix.css",
            )
        }

        js = (
            # Pequeno hack para garantir que o CSS seja aplicado após o carregamento da página
            "admin/js/jquery.init.js",
            "js/toggle_demanda.js",
        )
