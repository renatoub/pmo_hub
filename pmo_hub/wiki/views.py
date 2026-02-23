# /pmo_hub/wiki/views.py
from django.shortcuts import render, get_object_or_404
from .models import WikiPage

def page_detail(request, slug):
    page = get_object_or_404(WikiPage, slug=slug)
    return render(request, 'wiki/page_detail.html', {'page': page})