#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()

from core_system.models import Member

# Fix all members - set member_type to "Member" for those who aren't explicitly "Officer-Member"
members = Member.objects.all()
updated = 0

for m in members:
    # Skip if already set to "Officer-Member"
    if m.member_type and m.member_type.lower() == "officer-member":
        continue
    
    # Set to Member for all others
    old_type = m.member_type
    if m.member_type != "Member":
        m.member_type = "Member"
        m.save(update_fields=['member_type'])
        updated += 1
        print(f"Updated {m.full_name} from '{old_type}' to 'Member'")

print(f"\n✓ Total updated: {updated}")
