"""
Create missing TradeCategory records from TRADE_CHOICES without touching other data.
Run from backend folder:
    python create_categories.py
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coconut_wireless.settings')
import django
django.setup()

from marketplace.constants import TRADE_CHOICES
from marketplace.models import TradeCategory

created = []
for slug, label in TRADE_CHOICES:
    name = label.split(' ', 1)[-1] if ' ' in label else label
    icon = label[0]
    obj, created_flag = TradeCategory.objects.get_or_create(slug=slug, defaults={'name': name, 'icon': icon})
    if created_flag:
        created.append(slug)

if created:
    print('Created categories:', ', '.join(created))
else:
    print('No new categories were created.')
