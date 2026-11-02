import os
import sys
from datetime import datetime, date
from decimal import Decimal
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'food_ex.settings')
django.setup()

from django.apps import apps

output_path = os.path.join(os.getcwd(), 'database_data.txt')

app_labels = [
    'accounts',
    'customer',
    'restaurant',
    'delivery',
    'orders',
    'payments',
    'notifications',
    'location',
    'admin',
    'sessions',
    'auth',
]

models = [m for m in apps.get_models() if m._meta.app_label in app_labels]

with open(output_path, 'w', encoding='utf-8') as f:
    f.write('=' * 85 + '\n')
    f.write(' FOOD_EX PROJECT - COMPLETE DATABASE EXPORT\n')
    f.write(f' Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    f.write('=' * 85 + '\n\n')

    f.write('TABLE OF CONTENTS & RECORD COUNTS:\n')
    f.write('-' * 85 + '\n')
    total_records = 0
    model_counts = []
    for model in models:
        try:
            cnt = model.objects.count()
        except Exception as e:
            cnt = f'Error: {e}'
        model_counts.append((model, cnt))
        if isinstance(cnt, int):
            total_records += cnt
        f.write(f'  * {model._meta.label:<38} (Table: {model._meta.db_table:<30}): {cnt} records\n')
    f.write('-' * 85 + '\n')
    f.write(f'TOTAL RECORDS: {total_records}\n\n')

    for model, cnt in model_counts:
        f.write('\n' + '=' * 85 + '\n')
        f.write(f' MODEL: {model._meta.label}  |  DATABASE TABLE: {model._meta.db_table}\n')
        f.write(f' TOTAL RECORDS: {cnt}\n')
        f.write('=' * 85 + '\n')

        if not isinstance(cnt, int) or cnt == 0:
            f.write('  (No records found in this table)\n\n')
            continue

        field_names = [field.name for field in model._meta.fields]
        f.write(f'COLUMNS: {", ".join(field_names)}\n')
        f.write('-' * 85 + '\n')

        for idx, obj in enumerate(model.objects.all(), 1):
            pk_val = getattr(obj, 'pk', 'N/A')
            f.write(f'[{idx}/{cnt}] Record ID: {pk_val}\n')
            for field in model._meta.fields:
                try:
                    val = getattr(obj, field.name, None)
                    if field.name == 'password' and isinstance(val, str) and val.startswith('pbkdf2_'):
                        val = f'[PASSWORD_HASH: {val[:20]}...]'
                    elif isinstance(val, (datetime, date)):
                        val = val.isoformat()
                    elif isinstance(val, Decimal):
                        val = str(val)
                    elif hasattr(val, 'pk'):
                        val = f'ID {val.pk} ({str(val)})'
                except Exception as ex:
                    val = f'<Error reading field: {ex}>'
                f.write(f'    {field.name:<25}: {val}\n')
            f.write('\n')

print(f'Successfully wrote complete database data to {output_path} (Total records: {total_records})')

