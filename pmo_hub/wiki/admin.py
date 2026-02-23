# /pmo_hub/wiki/admin.py
from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin

from .models import WikiPage


@admin.register(WikiPage)
class WikiPageAdmin(MarkdownxModelAdmin):
    list_display = ("title", "slug", "updated_at")
    prepopulated_fields = {"slug": ("title",)}
    search_fields = ("title", "content")
