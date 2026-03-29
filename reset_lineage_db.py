from django.db import connection
cursor = connection.cursor()
cursor.execute('PRAGMA foreign_keys = OFF')
cursor.execute("DELETE FROM django_migrations WHERE app='lineage'")
tables = [
    'lineage_gcpetl_fontes', 'lineage_gcpetl', 'lineage_gcptable_projetos',
    'lineage_gcptable', 'lineage_gcpasset', 'lineage_gcpproject',
    'lineage_gcplocation', 'lineage_projetodesenvolvimento'
]
for t in tables:
    cursor.execute(f'DROP TABLE IF EXISTS {t}')
cursor.execute('PRAGMA foreign_keys = ON')
print("Reset de tabelas do lineage concluído com sucesso.")
