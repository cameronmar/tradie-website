"""
Management command: python manage.py generate_monthly_invoices

Generates one DRAFT invoice per local pro for all eligible pending platform
fees in a calendar month. Invoices are NOT sent automatically — an admin must
review and send each one from /admin/marketplace/invoice/.

Intended to run on a monthly schedule (e.g. a Railway Cron Job service on the
1st of each month) so draft invoices for the previous month are waiting for
admin review without anyone having to trigger it by hand.
"""
import calendar
from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from marketplace.utils import create_weekly_invoices


class Command(BaseCommand):
    help = (
        'Generate draft invoices for all local pros with pending platform fees '
        'for a calendar month (default: the previous calendar month).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--month', type=str, default=None,
            help='Month to generate for, as YYYY-MM. Defaults to the previous calendar month.',
        )

    def handle(self, *args, **options):
        if options['month']:
            try:
                year, month = (int(part) for part in options['month'].split('-'))
            except ValueError:
                raise CommandError('--month must be in YYYY-MM format, e.g. 2026-06')
        else:
            today = date.today()
            last_day_prev_month = today.replace(day=1) - timedelta(days=1)
            year, month = last_day_prev_month.year, last_day_prev_month.month

        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])

        invoices = create_weekly_invoices(period_start, period_end)

        if invoices:
            total = sum(inv.total_amount for inv in invoices)
            self.stdout.write(self.style.SUCCESS(
                f'Generated {len(invoices)} draft invoice(s) for {period_start} to {period_end} '
                f'(total FJD ${total:.2f}). Review and send from /admin/marketplace/invoice/.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'No local pros had eligible pending fees for {period_start} to {period_end}. '
                f'No invoices were generated.'
            ))
