# /pmo_hub/wiki/templatetags/wiki_tags.py
import markdown
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def render_markdown(text):
    md = markdown.Markdown(extensions=[
        'fenced_code', 
        'codehilite', 
        'tables', 
        'toc'  # Esta extensão gera os IDs nos títulos e o sumário
    ])
    html_content = md.convert(text)
    return {
        'content': mark_safe(html_content),
        'toc': mark_safe(md.toc) # Retorna o HTML da lista de links (UL/LI)
    }