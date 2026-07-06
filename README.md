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

## Smoke Test

```bash
python admin_smoke_test.py
```

Checks:
- home page returns 200
- `/healthz/` returns 200
- admin login page is reachable

## Production Environment Variables

Required for production:

- `DJANGO_ENV=production`
- `DEBUG=False`
- `SECRET_KEY=<strong-random-value>`
- `ALLOWED_HOSTS=<comma-separated-hosts>`
- `CSRF_TRUSTED_ORIGINS=<comma-separated-https-origins>`
- `DATABASE_URL=<postgres-connection-url>`

Recommended security env vars (defaults are production-safe):

- `USE_X_FORWARDED_PROTO=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_SSL_REDIRECT=True`
- `SECURE_HSTS_SECONDS=3600`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=False` (set `True` only after confirming all subdomains are HTTPS-ready)
- `SECURE_HSTS_PRELOAD=False`

If `DEBUG=False`, startup fails fast when `SECRET_KEY` or `ALLOWED_HOSTS` are missing.
`SECURE_SSL_REDIRECT=True` requires HTTPS to be correctly configured at the platform/load balancer.

## Deploy on Railway

1. Create a new Railway project from this repo.
2. Set all required env vars above.
3. Use these commands:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn coconut_wireless.wsgi --log-file -`
4. Run after deploy (or as release command if configured):
   ```bash
   python manage.py migrate --noinput
   python manage.py collectstatic --noinput
   ```
5. Configure domain + HTTPS in Railway.

## Deploy on Render

1. Create a **Web Service** from this repo.
2. Set all required env vars above.
3. Configure:
   - **Build command:** `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - **Start command:** `gunicorn coconut_wireless.wsgi --log-file -`
4. Run migrations via Render Shell or deploy hook:
   ```bash
   python manage.py migrate --noinput
   ```
5. Configure custom domain + HTTPS in Render.

## Launch in 24h Checklist

- [ ] Set production env vars (`SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`)
- [ ] Point DNS to Railway/Render service and enable HTTPS
- [ ] Run migrations and collectstatic on production
- [ ] Verify `/`, `/healthz/`, and `/admin/login/` return 200
- [ ] Verify custom error pages (404/500) render with `DEBUG=False`
- [ ] Replace legal placeholder copy with lawyer-reviewed final text
- [ ] Create first production superuser
- [ ] Confirm email provider credentials (if using SMTP)
