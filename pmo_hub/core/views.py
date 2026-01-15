# pmo_hub\core\views.py
from datetime import datetime, timedelta

from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import UploadForm
from .models import AnexoDemanda, Demanda, Pendencia, Situacao, Tarefas


def upload_arquivos(request, demanda_id=None):
    demanda = None
    if demanda_id:
        demanda = get_object_or_404(Demanda, id=demanda_id)

    if request.method == "POST":
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            arquivos = request.FILES.getlist("arquivos")
            for f in arquivos:
                if demanda:
                    AnexoDemanda.objects.create(demanda=demanda, arquivo=f)
            return render(request, "sucesso.html")
    else:
        form = UploadForm()
    return render(request, "upload.html", {"form": form, "demanda": demanda})


def dashboard_view(request):
    SENHA_MESTRE = "hub123"
    if "logout" in request.GET:
        request.session["auth_dashboard"] = False
        return redirect("dashboard")
    if request.method == "POST":
        if request.POST.get("password") == SENHA_MESTRE:
            request.session["auth_dashboard"] = True
        else:
            return render(
                request, "core/login_dashboard.html", {"error": "Senha incorreta!"}
            )

    if not request.session.get("auth_dashboard"):
        return render(request, "core/login_dashboard.html")

    hoje = timezone.now().date()
    todas_demandas = (
        Demanda.objects.all()
        .select_related("situacao", "responsavel")
        .order_by("-criado_em")
    )

    for d in todas_demandas:
        if not d.data_prazo:
            d.status_prazo, d.cor_prazo = "Sem Prazo", "secondary"
        elif d.data_prazo < hoje:
            d.status_prazo, d.cor_prazo = "Atrasado", "danger"
        else:
            d.status_prazo, d.cor_prazo = "No Prazo", "success"

    desired_order = ["Backlog", "Priorizada", "Em execução", "No Farol", "Finalizado"]
    all_situacoes = list(Situacao.objects.all())
    situacoes = [
        s
        for name in desired_order
        for s in all_situacoes
        if s.nome.lower() == name.lower()
    ]
    situacoes += [s for s in all_situacoes if s not in situacoes]

    kanban_data = {
        sit: [d for d in todas_demandas if d.situacao_id == sit.id] for sit in situacoes
    }
    sit_data = Demanda.objects.values("situacao__nome", "situacao__cor_hex").annotate(
        total=Count("id")
    )
    tema_data = Demanda.objects.values("tema").annotate(total=Count("id"))

    context = {
        "kanban_data": kanban_data,
        "demandas": todas_demandas,
        "hoje": hoje,
        "labels_situacao": [
            item["situacao__nome"] or "Sem Situação" for item in sit_data
        ],
        "counts_situacao": [item["total"] for item in sit_data],
        "cores_situacao": [item["situacao__cor_hex"] or "#bdc3c7" for item in sit_data],
        "labels_tema": [item["tema"] for item in tema_data],
        "counts_tema": [item["total"] for item in tema_data],
    }
    return render(request, "core/dashboard.html", context)


def alterar_status_view(request, pk, situacao_id):
    d = get_object_or_404(Demanda, pk=pk)
    target = get_object_or_404(Situacao, pk=situacao_id)

    if target.pendente:
        if request.method == "POST":
            desc = request.POST.get("pendencia_descricao", "").strip()
            d.situacao = target
            d.save()
            if desc:
                Pendencia.objects.create(
                    demanda=d, descricao=desc, criado_por=request.user, resolvida=False
                )

            return render(request, "core/pendencia_form.html", {"msg_sucesso": True})

        return render(
            request,
            "core/pendencia_form.html",
            {"demanda": d, "target": target, "action_url": request.path},
        )

    d.situacao = target
    d.save()

    Pendencia.objects.filter(demanda=d, resolvida=False).update(
        resolvida=True, resolvido_em=timezone.now(), resolvido_por=request.user
    )

    return redirect(request.META.get("HTTP_REFERER", "dashboard"))


def adicionar_pendencia_tarefa_view(request, tarefa_id):
    tarefa = get_object_or_404(Tarefas, pk=tarefa_id)

    if request.method == "POST":
        descricao = request.POST.get("pendencia_descricao", "").strip()
        responsabilidade = request.POST.get("responsabilidade", "Interno")

        if descricao:
            # 1. Atualiza os campos de texto e data
            tarefa.pendencia = descricao
            tarefa.pendencia_data = timezone.now()
            tarefa.responsabilidade_pendencia = responsabilidade
            tarefa.resolvida = False
            tarefa.concluida = False
            tarefa.save()  # Salva primeiro os campos simples

            # 2. Adiciona o usuário atual aos responsáveis (ManyToMany)
            # O método .add() não sobrescreve os atuais, apenas inclui o novo
            if request.user.is_authenticated:
                tarefa.responsaveis.add(request.user)

            return render(
                request, "core/pendencia_tarefa_form.html", {"msg_sucesso": True}
            )

    return render(
        request,
        "core/pendencia_tarefa_form.html",
        {"tarefa": tarefa, "choices": Tarefas.ResponsabilidadeChoices.choices},
    )


def criar_subatividade_view(request, pk):
    pai = get_object_or_404(Demanda, pk=pk)
    url = reverse("admin:core_demanda_add")
    params = f"?parent={pai.id}&tema={pai.tema.id if pai.tema else ''}"
    return redirect(url + params)


def gantt_data(request):
    # Captura datas do filtro vindas da URL (enviadas pelo JS do template)
    str_inicio = request.GET.get("data_inicio")
    str_fim = request.GET.get("data_fim")

    # Base do QuerySet com prefetch para performance
    queryset = Demanda.objects.prefetch_related(
        "rotulos", "tarefas__responsaveis"
    ).filter(data_inicio__isnull=False)

    # Filtro de Interseção: Garante que demandas que começaram antes mas terminam dentro
    # ou após o período sejam incluídas.
    if str_inicio and str_fim:
        try:
            d_start = datetime.strptime(str_inicio, "%Y-%m-%d").date()
            d_end = datetime.strptime(str_fim, "%Y-%m-%d").date()
            queryset = queryset.filter(data_inicio__lte=d_end, data_prazo__gte=d_start)
        except ValueError:
            pass

    tasks = []
    for demanda in queryset:
        # Coleta consolidada de responsáveis das tarefas (sem duplicatas)
        resp_map = {}
        for tarefa in demanda.tarefas.all():
            for resp in tarefa.responsaveis.all():
                resp_map[resp.username] = resp.username

        # Formatação de datas
        start_str = demanda.data_inicio.strftime("%Y-%m-%d")
        end_date = (
            demanda.data_prazo
            if demanda.data_prazo and demanda.data_prazo > demanda.data_inicio
            else (demanda.data_inicio + timedelta(days=1))
        )
        end_str = end_date.strftime("%Y-%m-%d")

        # Define classe de cor baseada no progresso
        c_class = "bar-done" if demanda.progresso_total >= 100 else "bar-demanda"

        tasks.append(
            {
                "id": str(demanda.id),
                "name": demanda.titulo,
                "rotulos": [
                    {"nome": r.nome, "cor": r.cor_hex} for r in demanda.rotulos.all()
                ],
                "responsaveis": list(resp_map.values()),
                "tema": demanda.tema.nome if demanda.tema else "Sem Tema",
                "start": start_str,
                "end": end_str,
                "progress": demanda.progresso_total,
                "custom_class": c_class,
            }
        )

    return JsonResponse(tasks, safe=False)


def gantt_view(request):
    return render(request, "core/gantt.html")
