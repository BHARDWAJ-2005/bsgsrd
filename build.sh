#!/usr/bin/env bash
# Production build script for BSG Sangareddy on Render / Railway / similar.
# SAFE: Does NOT clear or reset existing school/student/leader data on redeployment.
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input

# Apply any pending DB schema migrations (never deletes data)
python manage.py migrate

# Seed schools ONLY if none exist yet (first-time deploy only).
# On subsequent deploys this is a safe no-op.
python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bsg_sangareddy.settings')
django.setup()
from enrollment.models import School
if School.objects.count() == 0:
    from django.core.management import call_command
    print('No schools found — running initial school seeding...')
    call_command('load_official_sanctioned_schools')
    print('School seeding complete.')
else:
    print(f'Schools already exist ({School.objects.count()} found). Skipping seed. No data was modified.')
"
