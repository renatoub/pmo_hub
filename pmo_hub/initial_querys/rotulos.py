from core.models import Rotulos

data = {
    "Otimização": "#fd7e14",
    "Engenharia de Dados": "#007bff",
    "Cliente": "#001f3f",
    "Dataset": "#20c997",
    "Pipeline": "#17a2b8",
    "Levantamento de requisitos": "#adb5bd",
    "Governança de Dados": "#343a40",
    "Suporte": "#dc3545",
    "Exportação de Dados": "#6c757d",
    "Pesquisa/Exploração": "#795548",
    "Dashboard": "#e83e8c",
    "Monitoramento": "#ffc107",
    "Gestão": "#51585e",
    "Automação": "#6610f2",
    "Qualidade de Dados": "#28a745",
    "Documentação": "#dee2e6",
}

for nome, cor in data.items():
    Rotulos.objects.get_or_create(nome=nome, defaults={"cor_hex": cor})
