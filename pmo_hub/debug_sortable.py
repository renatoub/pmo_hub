import os
import django

# Setup Django first
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pmo.settings")
django.setup()

from django.conf import settings
from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin import site
from core.models import Demanda, Tarefas
from core.admin.demanda_admin import DemandaAdmin
from core.admin.inlines import TarefasInline

def run():
    # Create a user
    if not User.objects.filter(username="admin").exists():
        user = User.objects.create_superuser("admin", "admin@example.com", "password")
    else:
        user = User.objects.get(username="admin")
    
    # Create a Demanda
    demanda = Demanda.objects.create(titulo="Test Demanda", responsavel=user)
    t = Tarefas.objects.create(demanda=demanda, nome="Tarefa 1", prioridade=1)
    print(f"Tarefas __str__: '{str(t)}'")
    
    # Get the ModelAdmin instance
    # We need to make sure admin is autodiscovered
    # django.setup() does that for installed apps admin.py
    
    model_admin = site._registry.get(Demanda)
    if not model_admin:
        print("DemandaAdmin not registered!")
        return

    # Create a request
    factory = RequestFactory()
    request = factory.get(f"/admin/core/demanda/{demanda.id}/change/")
    request.user = user
    
    # Get the view
    response = model_admin.change_view(request, str(demanda.id))
    response.render()
    
    content = response.content.decode("utf-8")
    
    print("Checking for sortable JS...")
    # These paths depend on django-admin-sortable2 version
    if "adminsortable2" in content:
         print("FOUND: adminsortable2 references in content")
    else:
         print("NOT FOUND: adminsortable2 references in content")

    # Check for inline sortable class
    if "sortable" in content:
        print("FOUND: 'sortable' string in content")
    
    # Check for the sortable handle class
    if "ui-sortable-handle" in content:
        print("FOUND: ui-sortable-handle")
    else:
        print("NOT FOUND: ui-sortable-handle")
        
    # Check for fieldset.sortable
    if 'class="module sortable"' in content or 'class="sortable module"' in content or 'fieldset class="sortable"' in content:
         print("FOUND: fieldset with sortable class (approx check)")
    else:
         print("NOT FOUND: fieldset with sortable class")

    # Check for td.original
    if 'class="original"' in content:
        print("FOUND: td.original")
        # Extract content of td.original
        import re
        # Find the one related to tarefas
        # Looking for input with name starting with tarefas
        
        matches = re.findall(r'<td class="original">(.*?)</td>', content, re.DOTALL)
        found_tarefa = False
        for m in matches:
            if 'name="tarefas' in m:
                print(f"Content of td.original for TAREFAS: {m.strip()}")
                found_tarefa = True
                break
        if not found_tarefa:
             print("Content of td.original for TAREFAS not found")

    else:
        print("NOT FOUND: td.original")

    # Check Media
    print("\nMedia JS:")
    # We need to check the media property of the inline instance or class
    # The ModelAdmin combines its media with inlines' media
    print(model_admin.media._js)

if __name__ == "__main__":
    run()
