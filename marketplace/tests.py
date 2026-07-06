import json
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.db import DatabaseError
from django.test import TestCase, override_settings


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
)
class CriticalPathViewsTests(TestCase):
    def test_home_page_returns_200(self):
        response = self.client.get('/', secure=True)
        self.assertEqual(response.status_code, 200)

    def test_healthz_returns_200_when_db_is_available(self):
        response = self.client.get('/healthz/', secure=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_healthz_returns_503_when_db_unavailable(self):
        with mock.patch('django.db.connection.cursor', side_effect=DatabaseError('Database connection unavailable')):
            response = self.client.get('/healthz/', secure=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {'status': 'error'})

    def test_admin_login_page_is_reachable(self):
        response = self.client.get('/admin/login/', secure=True)
        self.assertEqual(response.status_code, 200)


class ProductionSettingsTests(TestCase):
    @staticmethod
    def _run_settings_import(extra_env):
        env = os.environ.copy()
        env.update(extra_env)
        return subprocess.run(
            [sys.executable, '-c', 'import coconut_wireless.settings'],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
        )

    def test_production_requires_debug_false(self):
        result = self._run_settings_import(
            {
                'DJANGO_ENV': 'production',
                'DEBUG': 'True',
                'SECRET_KEY': 'x',
                'ALLOWED_HOSTS': 'example.com',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('DEBUG must be False', result.stderr)

    def test_production_requires_secret_key(self):
        result = self._run_settings_import(
            {
                'DJANGO_ENV': 'production',
                'DEBUG': 'False',
                'SECRET_KEY': '',
                'ALLOWED_HOSTS': 'example.com',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY environment variable is required', result.stderr)

    def test_production_requires_allowed_hosts(self):
        result = self._run_settings_import(
            {
                'DJANGO_ENV': 'production',
                'DEBUG': 'False',
                'SECRET_KEY': 'x',
                'ALLOWED_HOSTS': '',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ALLOWED_HOSTS must be set', result.stderr)

    def test_production_requires_csrf_trusted_origins(self):
        result = self._run_settings_import(
            {
                'DJANGO_ENV': 'production',
                'DEBUG': 'False',
                'SECRET_KEY': 'x',
                'ALLOWED_HOSTS': 'example.com',
                'CSRF_TRUSTED_ORIGINS': '',
            }
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CSRF_TRUSTED_ORIGINS must be set', result.stderr)

    def test_production_secure_defaults(self):
        env = os.environ.copy()
        env.update(
            {
                'DJANGO_ENV': 'production',
                'DEBUG': 'False',
                'SECRET_KEY': 'x',
                'ALLOWED_HOSTS': 'example.com',
                'CSRF_TRUSTED_ORIGINS': 'https://example.com',
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                '-c',
                (
                    'import json;'
                    'import coconut_wireless.settings as s;'
                    'print(json.dumps({'
                    '"SESSION_COOKIE_SECURE": s.SESSION_COOKIE_SECURE,'
                    '"CSRF_COOKIE_SECURE": s.CSRF_COOKIE_SECURE,'
                    '"SECURE_SSL_REDIRECT": s.SECURE_SSL_REDIRECT,'
                    '"SECURE_HSTS_SECONDS": s.SECURE_HSTS_SECONDS'
                    '}))'
                ),
            ],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        payload = json.loads(result.stdout.strip())
        self.assertTrue(payload['SESSION_COOKIE_SECURE'])
        self.assertTrue(payload['CSRF_COOKIE_SECURE'])
        self.assertTrue(payload['SECURE_SSL_REDIRECT'])
        self.assertGreater(payload['SECURE_HSTS_SECONDS'], 0)
