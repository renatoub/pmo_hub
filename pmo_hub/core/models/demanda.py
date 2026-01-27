# pmo_hub/core/models/demanda.py
import os

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from .auxiliares import (
    Contato,
    ResultadosEsperados,
    Riscos,
    Situacao,
    Tema,
    TipoAtividade,
    upload_anexo_path,
)
from .base import TimeStampedModel


class Demanda(TimeStampedModel):
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subitens",
        verbose_name="Demanda Pai",
    )
    titulo = models.CharField(max_length=255, verbose_name="Título")
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    observacao = models.TextField(blank=True, verbose_name="Observação")
    rotulos = models.ManyToManyField(
        "Rotulos", blank=True, verbose_name="Rótulos", related_name="demandas"
    )
    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True)
    temas = models.ManyToManyField(Tema, related_name='temas')
    pmo = models.BooleanField(blank=False, null= False, default=False, verbose_name="Tela PMO")
    tipo = models.ForeignKey(
        TipoAtividade, on_delete=models.SET_NULL, null=True, blank=True
    )
    situacao = models.ForeignKey(
        Situacao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Bucket",
    )
    conclusao = models.TextField(blank=True, verbose_name="Conclusão")
    riscos = models.ManyToManyField(Riscos, blank=True)
    objetivo_geral = models.TextField(blank=True, verbose_name="Objetivo Geral")
    resultados_esperados = models.ManyToManyField(
        ResultadosEsperados, blank=True, verbose_name="Resultados Esperados"
    )

    proximos_passos = models.TextField(blank=True, verbose_name="Próximos Passos")
    dependencias_externas = models.TextField(
        blank=True, verbose_name="Dependências Externas"
    )
    porcentagem_concluida = models.PositiveIntegerField(
        default=0, verbose_name="Porcentagem"
    )

    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandas_responsaveis",
        verbose_name="Responsáveis",
    )
    solicitantes = models.ManyToManyField(
        Contato,
        blank=True,
        related_name="demandas_solicitadas",
        verbose_name="Solicitantes",
    )

    data_inicio = models.DateField(default=timezone.now, verbose_name="Data de Início")
    data_prazo = models.DateField(null=True, blank=True, verbose_name="Data de Prazo")
    data_fechamento = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Fechamento"
    )

    history = HistoricalRecords(
        verbose_name_plural="Históricos", verbose_name="Histórico"
    )

    @property
    def progresso_total(self):
        # Usar 'tarefas' conforme definido no related_name do model Tarefas
        stats = self.tarefas.aggregate(
            total=models.Sum("horas_estimadas"),
            concluidas=models.Sum("horas_estimadas", filter=models.Q(concluida=True)),
        )
        total = stats["total"] or 0
        concluidas = stats["concluidas"] or 0

        if total == 0:
            return 0
        return round((concluidas / total) * 100, 2)

    @property
    def stats_tarefas(self):
        total = self.tarefas.count()
        concluidas = self.tarefas.filter(concluida=True).count()

        # Cálculo por Quantidade
        percent_qtd = (concluidas / total * 100) if total > 0 else 0

        # Cálculo por Horas (já existente no progresso_total)
        percent_horas = self.progresso_total

        return {
            "total": total,
            "concluidas": concluidas,
            "percent_qtd": round(percent_qtd, 1),
            "percent_horas": percent_horas,
        }

    def save(self, *args, **kwargs):
        from .auxiliares import Situacao

        if not self.pk and not self.situacao:
            situacao_padrao = Situacao.objects.filter(padrao=True).first()
            if situacao_padrao:
                self.situacao = situacao_padrao

        if self.situacao:
            if self.situacao.fechado and not self.data_fechamento:
                self.data_fechamento = timezone.now()
        else:
            self.data_fechamento = None

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.tema if self.tema else 'S/T'}: {self.titulo}"


class AnexoDemanda(models.Model):
    demanda = models.ForeignKey(
        Demanda, on_delete=models.CASCADE, related_name="anexos_set"
    )
    arquivo = models.FileField(upload_to=upload_anexo_path)
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Todos os Anexos"

    def __str__(self):
        return os.path.basename(self.arquivo.name)
