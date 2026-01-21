# pmo_hub/pmo/urls.py
from core.views import (
    adicionar_pendencia_tarefa_view,
    alterar_status_view,
    criar_subatividade_view,
    gantt_data,
    gantt_view,
    registrar_pendencia_view,
    resolver_pendencias_e_alterar_status_view,
)
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView

urlpatterns = [
    # Coloque as ações ANTES do admin ou com um nome bem específico
    path(
        "acoes/status/<int:pk>/<int:situacao_id>/",
        alterar_status_view,
        name="alterar_status",
    ),
    path(
        "demanda/<int:demanda_id>/resolver-pendencias/<int:situacao_id>/",
        resolver_pendencias_e_alterar_status_view,
        name="resolver_pendencias_form",
    ),
    path(
        "demanda/<int:demanda_id>/pendencia/<int:situacao_id>/",
        registrar_pendencia_view,
        name="registrar_pendencia_form",
    ),
    path(
        "acoes/pendencia/<int:tarefa_id>/",
        adicionar_pendencia_tarefa_view,
        name="adicionar_pendencia_tarefa",
    ),
    path(
        "acoes/nova-sub/<int:pk>/", criar_subatividade_view, name="criar_subatividade"
    ),
    # path("gantt-data/", gantt_data, name="gantt_data_json"),
    path("admin/core/demanda/gantt-data/", gantt_data, name="gantt_data_json"),
    path("gantt/", gantt_view, name="gantt_view"),
    path("admin/", admin.site.urls),
    path(
        "",
        RedirectView.as_view(url="admin/", permanent=False),
    ),
    # path("", dashboard_view, name="dashboard"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
