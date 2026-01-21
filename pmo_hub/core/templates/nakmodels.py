# pmo_hub/core/models/models.py
import os

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

# --- Classes Abstratas ---


class TimeStampedModel(models.Model):
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    atualizado_em = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        abstract = True


# --- Modelos de Apoio (Auxiliares) ---


class Tema(models.Model):
    nome = models.CharField(max_length=100, unique=True)

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
        default=False, help_text="Situação padrão para novas demandas"
    )
    pendente = models.BooleanField(
        default=False, help_text="Representa estado 'pendente'"
    )
    proximas_situacoes = models.ManyToManyField("self", symmetrical=False, blank=True)

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


# --- Modelos Principais ---


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

    tema = models.ForeignKey(Tema, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.ForeignKey(
        TipoAtividade, on_delete=models.SET_NULL, null=True, blank=True
    )
    situacao = models.ForeignKey(
        Situacao, on_delete=models.SET_NULL, null=True, blank=True
    )

    riscos = models.ManyToManyField(Riscos, blank=True)
    objetivo_geral = models.TextField(blank=True)
    resultados_esperados = models.ManyToManyField(ResultadosEsperados, blank=True)

    proximos_passos = models.TextField(blank=True)
    dependencias_externas = models.TextField(blank=True)
    porcentagem_concluida = models.PositiveIntegerField(
        default=0, verbose_name="Porcentagem"
    )

    responsavel = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="demandas_responsaveis",
    )
    solicitantes = models.ManyToManyField(
        Contato, blank=True, related_name="demandas_solicitadas"
    )

    data_inicio = models.DateField(default=timezone.now)
    data_prazo = models.DateField(null=True, blank=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Demanda"

    def __str__(self):
        return f"{self.tema if self.tema else 'S/T'}: {self.titulo}"


def upload_anexo_path(instance, filename):
    return f"anexos/demanda_{instance.demanda.id}/{filename}"


class AnexoDemanda(models.Model):
    demanda = models.ForeignKey(
        Demanda, on_delete=models.CASCADE, related_name="anexos"
    )
    arquivo = models.FileField(upload_to=upload_anexo_path)
    data_upload = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Anexo"
        verbose_name_plural = "Anexos"

    def __str__(self):
        return os.path.basename(self.arquivo.name)


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

    def save(self, *args, **kwargs):
        """Lógica de transição de situação movida para o save (substitui signals)"""
        if self.pk:
            old_status = Pendencia.objects.get(pk=self.pk).resolvida
            if not old_status and self.resolvida:  # Foi resolvida agora
                self.resolvido_em = timezone.now()
                exec_sit = Situacao.objects.filter(nome__icontains="exec").first()
                if exec_sit:
                    Demanda.objects.filter(pk=self.demanda_id).update(
                        situacao=exec_sit, data_fechamento=None
                    )
            elif old_status and not self.resolvida:  # Foi desmarcada
                self.resolvido_em = None
                pend_sit = Situacao.objects.filter(nome__icontains="pend").first()
                if pend_sit:
                    Demanda.objects.filter(pk=self.demanda_id).update(situacao=pend_sit)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pendência: {self.demanda.titulo}"


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
