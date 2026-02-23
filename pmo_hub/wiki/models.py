# /pmo_hub/wiki/models.py
from django.db import models
from django.utils.text import slugify
from markdownx.models import MarkdownxField

class WikiPage(models.Model):
    title = models.CharField(max_length=255, verbose_name="Título")
    slug = models.SlugField(unique=True, max_length=255, help_text="Gerado automaticamente do título.")
    content = MarkdownxField(verbose_name="Conteúdo Markdown")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title