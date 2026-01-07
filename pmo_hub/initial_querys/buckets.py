from core.models import Situacao

data = {
    "Backlog": "#fd7e14",
    "A fazer": "#007bff",
    "Com impeditivo": "#001f3f",
    "Em validação": "#fffff",
}

for nome, cor in data.items():
    Situacao.objects.get_or_create(nome=nome, defaults={"cor_hex": cor})
