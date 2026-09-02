import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'caufa_portal.settings')
django.setup()
from django.urls import get_resolver, reverse

resolver = get_resolver(None)
print('reverse_public_register:', reverse('public_register'))
print('\npatterns:')
for p in resolver.url_patterns:
    pattern = str(p)
    name = getattr(p, 'name', None)
    if 'register' in pattern or name == 'public_register':
        print(repr(pattern), name)
