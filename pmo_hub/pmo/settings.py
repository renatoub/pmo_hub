# pmo_hub/pmo/settings.py
import os
from pathlib import Path

from django.utils import html

from pmo import __version__ as APP_VERSION

orig_format_html = html.format_html


def patched_format_html(format_string, *args, **kwargs):
    if not args and not kwargs:
        return html.mark_safe(format_string)
    return orig_format_html(format_string, *args, **kwargs)


html.format_html = patched_format_html

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
ENVIRONMENT = os.getenv("BRANCH", "localhost")

ENVIRONMENT_NAME = (
    "Desenvolvimento"
    if ENVIRONMENT == "dev"
    else "Localhost"
    if ENVIRONMENT == "localhost"
    else None
)
ENVIRONMENT_COLOR = (
    "#28a745"
    if ENVIRONMENT == "dev"
    else "#17a2b8"
    if ENVIRONMENT == "localhost"
    else None
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-+8!lj9_fo5v!r)7o88hp-w4ia6hwr(u9cy_c-^zm-2&2mla_f^"

ALLOWED_HOSTS = [
    "localhost",
    "10.6.6.95",
]


# Application definition

INSTALLED_APPS = [
    "jazzmin",
    "core",
    "simple_history",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "adminsortable2",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pmo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.environment_info",
            ],
        },
    },
]

WSGI_APPLICATION = "pmo.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "pt-br"

TIME_ZONE = "America/Sao_Paulo"

USE_I18N = True

USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

JAZZMIN_SETTINGS = {
    "site_title": "PMO Hub",
    "site_header": "PMO Hub",
    "site_brand": "PMO Hub",
    "custom_css": "css/admin_fix.css",
    # "site_logo": "img/logo.png",
    # "login_logo": "img/logo.png",
    # "site_logo_classes": "img-circle",
    # "site_icon": "img/logo.png",
    # "site_logo_classes": "img-circle",
    "welcome_sign": "Bem-vindo ao PMO Hub - Gerenciamento de core",
    "copyright": f"Equatorial Energia Ltda v{APP_VERSION}",
    "search_model": ["core.Demanda"],
    "user_avatar": None,
    # Links no menu superior
    # "topmenu_links": [
    #     {"name": "Início", "url": "admin:index", "permissions": ["auth.view_user"]},
    #     {"model": "core.Demanda"},
    # ],
    "topmenu_links": [
        {"name": "Início", "url": "admin:index", "permissions": ["auth.view_user"]},
        {
            "name": "Painel PMO",
            "url": "admin:core_demanda_pmo",
        },
        {"name": "Linha do Tempo", "url": "/admin/core/demanda/gantt-view/"},
        {"name": "Dashboard Kanban", "url": "admin:core_demanda_dashboard"},
        {"model": "core.Demanda"},
    ],
    # Menu Lateral
    "show_sidebar": True,
    "navigation_expanded": True,
    "hide_apps": [],
    "hide_models": [],
    # Ícones para os modelos (usando Font Awesome)
    "icons": {
        "auth.Group": "fas fa-users",
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "core.Demanda": "fas fa-tasks",
        "core.Tema": "fas fa-tags",
        "core.Situacao": "fas fa-check-circle",
        "core.TipoAtividade": "fas fa-list",
        "core.Contato": "fas fa-address-book",
    },
    # Configuração de Interface
    "show_ui_builder": True,  # Isso permite que você ajuste o tema em tempo real no painel
    "changeform_format": "horizontal_tabs",  # Organiza os campos em abas se quiser
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": True,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": True,
    "brand_colour": "navbar-white",
    "accent": "accent-primary",
    "navbar": "navbar-white navbar-light",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": True,
    "sidebar_fixed": True,
    "sidebar": "sidebar-light-info",
    "sidebar_nav_small_text": True,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": True,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": True,
    "theme": "simplex",
    "dark_mode_theme": False,
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
    "theme_cls": "flatly",
    "actions_sticky_top": False,
}
