#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()

from core_system.models import Member

# Find JAYEM
members = Member.objects.filter(full_name__icontains='JAYEM')
for m in members:
    print(f"Name: {m.full_name}")
    print(f"Employee ID: {m.employee_id}")
    print(f"Member Type: '{m.member_type}'")
    print(f"Officer User ID: {m.officer_user_id_FK_id}")
    print(f"---")

# Also check all members and their types
print("\nAll members:")
all_members = Member.objects.all()
for m in all_members:
    print(f"{m.full_name} - member_type: '{m.member_type}' - officer_id: {m.officer_user_id_FK_id}")
