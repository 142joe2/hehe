import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()
from django.urls import get_resolver, reverse

resolver = get_resolver(None)
print('reverse_public_register:', reverse('public_register'))
print('\npatterns:')
for p in resolver.url_patterns:
    if 'register' in str(p) or 'public_register' in getattr(p, 'name', ''):
        print(repr(str(p)), getattr(p, 'name', None))
