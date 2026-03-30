# pmo_hub/gcp/views.py
from cron_descriptor import Options, get_description
from django.http import JsonResponse


def get_cron_description(request):
    """Retorna a tradução da expressão cron para texto."""
    cron_expression = request.GET.get("cron", "")
    try:
        options = Options()
        options.locale_code = "pt_BR"
        description = get_description(cron_expression, options=options)
        return JsonResponse({"description": description, "valid": True})
    except Exception:
        return JsonResponse({"description": "Expressão Cron inválida", "valid": False})
