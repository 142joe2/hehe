import django, os, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'caufa_portal.settings'
django.setup()

from django.test import Client
from core_system.auth_utils import create_access_session
from core_system.models import OfficerUser

officer = OfficerUser.objects.filter(role='Auditor').first()
if not officer:
    officer = OfficerUser.objects.create(
        full_name='Test Auditor',
        username='test_auditor_api',
        password_hash='x',
        role='Auditor',
        account_status='Active',
    )

session, token = create_access_session(officer=officer, ip_address='127.0.0.1', device_info='test')

c = Client()
s = c.session
s['access_token'] = token
s['officer_id'] = officer.user_id_PK
s['role'] = officer.role
s.save()

resp = c.get('/api/auditor/approved-aid-posts/')
print(f'Status: {resp.status_code}')
data = json.loads(resp.content)
print(f'ok: {data.get("ok")}')
print(f'posts count: {len(data.get("posts", []))}')
for p in data.get('posts', []):
    print(f'  post_id={p.get("post_id")}, member_name={p.get("member_name")}, aid_type={p.get("aid_type")}')
