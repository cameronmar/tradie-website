# Coconut Wireless

Fiji-based marketplace connecting Clients with Providers / Local Pros.  
Built with Django — an Airtasker-style platform for the Fijian market.

---

## Quick Start (Local Development)

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### Set up environment variables

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY (see note below)
```

Generate a secure secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### Run migrations

```bash
python manage.py migrate
```

### Create a superuser

```bash
python manage.py createsuperuser
```

### Start the server

```bash
python manage.py runserver
```

Visit: http://127.0.0.1:8000/  
Admin: http://127.0.0.1:8000/admin/

---

## Smoke Test

Runs automated checks on admin pages, model counts, and fee calculations:

```bash
python admin_smoke_test.py
```

---

## Project Structure

```
backend/
├── manage.py
├── requirements.txt
├── .env.example          ← copy to .env and fill in values
├── .gitignore
├── coconut_wireless/     ← Django project settings
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── marketplace/          ← main app
    ├── models.py
    ├── views.py
    ├── urls.py
    ├── forms.py
    ├── admin.py
    ├── utils.py
    ├── constants.py
    ├── managers.py
    ├── migrations/
    ├── templates/
    └── templatetags/
```

---

## Deployment Notes

### Environment variables

Set these in your hosting environment (never commit `.env` to Git):

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key — generate a fresh one |
| `DEBUG` | Set to `False` in production |
| `ALLOWED_HOSTS` | Comma-separated list, e.g. `coconutwireless.fj,www.coconutwireless.fj` |
| `EMAIL_BACKEND` | Use SMTP backend in production |
| `EMAIL_HOST` | SMTP host (e.g. `smtp.sendgrid.net`) |
| `EMAIL_HOST_USER` | SMTP username |
| `EMAIL_HOST_PASSWORD` | SMTP password / API key |

### Collect static files (production)

```bash
python manage.py collectstatic --noinput
```

Static files are written to `backend/staticfiles/`. Serve this directory via your web server (nginx, Caddy, etc.) or a CDN.

### Run migrations on deploy

```bash
python manage.py migrate
```

### Database

- **Local / testing:** SQLite (`db.sqlite3`) — already configured, no setup needed.
- **Production:** Use PostgreSQL. Install `psycopg2-binary` and `dj-database-url`, then set `DATABASE_URL` in your environment.

```bash
pip install dj-database-url psycopg2-binary
```

Add to `settings.py`:

```python
import dj_database_url
DATABASES['default'] = dj_database_url.config(conn_max_age=600)
```

### Media files warning

User-uploaded files (provider documents, sponsor banners) are stored in `media/`.  
This directory is **excluded from Git**. In production, store media on an object storage service such as AWS S3, Backblaze B2, or DigitalOcean Spaces.

### Create superuser on first deploy

```bash
python manage.py createsuperuser
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 4.x |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Auth | Custom AbstractUser (email login) |
| File uploads | Django FileField + Pillow |
| Admin | Django Admin (customised) |
| Frontend | Plain HTML / CSS / JS (no framework) |
| Timezone | Pacific/Fiji |

---

## Licence

Proprietary — Coconut Wireless · Fiji · 2026
