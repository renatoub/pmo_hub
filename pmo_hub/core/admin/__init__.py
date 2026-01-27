# pmo_hub/core/admin/__init__.py
from django.contrib import admin

from ..models import (
    AnexoDemanda,
    Contato,
    Demanda,
    ResultadosEsperados,
    Riscos,
    Rotulos,
    Situacao,
    Tarefas,
    Tema,
    TipoAtividade,
)

# Imports das classes Admin
from .auxiliares import (
    AnexoDemandaAdmin,
    AuxiliarAdmin,
    ContatoAdmin,
    RotulosAdmin,
    SituacaoAdmin,
    TemasAdmin,
)
from .demanda_admin import DemandaAdmin
from .tarefas import TarefasAdmin

# Registro unificado
admin.site.register(Rotulos, RotulosAdmin)
admin.site.register(Tarefas, TarefasAdmin)
admin.site.register(Demanda, DemandaAdmin)
admin.site.register(Situacao, SituacaoAdmin)
admin.site.register(Contato, ContatoAdmin)
admin.site.register(AnexoDemanda, AnexoDemandaAdmin)

# Modelos Auxiliares
admin.site.register(Tema, TemasAdmin)
admin.site.register(TipoAtividade, AuxiliarAdmin)
admin.site.register(Riscos, AuxiliarAdmin)
admin.site.register(ResultadosEsperados, AuxiliarAdmin)
