"""
Lightweight smoke test for launch readiness.

Usage:
    python admin_smoke_test.py
"""
import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'coconut_wireless.settings')

import django
from django.test import Client

django.setup()


def main():
    client = Client()
    checks = [
        ('/', 'Home page'),
        ('/healthz/', 'Health check'),
        ('/admin/login/', 'Admin login page'),
    ]

    failed = False
    print('--- SMOKE TEST REPORT ---')
    for path, label in checks:
        response = client.get(path)
        ok = response.status_code == 200
        print(f'{label}: GET {path} -> {response.status_code}')
        failed = failed or not ok

    print('--- END REPORT ---')
    if failed:
        print('Smoke test failed: one or more checks did not return HTTP 200.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
