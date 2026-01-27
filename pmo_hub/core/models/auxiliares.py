# pmo_hub/core/models/auxiliares.py
import os

from django.db import models


class Tema(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    cor_hex = models.CharField(max_length=7, default="#6c757d", help_text="Ex: #d9534f")

    def __str__(self):
        return self.nome


class TipoAtividade(models.Model):
    nome = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.nome


class Riscos(models.Model):
    nome = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Riscos"

    def __str__(self):
        return self.nome


class ResultadosEsperados(models.Model):
    nome = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = "Resultados Esperados"

    def __str__(self):
        return self.nome


class Situacao(models.Model):
    nome = models.CharField(max_length=100)
    cor_hex = models.CharField(max_length=7, default="#6c757d", help_text="Ex: #d9534f")
    padrao = models.BooleanField(
        default=False,
        help_text="Bucket padrão para novas demandas",
        verbose_name="Padrão",
    )
    pendente = models.BooleanField(
        default=False, help_text="Representa estado 'pendente'"
    )
    proximas_situacoes = models.ManyToManyField(
        "self", symmetrical=False, blank=True, verbose_name="Buckets seguintes"
    )
    fechado = models.BooleanField(
        default=False, help_text="Indica se é um estado final (fechado)"
    )

    class Meta:
        verbose_name = "Bucket"
        verbose_name_plural = "Buckets"

    def __str__(self):
        return self.nome


class Contato(models.Model):
    nome = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.nome


class Rotulos(models.Model):
    nome = models.CharField(max_length=50, unique=True)
    cor_hex = models.CharField(
        max_length=7, default="#6c757d", help_text="Cor em Hexadecimal (ex: #007bff)"
    )

    class Meta:
        verbose_name = "Rótulo"
        verbose_name_plural = "Rótulos"

    def __str__(self):
        return self.nome


def upload_anexo_path(instance, filename):
    return os.path.join("anexos", f"demanda_{instance.demanda.id}", filename)
