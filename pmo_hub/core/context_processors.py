# core/context_processors.py
from django.conf import settings


def environment_info(request):
    return {
        "ENV_NAME": getattr(settings, "ENVIRONMENT_NAME", None),
        "ENV_COLOR": getattr(settings, "ENVIRONMENT_COLOR", "#000"),
    }
