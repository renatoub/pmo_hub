from django.contrib.auth.models import User
from django.db import models

from .base import TimeStampedModel
from .demanda import Demanda


class Tarefas(TimeStampedModel):
    class ResponsabilidadeChoices(models.TextChoices):
        INTERNO = "Interno", "Interno"
        EXTERNO = "Externo", "Externo"

    demanda = models.ForeignKey(
        Demanda, on_delete=models.CASCADE, related_name="tarefas"
    )
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    pendencia = models.TextField(blank=True, verbose_name="Descrição da Pendência")
    pendencia_data = models.DateField(null=True, blank=True)
    responsabilidade_pendencia = models.CharField(
        max_length=10, blank=True, choices=ResponsabilidadeChoices.choices
    )
    responsaveis = models.ManyToManyField(
        User, blank=True, related_name="tarefas_atribuidas"
    )
    concluida = models.BooleanField(default=False)

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
