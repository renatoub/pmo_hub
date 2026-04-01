import random
import re

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    # GCPProject,
    # GCPAsset,
    GCPTableBlob,
)


def get_random_color():
    colors = [
        "#447e9b",
        "#264653",
        "#2a9d8f",
        "#e76f51",
        "#6d597a",
        "#355070",
        "#b56576",
        "#588157",
        "#3d5a80",
        "#98c1d9",
        "#003049",
        "#d62828",
        "#f77f00",
        "#118ab2",
        "#073b4c",
    ]
    return random.choice(colors)


class GCPTableBlobInline(admin.TabularInline):
    """Tabular Inline View for Table Blob register"""

    model = GCPTableBlob
    min_num = 1
    extra = 1
    show_change_link = True
    fields = (
        "table_name",
        "table_type",
        "is_partitioned",
        "display_partitioned_columns",
    )
    readonly_fields = (
        "table_name",
        "table_type",
        "is_partitioned",
        "partitions_fields",
        "display_partitioned_columns",
    )

    @admin.display(description="Colunas particionadas")
    def display_partitioned_columns(self, obj):
        if not obj.partitions_fields or obj.partitions_fields == "[]":
            return "-"

        columns = [
            col.strip()
            for col in re.sub(r"[\[\]']", "", obj.partitions_fields).split(",")
            if col.strip()
        ]

        html = "".join(
            [
                f'<span style="background:{get_random_color()}; color:white; '
                f"padding:2px 6px; border-radius:4px; margin-right:5px; "
                f'display:inline-block; margin-bottom:2px;">{col}</span>'
                for col in columns
            ],
        )
        return format_html("{}", mark_safe(html))
