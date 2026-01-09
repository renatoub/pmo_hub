# pmo_hub\core\views.py
from datetime import timedelta

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
            tarefa.pendencia_data = timezone.now().date()
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
    # Filtrar apenas quem tem data de início para o Gantt não quebrar
    demandas = Demanda.objects.prefetch_related("tarefas").filter(
        data_inicio__isnull=False
    )
    tasks = []

    for d in demandas:
        start_str = d.data_inicio.strftime("%Y-%m-%d")

        # O Gantt exige que 'end' seja estritamente maior que 'start' para desenhar a barra
        if d.data_prazo and d.data_prazo > d.data_inicio:
            end_str = d.data_prazo.strftime("%Y-%m-%d")
        else:
            # Se não houver prazo ou for no mesmo dia, forçamos +1 dia para a barra existir
            end_str = (d.data_inicio + timedelta(days=1)).strftime("%Y-%m-%d")

        tasks.append(
            {
                "id": str(d.id),
                "name": d.titulo,
                "start": start_str,
                "end": end_str,
                "progress": d.progresso_total,  # Agora usa a property com peso de horas
                "custom_class": "bar-demanda",
            }
        )
    return JsonResponse(tasks, safe=False)
