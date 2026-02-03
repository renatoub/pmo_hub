# pmo_hub/core/models/tarefas.py
from datetime import datetime, timedelta

from django.contrib.auth.models import User
from django.db import models
from django.db.models import Max
from django.utils import timezone
from simple_history.models import HistoricalRecords
from django.template.defaultfilters import date as django_date_filter

from .base import TimeStampedModel
from .demanda import Demanda


class Tarefas(TimeStampedModel):
    CARGA_HORARIA_DIARIA = 8

    class ResponsabilidadeChoices(models.TextChoices):
        INTERNO = "Interno", "Interno"
        EXTERNO = "Externo", "Externo"

    demanda = models.ForeignKey(
        Demanda, on_delete=models.CASCADE, related_name="tarefas"
    )
    nome = models.TextField(max_length=255, blank=False, null=False, verbose_name="Nome da Tarefa")
    descricao = models.TextField(blank=True, verbose_name="Descrição da Tarefa")
    prioridade = models.PositiveIntegerField(
        default=0, blank=False, null=False, verbose_name="Prioridade"
    )
    horas_estimadas = models.PositiveIntegerField(
        default=0, verbose_name="Horas Estimadas"
    )
    resolvida = models.BooleanField(default=False, verbose_name="Pendência Resolvida")
    pendencia = models.TextField(blank=True, verbose_name="Descrição da Pendência")
    responsabilidade_pendencia = models.CharField(
        max_length=10,
        blank=True,
        choices=ResponsabilidadeChoices.choices,
        verbose_name="Responsáveis por concluir a pendência",
    )
    pendencia_data = models.DateTimeField(
        null=True, blank=True, verbose_name="Data da Pendência"
    )
    pendencia_resolvida_em = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Resolução da Pendência"
    )
    responsaveis = models.ManyToManyField(
        User, blank=True, related_name="tarefas_atribuidas"
    )
    concluida = models.BooleanField(default=False, verbose_name="Concluída")
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Data de Criação")
    atualizado_em = models.DateTimeField(
        auto_now=True, verbose_name="Data de Atualização"
    )
    concluido_em = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Conclusão"
    )


    def save(self, *args, **kwargs):
        # 1. Lógica original de Auto-Incremento para novas tarefas
        if not self.prioridade and self.demanda_id and not self.concluida:
            max_prioridade = Tarefas.objects.filter(demanda=self.demanda).aggregate(
                Max("prioridade")
            )["prioridade__max"]
            self.prioridade = (max_prioridade or 0) + 1

        # 2. Lógica original de timestamps e pendências
        if self.pk:
            old_instance = Tarefas.objects.get(pk=self.pk)
            if not old_instance.concluida and self.concluida:
                self.concluido_em = datetime.now()
                if not self.resolvida:
                    self.resolvida = True
                    self.pendencia_resolvida_em = datetime.now()

            if not old_instance.resolvida and self.resolvida:
                if not self.pendencia_resolvida_em:
                    self.pendencia_resolvida_em = datetime.now()

        # 3. Se concluída, força prioridade 0 (sai da lista ordenável)
        if self.concluida:
            self.prioridade = 0

        # Salva a instância atual
        super().save(*args, **kwargs)

        # 4. CRUCIAL: Dispara reordenação dos irmãos pendentes para tapar buracos
        if self.demanda_id:
            self._reordenar_pendentes()

    def get_previsao_entrega(self):
        if self.concluida:
            return django_date_filter(self.concluido_em, "d \d\e F \d\e Y") if self.concluido_em else "Concluída"

        # if Tarefas.objects.prefetch_related("Demanda")

        tarefas_irmas = Tarefas.objects.filter(
            demanda_id=self.demanda_id, 
            concluida=False
        ).order_by('prioridade', 'criado_em')

        data_cursor = timezone.now()
        horas_disponiveis_hoje = self.CARGA_HORARIA_DIARIA

        for tarefa in tarefas_irmas:
            while data_cursor.weekday() >= 5:
                data_cursor += timedelta(days=1)
                horas_disponiveis_hoje = self.CARGA_HORARIA_DIARIA

            horas_restantes_tarefa = tarefa.horas_estimadas

            while horas_restantes_tarefa > 0:
                if horas_disponiveis_hoje <= 0:
                    data_cursor += timedelta(days=1)
                    while data_cursor.weekday() >= 5:
                        data_cursor += timedelta(days=1)
                    horas_disponiveis_hoje = self.CARGA_HORARIA_DIARIA

                consumo = min(horas_restantes_tarefa, horas_disponiveis_hoje)
                horas_restantes_tarefa -= consumo
                horas_disponiveis_hoje -= consumo

            # Se esta for a tarefa que estamos calculando, retorna a data onde o cursor parou
            if tarefa.id == self.id:
                return django_date_filter(data_cursor, "d \d\e F \d\e Y")

        return "-"

    def _reordenar_pendentes(self):
        """Recalcula a prioridade de todas as tarefas NÃO concluídas desta demanda"""
        pendentes = Tarefas.objects.filter(
            demanda_id=self.demanda_id, 
            concluida=False
        ).order_by('prioridade', 'criado_em')

        updates = []
        for index, tarefa in enumerate(pendentes, start=1):
            if tarefa.prioridade != index:
                tarefa.prioridade = index
                updates.append(tarefa)
        
        if updates:
            Tarefas.objects.bulk_update(updates, ['prioridade'])

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"
        ordering = ["prioridade"]

    def __str__(self):
        return self.nome


class Pendencia(models.Model):
    demanda = models.ForeignKey(
        Demanda, on_delete=models.CASCADE, related_name="pendencias"
    )
    descricao = models.TextField()
    resolvida = models.BooleanField(default=False)
    criado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    resolvido_em = models.DateTimeField(null=True, blank=True)
    resolvido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pendencias_resolvidas",
    )

    def __str__(self):
        return f"Pendência em {self.demanda.titulo}"
