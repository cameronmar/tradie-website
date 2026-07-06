# Coconut Wireless Runbook

## Incident Response Basics

1. Confirm scope:
   - Is outage global or partial?
   - Is `/healthz/` failing?
2. Check latest deploy and CI status.
3. Review platform logs for startup/configuration/database errors.
4. Run smoke checks:
   - `/`
   - `/healthz/`
   - `/admin/login/`
5. If `SENTRY_DSN` is configured, inspect Sentry for top exceptions and release markers.

## First-Line Mitigations

- Restart app instance.
- Verify required env vars are set correctly (`DJANGO_ENV`, `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`).
- Verify database availability and credentials.

## Rollback

1. Select the previous known-good deploy in the hosting platform.
2. Redeploy that version.
3. Re-run smoke checks and `python manage.py check --deploy`.
4. Communicate status update and record timeline.

## Escalation

- Escalate persistent data-layer failures immediately.
- Escalate repeated 5xx responses after rollback.
- Open a follow-up issue with:
  - trigger time
  - impact
  - root cause (if known)
  - remediation and prevention actions
