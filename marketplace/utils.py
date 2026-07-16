"""
Utility functions for platform fees, invoicing, and business logic.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction

from .models import (
    PlatformSettings, PlatformFee, Invoice, InvoiceLine, InvoiceNotification, Quote, Task,
    PlatformNotice, User,
)


def get_active_platform_settings():
    """Get the active platform settings."""
    return PlatformSettings.get_active()


def calculate_platform_fee(job_value, settings=None):
    """
    Calculate platform fee based on job value and active settings.
    
    Returns: (fee_rate, fee_cap, calculated_fee)
    """
    if settings is None:
        settings = get_active_platform_settings()
    
    if not settings:
        return Decimal('0'), Decimal('0'), Decimal('0')
    
    large_threshold = Decimal(str(settings.large_job_threshold))
    success_rate = Decimal(str(settings.success_fee_rate))
    large_rate = Decimal(str(settings.large_job_fee_rate))
    fee_cap = Decimal(str(settings.success_fee_cap))

    if job_value > large_threshold:
        fee_rate = large_rate
        calculated_fee = (job_value * fee_rate) / Decimal('100')
    else:
        fee_rate = success_rate
        calculated_fee = (job_value * fee_rate) / Decimal('100')
        if calculated_fee > fee_cap:
            calculated_fee = fee_cap

    return fee_rate, fee_cap, calculated_fee


def calculate_quote_with_platform_fee(base_price, settings=None):
    """
    When tradie includes platform fee in quote, calculate what client sees.
    
    Returns: {
        'base_price': base_price,
        'fee_rate': fee_rate,
        'fee_cap': fee_cap,
        'estimated_platform_fee': estimated_fee,
        'client_quote_total': client_sees,
    }
    """
    if settings is None:
        settings = get_active_platform_settings()
    
    if not settings:
        return None
    
    success_rate = Decimal(str(settings.success_fee_rate))
    fee_cap = Decimal(str(settings.success_fee_cap))
    large_threshold = Decimal(str(settings.large_job_threshold))
    large_rate = Decimal(str(settings.large_job_fee_rate))

    if success_rate >= 100 or large_rate >= 100:
        return None

    fee_multiplier = Decimal('1') - (success_rate / Decimal('100'))
    candidate_quote = base_price / fee_multiplier
    estimated_fee = (candidate_quote * success_rate) / Decimal('100')
    fee_rule = f'Standard {success_rate}%'

    if candidate_quote > large_threshold:
        # Large job fee applies instead of standard rate
        candidate_quote = base_price / (Decimal('1') - (large_rate / Decimal('100')))
        estimated_fee = candidate_quote - base_price
        fee_rule = f'Large job {large_rate}%'
    elif estimated_fee > fee_cap:
        candidate_quote = base_price + fee_cap
        estimated_fee = fee_cap
        fee_rule = f'Standard {success_rate}% / FJD ${fee_cap} cap'

    client_total = candidate_quote.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    estimated_fee = estimated_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return {
        'base_price': base_price,
        'fee_rate': success_rate,
        'fee_cap': fee_cap,
        'estimated_platform_fee': estimated_fee,
        'client_quote_total': client_total,
        'estimated_tradie_take_home': base_price,
        'fee_rule_applied': fee_rule,
        'large_job_threshold': large_threshold,
        'large_job_fee_rate': large_rate,
    }


def calculate_quote_from_take_home(minimum_take_home, settings=None):
    """Reverse-calculate the lowest customer-facing quote for a desired take-home amount."""
    if settings is None:
        settings = get_active_platform_settings()

    if not settings or minimum_take_home <= 0:
        return None

    success_rate = Decimal(str(settings.success_fee_rate))
    fee_cap = Decimal(str(settings.success_fee_cap))
    large_threshold = Decimal(str(settings.large_job_threshold))
    large_rate = Decimal(str(settings.large_job_fee_rate))

    if success_rate >= 100 or large_rate >= 100:
        return None

    standard_multiplier = Decimal('1') - (success_rate / Decimal('100'))
    candidate_quote = minimum_take_home / standard_multiplier
    estimated_fee = (candidate_quote * success_rate) / Decimal('100')
    fee_rule = f'Standard {success_rate}%'

    if candidate_quote > large_threshold:
        candidate_quote = minimum_take_home / (Decimal('1') - (large_rate / Decimal('100')))
        estimated_fee = candidate_quote - minimum_take_home
        fee_rule = f'Large job {large_rate}%'
    elif estimated_fee > fee_cap:
        candidate_quote = minimum_take_home + fee_cap
        estimated_fee = fee_cap
        fee_rule = f'Standard {success_rate}% / FJD ${fee_cap} cap'

    client_total = candidate_quote.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    estimated_fee = estimated_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    provider_take_home = (client_total - estimated_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return {
        'minimum_take_home_amount': minimum_take_home,
        'customer_facing_quote': client_total,
        'estimated_platform_fee': estimated_fee,
        'estimated_provider_take_home': provider_take_home,
        'fee_rule_applied': fee_rule,
        'success_fee_rate_at_quote_time': success_rate,
        'success_fee_cap_at_quote_time': fee_cap,
        'large_job_threshold_at_quote_time': large_threshold,
        'large_job_fee_rate_at_quote_time': large_rate,
    }


def calculate_quote_without_platform_fee(quote_total, settings=None):
    """
    When tradie absorbs the platform fee (include_platform_fee=False).
    
    Returns: {
        'base_price': quote_total,  # What tradie wants
        'fee_rate': fee_rate,
        'fee_cap': fee_cap,
        'estimated_platform_fee': estimated_fee,
        'client_quote_total': quote_total,  # Client sees this
        'estimated_tradie_take_home': tradie_gets,
    }
    """
    if settings is None:
        settings = get_active_platform_settings()
    
    if not settings:
        return None
    
    fee_rate, fee_cap, estimated_fee = calculate_platform_fee(quote_total, settings)
    tradie_gets = quote_total - estimated_fee

    return {
        'base_price': quote_total,
        'fee_rate': fee_rate,
        'fee_cap': fee_cap,
        'estimated_platform_fee': estimated_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'client_quote_total': quote_total,
        'estimated_tradie_take_home': tradie_gets.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
    }


def create_platform_fee_for_task(task, final_job_value):
    """
    Create a PlatformFee record when a task is completed. Applies (and
    consumes) any discount selected on the accepted quote — founding member
    credit or a promo code — capped so it can never exceed the fee itself.
    Recalculated fresh here rather than trusting the quote-time estimate,
    since the credit balance or promo validity may have changed since then.
    """
    if not task.assigned_tradie:
        return None

    settings = get_active_platform_settings()
    if not settings:
        return None

    fee_rate, fee_cap, gross_fee_amount = calculate_platform_fee(final_job_value, settings)

    with transaction.atomic():
        discount_amount = Decimal('0.00')
        accepted_quote = task.quotes.filter(status=Quote.STATUS_ACCEPTED).first()
        if accepted_quote:
            if accepted_quote.used_founding_credit:
                profile = getattr(task.assigned_tradie, 'tradie_profile', None)
                if profile and profile.is_founding_member and profile.founding_member_credit_balance > 0:
                    discount_amount = min(profile.founding_member_credit_balance, gross_fee_amount)
                    profile.founding_member_credit_balance -= discount_amount
                    profile.save(update_fields=['founding_member_credit_balance'])
            elif accepted_quote.promo_code_id:
                promo = accepted_quote.promo_code
                if promo and promo.is_valid_now():
                    discount_amount = promo.calculate_discount(gross_fee_amount)
                    promo.times_used += 1
                    promo.save(update_fields=['times_used'])

        fee_amount = gross_fee_amount - discount_amount

        platform_fee = PlatformFee.objects.create(
            task=task,
            tradie=task.assigned_tradie,
            final_job_value=final_job_value,
            fee_rate=fee_rate,
            fee_cap=fee_cap,
            gross_fee_amount=gross_fee_amount,
            discount_amount=discount_amount,
            fee_amount=fee_amount,
            status=PlatformFee.STATUS_PENDING,
        )

    return platform_fee


def get_eligible_platform_fees(tradie, period_start, period_end):
    """
    PlatformFees eligible for invoicing for `tradie` within [period_start, period_end]:
    pending, linked to a completed task with a confirmed final job value,
    and completed within the period. (status=pending already excludes fees
    that are invoiced, paid, or waived, and fees already linked to an invoice.)
    """
    return PlatformFee.objects.filter(
        tradie=tradie,
        status=PlatformFee.STATUS_PENDING,
        task__status=Task.STATUS_COMPLETED,
        task__final_job_value__isnull=False,
        task__completed_at__date__gte=period_start,
        task__completed_at__date__lte=period_end,
    ).select_related('task').order_by('task__completed_at')


def get_providers_with_pending_fees(period_start, period_end):
    """
    Group eligible pending PlatformFees by provider for the given period.
    Returns a list of {'tradie': User, 'fees': [...], 'total': Decimal}.
    """
    fees = PlatformFee.objects.filter(
        status=PlatformFee.STATUS_PENDING,
        task__status=Task.STATUS_COMPLETED,
        task__final_job_value__isnull=False,
        task__completed_at__date__gte=period_start,
        task__completed_at__date__lte=period_end,
    ).select_related('tradie', 'task').order_by('tradie__first_name', 'tradie__last_name', 'task__completed_at')

    grouped = {}
    order = []
    for fee in fees:
        if fee.tradie_id not in grouped:
            grouped[fee.tradie_id] = {'tradie': fee.tradie, 'fees': [], 'total': Decimal('0')}
            order.append(fee.tradie_id)
        grouped[fee.tradie_id]['fees'].append(fee)
        grouped[fee.tradie_id]['total'] += fee.fee_amount

    return [grouped[tid] for tid in order]


def fee_rule_label(fee, settings=None):
    """Describe which fee rule applied to a PlatformFee, e.g. 'Standard 7.5%' or 'Large job 3%'."""
    if settings is None:
        settings = get_active_platform_settings()
    rate_str = f'{fee.fee_rate:.2f}'.rstrip('0').rstrip('.')
    if settings and fee.fee_rate == settings.large_job_fee_rate and settings.large_job_fee_rate != settings.success_fee_rate:
        return f'Large job {rate_str}%'
    return f'Standard {rate_str}%'


def build_invoice_line_description(fee, settings=None):
    """Build the auto-generated line description for a completed-job platform fee."""
    task = fee.task
    completed = task.completed_at
    completed_str = f'{completed.day} {completed.strftime("%B %Y")}' if completed else 'Not recorded'
    rule = fee_rule_label(fee, settings)

    lines = [
        f'Job: {task.title}',
        f'Completed: {completed_str}',
        f'Final job value: FJD ${fee.final_job_value:.2f}',
    ]
    if rule.startswith('Large job'):
        lines.append(f'Fee rule: {rule}')
    lines.append(f'Coconut Wireless fee: FJD ${fee.fee_amount:.2f}')
    return '\n'.join(lines)


def create_invoice_with_lines(tradie, period_start, period_end, fee_ids, manual_lines=None, due_days=7):
    """
    Create a draft invoice for `tradie` covering [period_start, period_end],
    with one InvoiceLine per selected (still-pending) PlatformFee — marking
    each as invoiced — plus any manual adjustment lines.
    """
    settings = get_active_platform_settings()
    fees = list(PlatformFee.objects.filter(
        pk__in=fee_ids, tradie=tradie, status=PlatformFee.STATUS_PENDING
    ).select_related('task'))

    total = Decimal('0')

    with transaction.atomic():
        invoice = Invoice.objects.create(
            tradie=tradie,
            invoice_number=generate_invoice_number(tradie),
            period_start=period_start,
            period_end=period_end,
            total_amount=Decimal('0'),
            status=Invoice.STATUS_DRAFT,
            due_date=timezone.localdate() + timedelta(days=due_days),
        )

        for fee in fees:
            InvoiceLine.objects.create(
                invoice=invoice,
                platform_fee=fee,
                task=fee.task,
                description=build_invoice_line_description(fee, settings),
                final_job_value=fee.final_job_value,
                fee_rate=fee.fee_rate,
                amount=fee.fee_amount,
            )
            total += fee.fee_amount
            fee.status = PlatformFee.STATUS_INVOICED
            fee.save(update_fields=['status'])

        for manual in (manual_lines or []):
            description = (manual.get('description') or '').strip()
            amount = manual.get('amount')
            if not description or amount in (None, ''):
                continue
            amount = Decimal(str(amount))
            InvoiceLine.objects.create(
                invoice=invoice,
                description=description,
                amount=amount,
            )
            total += amount

        invoice.total_amount = total
        invoice.save(update_fields=['total_amount'])

    return invoice


def send_invoice_notifications(invoice):
    """
    Mark the invoice as sent and notify the provider via in-platform message,
    email, and an SMS log entry (no SMS gateway required — admin can send the
    SMS manually using the logged text).

    Returns True if the email was delivered (or there was no address to send
    to), False if the email attempt failed. The invoice is still marked sent
    and the in-platform/SMS log entries are still created either way — a mail
    server outage shouldn't block the admin from progressing an invoice.
    """
    from django.conf import settings as django_settings
    from django.core.mail import send_mail

    tradie = invoice.tradie
    lines = invoice.lines.all()

    period_str = ''
    if invoice.period_start and invoice.period_end:
        period_str = f'{invoice.period_start.strftime("%d %B %Y")} to {invoice.period_end.strftime("%d %B %Y")}'

    job_lines = '\n'.join(
        f'- {(line.task.title if line.task else line.description.splitlines()[0])}: FJD ${line.amount:.2f}'
        for line in lines
    )

    subject = f'Coconut Wireless invoice {invoice.invoice_number}'

    body = (
        f'Bula {tradie.first_name},\n\n'
        f'Your Coconut Wireless invoice {invoice.invoice_number} has been issued '
        f'for the period {period_str}.\n\n'
        f'Invoice total: FJD ${invoice.total_amount:.2f}\n'
        f'Due date: {invoice.due_date.strftime("%d %B %Y")}\n\n'
        f'Jobs included:\n{job_lines}\n\n'
        f'Please arrange payment by bank transfer or M-PAiSA.\n\n'
        f'You can view the full invoice in your Billing section.\n\n'
        f'Vinaka,\nCoconut Wireless Team'
    )

    sms_body = (
        f'Coconut Wireless invoice {invoice.invoice_number} issued. '
        f'Amount: FJD ${invoice.total_amount:.2f}. '
        f'Due: {invoice.due_date.strftime("%d %B %Y")}. '
        f'Check your Coconut Wireless messages/email. Vinaka.'
    )

    InvoiceNotification.objects.create(
        invoice=invoice, recipient=tradie, channel=InvoiceNotification.CHANNEL_IN_PLATFORM,
        subject=subject, body=body,
    )

    email_sent = True
    if tradie.email:
        try:
            send_mail(
                subject, body,
                getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@coconutwireless.fj'),
                [tradie.email],
                fail_silently=False,
            )
        except Exception as exc:
            email_sent = False
            import sys
            import traceback
            print(f'send_invoice_notifications: email send failed: {exc!r}', flush=True)
            traceback.print_exc()
            sys.stderr.flush()
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except ImportError:
                pass

    InvoiceNotification.objects.create(
        invoice=invoice, recipient=tradie, channel=InvoiceNotification.CHANNEL_EMAIL,
        subject=subject, body=body,
    )

    InvoiceNotification.objects.create(
        invoice=invoice, recipient=tradie, channel=InvoiceNotification.CHANNEL_SMS,
        subject=subject, body=sms_body,
    )

    invoice.status = Invoice.STATUS_SENT
    invoice.sent_at = timezone.now()
    invoice.save(update_fields=['status', 'sent_at'])

    return email_sent

    return invoice


def create_weekly_invoices(period_start, period_end):
    """
    Generate one DRAFT invoice per provider for all eligible pending platform
    fees within [period_start, period_end]. Invoices are NOT sent automatically —
    admin must review and send each one.
    """
    invoices = []
    for entry in get_providers_with_pending_fees(period_start, period_end):
        invoice = create_invoice_with_lines(
            tradie=entry['tradie'],
            period_start=period_start,
            period_end=period_end,
            fee_ids=[f.pk for f in entry['fees']],
        )
        invoices.append(invoice)
    return invoices


def generate_invoice_number(tradie):
    """Generate a unique invoice number."""
    from django.utils import timezone
    today = timezone.localdate()
    tradie_id = str(tradie.id).zfill(5)
    date_str = today.strftime('%Y%m%d')
    # Format: INV-20260610-00123-001 (date-tradie_id-sequence)
    count = Invoice.objects.filter(tradie=tradie, created_at__date=today).count() + 1
    return f'INV-{date_str}-{tradie_id}-{str(count).zfill(3)}'


def is_tradie_payment_restricted(tradie):
    """
    Check if tradie has overdue invoices > 14 days old.
    If so, restrict them from submitting new quotes.
    """
    from django.utils import timezone
    from datetime import timedelta

    today = timezone.localdate()
    cutoff_date = today - timedelta(days=14)
    
    overdue_old = Invoice.objects.filter(
        tradie=tradie,
        status__in=[Invoice.STATUS_SENT, Invoice.STATUS_OVERDUE],
        due_date__lt=cutoff_date,
    ).exists()
    
    return overdue_old


def get_tradie_unpaid_invoices(tradie):
    """Get all unpaid invoices for a tradie."""
    return Invoice.objects.filter(
        tradie=tradie,
        status__in=[Invoice.STATUS_SENT, Invoice.STATUS_OVERDUE],
    ).order_by('-due_date')


def get_tradie_billing_summary(tradie):
    """Get billing summary for tradie dashboard."""
    from django.utils import timezone
    today = timezone.localdate()
    week_ago = today - timedelta(days=7)
    
    # Current week fees (pending/invoiced)
    week_fees = PlatformFee.objects.filter(
        tradie=tradie,
        created_at__date__gte=week_ago,
        status__in=[PlatformFee.STATUS_PENDING, PlatformFee.STATUS_INVOICED],
    )
    current_week_total = sum(f.fee_amount for f in week_fees) or Decimal('0')
    
    # Unpaid invoices
    unpaid_invoices = get_tradie_unpaid_invoices(tradie)
    unpaid_total = sum(i.total_amount for i in unpaid_invoices) or Decimal('0')
    
    # Next invoice date (7 days from today)
    next_invoice_date = today + timedelta(days=7)
    
    # Check if restricted
    is_restricted = is_tradie_payment_restricted(tradie)
    
    return {
        'current_week_fees': current_week_total,
        'unpaid_invoices_count': unpaid_invoices.count(),
        'unpaid_invoices_total': unpaid_total,
        'next_invoice_date': next_invoice_date,
        'is_payment_restricted': is_restricted,
        'unpaid_invoices': unpaid_invoices,
    }


def send_welcome_notice(user):
    """
    Send a welcome email to a newly registered user and also log an in-platform
    PlatformNotice so it shows up in their in-app Notices inbox (not just email).
    Best-effort only — registration must succeed even if the email fails to send,
    so failures here are swallowed rather than raised.
    """
    from django.conf import settings as django_settings
    from django.core.mail import send_mail

    if user.role == User.ROLE_TRADIE:
        subject = 'Welcome to Coconut Wireless — you are set up as a Local Pro'
        body = (
            f'Bula {user.first_name},\n\n'
            f'Welcome to Coconut Wireless! Your local pro account has been created.\n\n'
            f'Your documents are now pending review — once verified, you can start '
            f'quoting on tasks posted by clients across Fiji.\n\n'
            f'In the meantime, you can complete your profile and browse open tasks '
            f'in your service towns from your dashboard.\n\n'
            f'Vinaka,\nCoconut Wireless Team'
        )
    else:
        subject = 'Welcome to Coconut Wireless'
        body = (
            f'Bula {user.first_name},\n\n'
            f'Welcome to Coconut Wireless! Your client account is ready.\n\n'
            f'Post your first task to get quotes from trusted local pros in your area.\n\n'
            f'Vinaka,\nCoconut Wireless Team'
        )

    # Log an in-platform notice (always — this is what the user sees in their
    # Notices inbox) and a separate email-channel record for the audit trail,
    # matching the same per-channel logging pattern as invoice notifications.
    PlatformNotice.objects.create(
        recipient=user,
        notice_type=PlatformNotice.TYPE_WELCOME,
        channel=PlatformNotice.CHANNEL_IN_PLATFORM,
        subject=subject,
        body=body,
    )

    if user.email:
        try:
            send_mail(
                subject, body,
                getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@coconutwireless.fj'),
                [user.email],
                fail_silently=False,
            )
            PlatformNotice.objects.create(
                recipient=user,
                notice_type=PlatformNotice.TYPE_WELCOME,
                channel=PlatformNotice.CHANNEL_EMAIL,
                subject=subject,
                body=body,
            )
        except Exception as exc:
            import sys
            import traceback
            print(f'send_welcome_notice: email send failed: {exc!r}', flush=True)
            traceback.print_exc()
            sys.stderr.flush()
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except ImportError:
                pass


def notify_admin(subject, body):
    """
    Send an operational notification (support contact click, new tradie
    pending approval, etc.) to settings.ADMIN_EMAIL. Best-effort and silent
    if ADMIN_EMAIL isn't configured — this must never break the user-facing
    request that triggered it.
    """
    from django.conf import settings as django_settings
    from django.core.mail import send_mail

    admin_email = getattr(django_settings, 'ADMIN_EMAIL', '')
    if not admin_email:
        print(f'notify_admin: ADMIN_EMAIL not configured, skipping notification: {subject}', flush=True)
        return False

    try:
        send_mail(
            subject, body,
            getattr(django_settings, 'DEFAULT_FROM_EMAIL', 'noreply@coconutwireless.fj'),
            [admin_email],
            fail_silently=False,
        )
        return True
    except Exception as exc:
        import sys
        import traceback
        print(f'notify_admin: send failed: {exc!r}', flush=True)
        traceback.print_exc()
        sys.stderr.flush()
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(exc)
        except ImportError:
            pass
        return False
