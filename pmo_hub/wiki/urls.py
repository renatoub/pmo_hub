# /pmo_hub/wiki/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('<slug:slug>/', views.page_detail, name='wiki_page_detail'),
]