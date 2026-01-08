# pmo_hub/core/models/base.py
from django.db import models


class TimeStampedModel(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        abstract = True
        ordering = ["-criado_em"]
        verbose_name = "Demanda"
