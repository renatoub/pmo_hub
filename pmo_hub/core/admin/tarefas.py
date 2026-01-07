from django.contrib import admin


class TarefasAdmin(admin.ModelAdmin):
    search_fields = ["nome"]
    list_display = ("nome", "pendencia", "get_responsaveis", "concluida", "criado_em")
    readonly_fields = (
        "pendencia",
        "pendencia_data",
        "responsabilidade_pendencia",
        "criado_em",
        "atualizado_em",
    )

    def get_responsaveis(self, obj):
        # Usando 'responsaveis' conforme a melhoria do modelo anterior
        return ", ".join([u.username for u in obj.responsaveis.all()])

    get_responsaveis.short_description = "Responsáveis"
