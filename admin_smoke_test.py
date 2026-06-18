"""
Run this script from the `backend` folder to perform automated admin page smoke tests
and basic model/integrity checks.

Usage:
    python admin_smoke_test.py
"""
import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coconut_wireless.settings')
import django
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from marketplace.models import (
    TradeCategory, Task, Quote, PlatformFee, Invoice, InvoiceLine, PublicReview, User
)
from marketplace import utils

User = get_user_model()

report = []

# Ensure superuser exists
admin_email = 'admin@example.fj'
admin_password = 'testpass123'
admin = User.objects.filter(email=admin_email).first()
if not admin:
    try:
        admin = User.objects.create_superuser(email=admin_email, password=admin_password)
        report.append(f'Created superuser {admin_email}')
    except Exception as e:
        report.append(f'Failed to create superuser: {e}')
else:
    report.append(f'Superuser exists: {admin_email}')

# Login via test client
client = Client()
client.force_login(admin)

admin_paths = [
    '/admin/marketplace/invoiceline/add/',
    '/admin/marketplace/invoice/add/',
    '/admin/marketplace/platformfee/add/',
    '/admin/marketplace/quote/add/',
    '/admin/marketplace/task/add/',
    '/admin/marketplace/tradecategory/add/',
    '/admin/marketplace/sponsor/add/',
    '/admin/marketplace/taskphoto/add/',
]

for p in admin_paths:
    try:
        r = client.get(p)
        report.append(f'GET {p} -> {r.status_code}')
    except Exception as e:
        report.append(f'GET {p} -> EXCEPTION: {e}')

# Counts
report.append('Model counts:')
report.append(f'  TradeCategory: {TradeCategory.objects.count()}')
report.append(f'  Task: {Task.objects.count()}')
report.append(f'  Quote: {Quote.objects.count()}')
report.append(f'  PlatformFee: {PlatformFee.objects.count()}')
report.append(f'  Invoice: {Invoice.objects.count()}')
report.append(f'  InvoiceLine: {InvoiceLine.objects.count()}')
report.append(f'  PublicReview: {PublicReview.objects.count()}')

# Fee calc sanity
try:
    rate, cap, fee = utils.calculate_platform_fee(420)
    report.append(f'calculate_platform_fee(420) -> rate={rate}, cap={cap}, fee={fee}')
except Exception as e:
    report.append(f'calculate_platform_fee raised: {e}')

# Platform settings
try:
    ps = utils.get_active_platform_settings()
    report.append(f'Active PlatformSettings: rate={ps.success_fee_rate}, cap={ps.success_fee_cap}, active={ps.active}')
except Exception as e:
    report.append(f'get_active_platform_settings raised: {e}')

# Billing summary for a seeded tradie if present
try:
    rajesh = User.objects.filter(email__icontains('rajesh').first())
except Exception:
    rajesh = None

# safer lookup
raj = User.objects.filter(email='rajesh.kumar@example.fj').first()
if raj:
    try:
        summary = utils.get_tradie_billing_summary(raj)
        report.append(f"Billing summary for {raj.email}: {summary}")
    except Exception as e:
        report.append(f'get_tradie_billing_summary raised: {e}')
else:
    report.append('Rajesh user not found')

# Print report
print('--- SMOKE TEST REPORT ---')
for line in report:
    print(line)
print('--- END REPORT ---')
