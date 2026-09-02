import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
import django
django.setup()
from core_system.models import AccessSession, Member, MedicalAid

print('AccessSession count', AccessSession.objects.count())
for a in AccessSession.objects.select_related('user_id_FK').all()[:20]:
    print('token', a.token_id, 'status', a.session_status, 'revoked', a.revoked_at, 'expires', a.expires_at, 'officer', a.user_id_FK.user_id_PK, getattr(a.user_id_FK, 'full_name', None))

print('Members with pending medical aid and officer:')
for m in Member.objects.filter(medicalaid__status='Pending').distinct()[:20]:
    print('member', m.member_id_PK, getattr(m, 'full_name', None), 'officer', getattr(m.officer_user_id_FK, 'user_id_PK', None))
    for ma in m.medicalaid_set.filter(status='Pending'):
        print('  aid', ma.medical_aid_id_PK, ma.hospital_name, ma.hospital_address, ma.admission_date, ma.discharge_date)
