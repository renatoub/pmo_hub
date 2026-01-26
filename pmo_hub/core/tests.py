# pmo_hub\core\tests.py
from django.test import TestCase
from django.contrib import admin
from core.models import Tarefas
from core.admin.inlines import TarefasInline
from adminsortable2.admin import SortableInlineAdminMixin


class TestSortableConfiguration(TestCase):
    def test_tarefas_inline_config(self):
        """
        Verify that TarefasInline is correctly configured for sorting.
        """
        # Check inheritance
        self.assertTrue(issubclass(TarefasInline, SortableInlineAdminMixin), 
                        "TarefasInline must inherit from SortableInlineAdminMixin")
        
        # Check ordering field
        self.assertEqual(TarefasInline.default_order_field, "prioridade",
                         "TarefasInline.default_order_field must be 'prioridade'")
        
        # Check model
        self.assertEqual(TarefasInline.model, Tarefas)
