# pmo_hub/core/models/tarefas.py
from datetime import datetime

from django.contrib.auth.models import User
from django.db import models
from simple_history.models import HistoricalRecords

from .base import TimeStampedModel
from .demanda import Demanda


class Tarefas(TimeStampedModel):
    class ResponsabilidadeChoices(models.TextChoices):
        INTERNO = "Interno", "Interno"
        EXTERNO = "Externo", "Externo"

    demanda = models.ForeignKey(
        Demanda, on_delete=models.CASCADE, related_name="tarefas"
    )
    nome = models.TextField(max_length=255)
    descricao = models.TextField(blank=True, verbose_name="Descrição da Tarefa")
    pendencia = models.TextField(blank=True, verbose_name="Descrição da Pendência")
    pendencia_data = models.DateTimeField(
        null=True, blank=True, verbose_name="Data da Pendência"
    )
    pendencia_resolvida_em = models.DateTimeField(
        null=True, blank=True, verbose_name="Data de Resolução da Pendência"
    )
    responsabilidade_pendencia = models.CharField(
        max_length=10,
        blank=True,
        choices=ResponsabilidadeChoices.choices,
        verbose_name="Responsáveis por concluir a pendência",
    )
    resolvida = models.BooleanField(default=False, verbose_name="Pendência Resolvida")
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
    horas_estimadas = models.PositiveIntegerField(
        default=0, verbose_name="Horas Estimadas"
    )

    def save(self, *args, **kwargs):
        if self.pk:
            # Busca a versão atual do banco para comparar status
            old_instance = Tarefas.objects.get(pk=self.pk)

            # Se a tarefa foi marcada como concluída AGORA
            if not old_instance.concluida and self.concluida:
                self.concluido_em = datetime.now()

                # Se havia uma pendência aberta, resolve automaticamente
                if not self.resolvida:
                    self.resolvida = True
                    self.pendencia_resolvida_em = datetime.now()

            # Caso a pendência seja marcada como resolvida manualmente (sem concluir a tarefa)
            if not old_instance.resolvida and self.resolvida:
                if not self.pendencia_resolvida_em:
                    self.pendencia_resolvida_em = datetime.now()

        super().save(*args, **kwargs)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Tarefa"
        verbose_name_plural = "Tarefas"

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
