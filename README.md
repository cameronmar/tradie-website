# Coconut Wireless

Fiji-based marketplace connecting clients with local tradies. Built with Django.

## Quick Start (Local Development)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

App: http://127.0.0.1:8000/  
Admin: http://127.0.0.1:8000/admin/

## CI Quality Gate Expectations

GitHub Actions workflow `.github/workflows/ci.yml` runs on every push and pull request and must pass before merge:

1. `python manage.py check --deploy`
2. `python manage.py migrate --noinput`
3. `python manage.py test`
4. `python admin_smoke_test.py`

## Smoke Test

```bash
python admin_smoke_test.py
```

Checks:
- home page returns 200
- `/healthz/` returns 200
- admin login page is reachable

## Production Environment Variables

| Variable | Required | Purpose / Notes |
|---|---|---|
| `DJANGO_ENV` | Yes | Set to `production` in deployed environments. |
| `DEBUG` | Yes | Must be `False` in production. Startup fails if `DJANGO_ENV=production` and `DEBUG=True`. |
| `SECRET_KEY` | Yes | Strong random value. Startup fails if missing in production. |
| `ALLOWED_HOSTS` | Yes | Comma-separated production hostnames. Startup fails if missing in production. |
| `CSRF_TRUSTED_ORIGINS` | Yes | Comma-separated `https://...` origins for production forms/admin. Startup fails if missing in production. |
| `DATABASE_URL` | Yes (production) | Postgres connection URL in production. SQLite is acceptable for local dev/CI. |
| `USE_X_FORWARDED_PROTO` | Optional | Defaults to `True` in production for hosted proxy TLS. |
| `SESSION_COOKIE_SECURE` | Optional | Defaults to `True` in production. |
| `CSRF_COOKIE_SECURE` | Optional | Defaults to `True` in production. |
| `SECURE_SSL_REDIRECT` | Optional | Defaults to `True` in production. |
| `SECURE_HSTS_SECONDS` | Optional | Defaults to `3600` in production. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | Optional | Defaults to `False`; set `True` only when all subdomains are HTTPS-ready. |
| `SECURE_HSTS_PRELOAD` | Optional | Defaults to `False`; enable only when preload requirements are met. |
| `SENTRY_DSN` | Optional | Enables Sentry error reporting only when provided. |
| `SENTRY_TRACES_SAMPLE_RATE` | Optional | Defaults to `0`. Example: `0.1` for 10% tracing. |

Local defaults remain documented in `.env.example`.

## Deployment Sequence

1. Ensure CI passes on the release commit.
2. Set production env vars in platform (Render/Railway).
3. Deploy application.
4. Run:
   ```bash
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```
5. Validate post-deploy (below).

## Post-Deploy Validation

Run these checks immediately after deploy:

```bash
python manage.py check --deploy
python admin_smoke_test.py
```

Then verify:
- `GET /` returns 200
- `GET /healthz/` returns 200
- `GET /admin/login/` returns 200
- application logs show no startup configuration errors

## Rollback Procedure

1. Re-deploy the last known-good release/version.
2. If schema changes were included, run rollback migration only if it is explicitly safe.
3. Re-run post-deploy validation checks.
4. If incident persists, follow `docs/runbook.md`.

## Deploy on Railway

1. Create a new Railway project from this repo.
2. Set all required env vars above.
3. Railway uses the committed `railway.toml` and `.python-version` files for deploy configuration.
4. Add a Railway Postgres service and link `DATABASE_URL` from the plugin into the web service variables.
5. Railway deploy behavior is:
   - **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Deploy command:** `python manage.py migrate --noinput`
   - **Start command:** `gunicorn coconut_wireless.wsgi --bind 0.0.0.0:$PORT --log-file -`
   - **Health check:** `/healthz/`
6. Configure domain + HTTPS in Railway.
7. Media uploads stored on local disk are ephemeral on Railway and will be lost on restart/redeploy unless you move media storage to an external object store.

## Deploy on Render

1. Create a **Web Service** from this repo.
2. Set all required env vars above.
3. Configure:
   - **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Start command:** `gunicorn coconut_wireless.wsgi --bind 0.0.0.0:$PORT --log-file -`
4. Run migrations:
   ```bash
   python manage.py migrate --noinput
   ```
5. Configure custom domain + HTTPS in Render.
