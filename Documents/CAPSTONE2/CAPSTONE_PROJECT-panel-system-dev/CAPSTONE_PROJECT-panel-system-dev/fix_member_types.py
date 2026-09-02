#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()

from core_system.models import Member

count = Member.objects.filter(member_type='Officer-Member').update(member_type='Member')
print(f"✓ Updated {count} members from 'Officer-Member' to 'Member'")
