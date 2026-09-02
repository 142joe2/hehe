import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'caufa_portal.settings'
import django
django.setup()
from core_system.models import Member
results = Member.objects.filter(email__icontains='government.gov')
for m in results:
    print(f"ID={m.member_id_PK}, name={m.full_name}, email={m.email}")
if not results:
    print("No members with @government.gov email found")
    # Show all unique emails
    all_emails = Member.objects.exclude(email__isnull=True).exclude(email__exact='').values_list('email', flat=True).distinct()[:20]
    for e in all_emails:
        print(f"  email: {e}")
