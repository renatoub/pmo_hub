# seu_app/models/__init__.py
from .auxiliares import (
    Contato,
    ResultadosEsperados,
    Riscos,
    Rotulos,
    Situacao,
    Tema,
    TipoAtividade,
)
from .base import TimeStampedModel
from .demanda import AnexoDemanda, Demanda, upload_anexo_path
from .tarefas import Pendencia, Tarefas
