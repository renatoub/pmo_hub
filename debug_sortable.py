
import os
import sys
import django

# Setup Django environment
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'pmo_hub'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pmo.settings')
django.setup()

# IMPORTANTE: Usar 'core' e não 'pmo_hub.core' para bater com INSTALLED_APPS = ['core']
from core.admin.inlines import TarefasInline
from core.admin.demanda_admin import DemandaAdmin
from core.models import Tarefas
from django.contrib.admin import site
from adminsortable2.admin import SortableInlineAdminMixin

print("\n" + "="*50)
print("DIAGNÓSTICO DO SORTABLE INLINE")
print("="*50 + "\n")

# 1. Verificar Herança
print(f"1. Herança de TarefasInline:")
bases = TarefasInline.__bases__
print(f"   Bases: {bases}")
if SortableInlineAdminMixin in bases:
    print("   [OK] Herda de SortableInlineAdminMixin")
else:
    print("   [CRÍTICO] NÃO herda de SortableInlineAdminMixin corretamente!")

# 2. Verificar Campos Readonly
print(f"\n2. Verificação de 'readonly_fields':")
# Instanciar para ver o valor final (pode ser dinâmico)
try:
    inline_instance = TarefasInline(DemandaAdmin.model, site)
    ro_fields = inline_instance.get_readonly_fields(None)
    print(f"   Campos Readonly: {ro_fields}")
    
    if 'prioridade' in ro_fields:
        print("   [FALHA] 'prioridade' ESTÁ em readonly_fields. Isso impede a ordenação.")
    else:
        print("   [OK] 'prioridade' NÃO está em readonly_fields.")
except Exception as e:
    print(f"   [ERRO] Ao instanciar inline: {e}")

# 3. Verificar Configuração de Ordenação
print(f"\n3. Configuração de Ordenação:")
default_order = getattr(TarefasInline, 'default_order_field', None)
print(f"   default_order_field: {default_order}")

# 4. Verificar Media (JS/CSS)
print(f"\n4. Assets (Media):")
try:
    media = inline_instance.media
    print(f"   JS: {media._js}")
    print(f"   CSS: {media._css}")
    
    has_sortable_js = any('adminsortable2' in str(js) or 'sortable' in str(js) for js in media._js)
    if has_sortable_js:
        print("   [OK] Scripts do adminsortable2 detectados.")
    else:
        print("   [ALERTA] Scripts do adminsortable2 NÃO encontrados na media do inline.")
except Exception as e:
    print(f"   [ERRO] Ao verificar media: {e}")

print("\n" + "="*50)
