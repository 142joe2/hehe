#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()

from core_system.models import Member

# Check all distinct member_type values
members = Member.objects.values('member_type').distinct()
print("Current member_type values in database:")
for m in members:
    count = Member.objects.filter(member_type=m['member_type']).count()
    print(f"  - '{m['member_type']}': {count} members")
