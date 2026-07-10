"""
views.py — all marketplace views.

Privacy rule enforced here:
  PrivateReview is NEVER imported into this file.
  It only lives in admin.py.
"""
from django.contrib import messages as flash
from django.contrib.auth import authenticate, login, logout
from decimal import Decimal
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .constants import (
    PRIVATE_REVIEW_CRITERIA,
    PUBLIC_REVIEW_CRITERIA,
    TOWN_CHOICES,
)
from .forms import (
    ClientRegistrationForm,
    LoginForm,
    MessageForm,
    PrivateReviewForm,
    PublicReviewForm,
    QuoteForm,
    QuotingAppointmentForm,
    TaskForm,
    TradieRegistrationForm,
)
from .models import (
    Invoice,
    Message,
    PlatformNotice,
    PlatformSettings,
    PublicReview,
    Quote,
    QuotingAppointment,
    QuotingAppointmentSlot,
    Sponsor,
    Task,
    TermsAcceptance,
    TradeCategory,
    TradieProfile,
    User,
)
from .utils import (
    calculate_platform_fee,
    calculate_quote_from_take_home,
    create_platform_fee_for_task,
    get_active_platform_settings,
    get_tradie_billing_summary,
    send_welcome_notice,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require_role(request, role):
    if not request.user.is_authenticated or request.user.role != role:
        raise PermissionDenied


def _get_tradie_profile(user):
    try:
        return user.tradie_profile
    except TradieProfile.DoesNotExist:
        return None


def _require_approved_tradie(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if request.user.role != User.ROLE_TRADIE:
        flash.error(request, 'Only local pro accounts can access this action.')
        return redirect('dashboard')
    profile = _get_tradie_profile(request.user)
    if not profile:
        flash.warning(request, 'Your local pro profile could not be found. Please contact support.')
        return redirect('tradie_dashboard')
    if profile.verification_status == TradieProfile.VERIFICATION_PENDING:
        flash.warning(request, 'Your local pro account is pending verification. You can browse, but quoting is disabled.')
        return redirect('tradie_dashboard')
    if profile.verification_status == TradieProfile.VERIFICATION_REJECTED:
        flash.error(request, 'Your local pro account verification was rejected. Please contact support.')
        return redirect('tradie_dashboard')
    if profile.verification_status == TradieProfile.VERIFICATION_SUSPENDED:
        flash.error(request, 'Your local pro account is suspended. Please contact support.')
        return redirect('tradie_dashboard')
    return None


def _build_conversations(user):
    """Return a list of dicts describing each unique (task, other_user) conversation,
    ordered by most-recent message first."""
    msgs = (
        Message.objects.filter(Q(sender=user) | Q(recipient=user))
        .select_related('task', 'sender', 'recipient')
        .order_by('-created_at')
    )
    seen = set()
    convs = []
    for msg in msgs:
        other = msg.recipient if msg.sender == user else msg.sender
        key = (msg.task_id, other.pk)
        if key not in seen:
            seen.add(key)
            convs.append({'task': msg.task, 'other': other, 'last_msg': msg})
    return convs


# ── Static pages ─────────────────────────────────────────────────────────────

def home(request):
    return render(request, 'marketplace/home.html', {
        'sponsors': Sponsor.get_active_for_placement('homepage'),
    })


def how_it_works(request):
    return render(request, 'marketplace/how_it_works.html', {
        'sponsors': Sponsor.get_active_for_placement('how_it_works'),
    })


def terms(request):
    return render(request, 'marketplace/terms.html')


def privacy(request):
    return render(request, 'marketplace/privacy.html')


def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({'status': 'error'}, status=503)
    return JsonResponse({'status': 'ok'})


# ── Auth ──────────────────────────────────────────────────────────────────────

def register_client(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = ClientRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        settings_obj = PlatformSettings.get_active()
        TermsAcceptance.objects.create(
            user=user,
            terms_version=settings_obj.terms_version if settings_obj else '1.0',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
        )
        login(request, user)
        send_welcome_notice(user)
        flash.success(request, f'Bula, {user.first_name}! Your client account is ready.')
        return redirect('client_dashboard')
    return render(request, 'marketplace/register_client.html', {
        'form': form,
        'closed_beta_enabled': settings.CLOSED_BETA_ENABLED,
        'beta_gate_clients': settings.BETA_GATE_CLIENT_SIGNUPS,
    })


def register_tradie(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = TradieRegistrationForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            user = form.save()
        except Exception as exc:
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except ImportError:
                pass
            flash.error(
                request,
                'Something went wrong creating your account (likely a document upload issue). '
                'Please try again — if it keeps failing, contact support.',
            )
            return render(request, 'marketplace/register_tradie.html', {
                'form': form,
                'trade_choices': TradeCategory.get_choices(),
                'town_choices': TOWN_CHOICES,
                'closed_beta_enabled': settings.CLOSED_BETA_ENABLED,
                'beta_gate_tradies': settings.BETA_GATE_TRADIE_SIGNUPS,
            })
        settings_obj = PlatformSettings.get_active()
        TermsAcceptance.objects.create(
            user=user,
            terms_version=settings_obj.terms_version if settings_obj else '1.0',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            accepted_platform_circumvention=form.cleaned_data.get('accepted_platform_circumvention', False),
            accepted_invoicing_terms=form.cleaned_data.get('accepted_invoicing_terms', False),
        )
        login(request, user)
        send_welcome_notice(user)
        flash.success(request, f'Bula, {user.first_name}! Your local pro account is created and pending document verification.')
        return redirect('tradie_dashboard')
    return render(request, 'marketplace/register_tradie.html', {
        'form': form,
        'trade_choices': TradeCategory.get_choices(),
        'town_choices': TOWN_CHOICES,
        'closed_beta_enabled': settings.CLOSED_BETA_ENABLED,
        'beta_gate_tradies': settings.BETA_GATE_TRADIE_SIGNUPS,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd   = form.cleaned_data
        user = authenticate(request, username=cd['email'], password=cd['password'])
        if user:
            login(request, user)
            nxt = request.GET.get('next', '')
            return redirect(nxt or 'dashboard')
        else:
            flash.error(request, 'Incorrect email or password.')
    return render(request, 'marketplace/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def dashboard(request):
    if request.user.role == User.ROLE_TRADIE:
        return redirect('tradie_dashboard')
    return redirect('client_dashboard')


# ── Client dashboard ──────────────────────────────────────────────────────────

@login_required
def client_dashboard(request):
    _require_role(request, User.ROLE_CLIENT)
    tasks = request.user.tasks.prefetch_related('quotes')
    ctx = {
        'open_tasks':      tasks.filter(status=Task.STATUS_OPEN),
        'assigned_tasks':  tasks.filter(status=Task.STATUS_ASSIGNED),
        'completed_tasks': tasks.filter(status=Task.STATUS_COMPLETED),
        'total_tasks':     tasks.count(),
        'new_quotes':      Quote.objects.filter(
            task__client=request.user, status=Quote.STATUS_PENDING
        ).count(),
        'appointments':    QuotingAppointment.objects.filter(client=request.user).select_related('task', 'provider').prefetch_related('slots').order_by('-created_at'),
        'sponsors':        Sponsor.get_active_for_placement('client_dashboard'),
    }
    return render(request, 'marketplace/client_dashboard.html', ctx)


# ── Tradie dashboard ──────────────────────────────────────────────────────────

@login_required
def tradie_dashboard(request):
    _require_role(request, User.ROLE_TRADIE)
    profile = _get_tradie_profile(request.user)
    tradie_is_approved = profile.is_approved() if profile else False

    nearby = Task.objects.none()
    if tradie_is_approved and profile.service_towns:
        nearby = (
            Task.objects.filter(
                status=Task.STATUS_OPEN,
                town__in=profile.service_towns,
            )
            .exclude(quotes__tradie=request.user)
            .order_by('-created_at')[:10]
        )

    my_quotes = (
        request.user.quotes
        .select_related('task', 'task__client')
        .order_by('-created_at')
    )

    provider_appointments = request.user.provider_quoting_appointments.select_related('task', 'client').prefetch_related('slots').order_by('-created_at')
    ctx = {
        'profile':         profile,
        'pending_quotes':  my_quotes.filter(status=Quote.STATUS_PENDING),
        'accepted_quotes': my_quotes.filter(status=Quote.STATUS_ACCEPTED),
        'completed_tasks': request.user.assigned_tasks.filter(status=Task.STATUS_COMPLETED),
        'nearby_tasks':    nearby,
        'review_count':    PublicReview.objects.filter(ratee=request.user).count(),
        'avg_rating':      (
            PublicReview.objects.filter(ratee=request.user)
            .aggregate(
                a=Avg('reliability_punctuality'), b=Avg('quote_price_accuracy'), c=Avg('value_for_money'),
                d=Avg('service_quality_workmanship'), e=Avg('communication_after_service'),
            )
        ),
        'appointments':    provider_appointments,
        'sponsors':        Sponsor.get_active_for_placement('tradie_dashboard'),
        'tradie_is_approved': tradie_is_approved,
    }
    return render(request, 'marketplace/tradie_dashboard.html', ctx)


@login_required
def billing(request):
    _require_role(request, User.ROLE_TRADIE)

    invoices = (
        request.user.invoices
        .prefetch_related('lines', 'lines__task', 'notifications')
        .order_by('-created_at')
    )

    ctx = {
        'invoices': invoices,
        'summary': get_tradie_billing_summary(request.user),
    }
    return render(request, 'marketplace/billing.html', ctx)


# ── Browse tasks ──────────────────────────────────────────────────────────────

def browse_tasks(request):
    qs = Task.objects.filter(status=Task.STATUS_OPEN).select_related('client')
    category = request.GET.get('category', '').strip()
    keyword  = request.GET.get('q', '').strip()
    town     = request.GET.get('town', '').strip()
    if category:
        qs = qs.filter(category=category)
    if keyword:
        qs = qs.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword))
    if town:
        qs = qs.filter(town=town)
    return render(request, 'marketplace/browse_tasks.html', {
        'tasks':           qs,
        'category_filter': category,
        'keyword_filter':  keyword,
        'town_filter':     town,
        'category_choices': TradeCategory.get_choices(),
        'town_choices':    TOWN_CHOICES,
        'sponsors':        Sponsor.get_active_for_placement('browse_tasks_sidebar'),
    })


# ── Post task ─────────────────────────────────────────────────────────────────

@login_required
def post_task(request):
    _require_role(request, User.ROLE_CLIENT)
    form = TaskForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.client = request.user
        task.save()
        flash.success(request, 'Task posted! Local pros will start sending quotes soon.')
        return redirect('task_detail', pk=task.pk)
    return render(request, 'marketplace/post_task.html', {
        'form': form,
        'category_choices': TradeCategory.get_choices(),
    })


# ── Task detail ───────────────────────────────────────────────────────────────

def task_detail(request, pk):
    task   = get_object_or_404(Task, pk=pk)
    quotes = task.quotes.select_related('tradie').order_by('created_at')

    user_quote        = None
    can_quote         = False
    tradie_is_approved = False
    can_accept        = False
    can_complete      = False
    can_rate_tradie   = False
    can_rate_client   = False
    client_has_rated  = False
    tradie_has_rated  = False

    if request.user.is_authenticated:
        u = request.user
        tradie_profile = _get_tradie_profile(u) if u.role == User.ROLE_TRADIE else None
        tradie_is_approved = tradie_profile.is_approved() if tradie_profile else False
        if u.role == User.ROLE_TRADIE and tradie_is_approved and task.status == Task.STATUS_OPEN:
            try:
                user_quote = quotes.get(tradie=u)
            except Quote.DoesNotExist:
                can_quote = True

        if u == task.client:
            if task.status == Task.STATUS_OPEN:
                can_accept = True
            if task.status == Task.STATUS_ASSIGNED:
                can_complete = True

    appointments = task.quoting_appointments.select_related('provider', 'client', 'selected_slot').prefetch_related('slots').order_by('-created_at')
    can_book_appointment = (
        request.user.is_authenticated
        and request.user.role == User.ROLE_TRADIE
        and tradie_is_approved
        and task.status == Task.STATUS_OPEN
    )
    user_has_appointment = request.user.is_authenticated and appointments.filter(provider=request.user).exists()

    can_message_client = (
        request.user.is_authenticated and request.user != task.client and (
            bool(user_quote) or user_has_appointment or request.user == task.assigned_tradie
        )
    )

    if request.user.is_authenticated and task.status == Task.STATUS_COMPLETED:
        client_has_rated = PublicReview.objects.filter(task=task, rater=task.client).exists()
        if u == task.client:
            can_rate_tradie = not client_has_rated
        if task.assigned_tradie:
            tradie_has_rated = PublicReview.objects.filter(
                task=task, rater=task.assigned_tradie
            ).exists()
            # NOTE: tradie rates client via PrivateReview — that form is at rate_client URL
            if u == task.assigned_tradie:
                # Check via separate import-free approach: query PrivateReview via model
                from .models import PrivateReview as _PR
                tradie_has_rated = _PR.objects.filter(task=task, rater=u).exists()
                can_rate_client = not tradie_has_rated

    # Quotes: client sees all; tradie sees only their own; others see none
    visible_quotes = []
    if request.user.is_authenticated:
        if request.user == task.client:
            visible_quotes = list(quotes)
        elif request.user.role == User.ROLE_TRADIE:
            visible_quotes = [q for q in quotes if q.tradie == request.user]

    return render(request, 'marketplace/task_detail.html', {
        'task':            task,
        'quotes':          visible_quotes,
        'user_quote':      user_quote,
        'can_quote':       can_quote,
        'can_accept':      can_accept,
        'can_complete':    can_complete,
        'can_rate_tradie': can_rate_tradie,
        'can_rate_client': can_rate_client,
        'client_has_rated': client_has_rated,
        'tradie_has_rated': tradie_has_rated,
        'quote_form':      QuoteForm() if can_quote else None,
        'platform_settings': get_active_platform_settings(),
        'submit_quote_url': reverse('submit_quote', args=[task.pk]),
        'appointments':    appointments,
        'can_book_appointment': can_book_appointment,
        'user_has_appointment': user_has_appointment,
        'can_message_client': can_message_client,
        'tradie_can_participate': tradie_is_approved,
        'sponsors':        Sponsor.get_active_for_placement('task_detail_sidebar'),
    })


# ── Submit quote ──────────────────────────────────────────────────────────────

@login_required
def submit_quote(request, pk):
    approval_redirect = _require_approved_tradie(request)
    if approval_redirect:
        return approval_redirect
    task = get_object_or_404(Task, pk=pk, status=Task.STATUS_OPEN)
    if Quote.objects.filter(task=task, tradie=request.user).exists():
        flash.error(request, 'You have already quoted on this task.')
        return redirect('task_detail', pk=pk)
    form = QuoteForm(request.POST)
    if form.is_valid():
        q = form.save(commit=False)
        q.task   = task
        q.tradie = request.user
        q.customer_facing_quote = q.price
        q.client_quote_total = q.price
        q.minimum_take_home_amount = form.cleaned_data.get('minimum_take_home_amount')

        settings = get_active_platform_settings()
        totals = None
        if q.price is not None and q.price > 0:
            fee_rate, fee_cap, _ = calculate_platform_fee(q.price, settings)
            q.success_fee_rate_at_quote_time = fee_rate
            q.success_fee_cap_at_quote_time = fee_cap
            q.large_job_threshold_at_quote_time = settings.large_job_threshold
            q.large_job_fee_rate_at_quote_time = settings.large_job_fee_rate
            q.fee_rule_applied = ''

            if q.price > settings.large_job_threshold:
                q.fee_rule_applied = f'Large job {settings.large_job_fee_rate}%'
            else:
                estimated_fee = (q.price * q.success_fee_rate_at_quote_time) / 100
                if estimated_fee > q.success_fee_cap_at_quote_time:
                    q.fee_rule_applied = f'Standard {q.success_fee_rate_at_quote_time}% / FJD ${q.success_fee_cap_at_quote_time} cap'
                else:
                    q.fee_rule_applied = f'Standard {q.success_fee_rate_at_quote_time}%'

            q.estimated_platform_fee = (q.price * (q.success_fee_rate_at_quote_time if q.price <= settings.large_job_threshold else q.large_job_fee_rate_at_quote_time) / 100)
            if q.price <= settings.large_job_threshold and q.estimated_platform_fee > q.success_fee_cap_at_quote_time:
                q.estimated_platform_fee = q.success_fee_cap_at_quote_time
            q.estimated_platform_fee = q.estimated_platform_fee.quantize(Decimal('0.01'))
            q.estimated_provider_take_home = (q.price - q.estimated_platform_fee).quantize(Decimal('0.01'))
            q.estimated_tradie_take_home = q.estimated_provider_take_home
        q.save()
        flash.success(request, 'Quote submitted! The client will be in touch.')
    else:
        for err in form.errors.values():
            flash.error(request, str(err))
    return redirect('task_detail', pk=pk)


# ── Book quoting appointment ─────────────────────────────────────────────────

@login_required
def book_quoting_appointment(request, pk):
    approval_redirect = _require_approved_tradie(request)
    if approval_redirect:
        return approval_redirect
    task = get_object_or_404(Task, pk=pk, status=Task.STATUS_OPEN)
    existing_appointments = task.quoting_appointments.filter(provider=request.user).prefetch_related('slots').order_by('-created_at')
    form = QuotingAppointmentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save(task, request.user)
        flash.success(request, 'Appointment request sent. The client can choose one of your proposed times.')
        return redirect('task_detail', pk=pk)
    return render(request, 'marketplace/book_quoting_appointment.html', {
        'task': task,
        'form': form,
        'existing_appointments': existing_appointments,
    })


@login_required
def accept_quoting_appointment_slot(request, pk, appt_pk, slot_pk):
    _require_role(request, User.ROLE_CLIENT)
    task = get_object_or_404(Task, pk=pk, client=request.user)
    appointment = get_object_or_404(QuotingAppointment, pk=appt_pk, task=task, status=QuotingAppointment.STATUS_REQUESTED)
    slot = get_object_or_404(QuotingAppointmentSlot, pk=slot_pk, quoting_appointment=appointment)
    appointment.status = QuotingAppointment.STATUS_ACCEPTED
    appointment.selected_slot = slot
    appointment.save()
    appointment.slots.update(is_selected=False)
    slot.is_selected = True
    slot.save()
    flash.success(request, 'Quoting appointment confirmed. Your local pro will see the accepted slot.')
    return redirect('task_detail', pk=pk)


@login_required
def decline_quoting_appointment(request, pk, appt_pk):
    _require_role(request, User.ROLE_CLIENT)
    task = get_object_or_404(Task, pk=pk, client=request.user)
    appointment = get_object_or_404(QuotingAppointment, pk=appt_pk, task=task, status=QuotingAppointment.STATUS_REQUESTED)
    appointment.status = QuotingAppointment.STATUS_DECLINED
    appointment.save()
    flash.success(request, 'You declined the appointment request. The local pro can send a new request if needed.')
    return redirect('task_detail', pk=pk)


@login_required
def cancel_quoting_appointment(request, pk, appt_pk):
    approval_redirect = _require_approved_tradie(request)
    if approval_redirect:
        return approval_redirect
    appointment = get_object_or_404(QuotingAppointment, pk=appt_pk, task__pk=pk, provider=request.user, status=QuotingAppointment.STATUS_REQUESTED)
    appointment.status = QuotingAppointment.STATUS_CANCELLED
    appointment.save()
    flash.success(request, 'Your quoting appointment request has been cancelled.')
    return redirect('task_detail', pk=pk)


# ── Accept quote ──────────────────────────────────────────────────────────────

@login_required
def accept_quote(request, pk, qpk):
    _require_role(request, User.ROLE_CLIENT)
    task  = get_object_or_404(Task, pk=pk, client=request.user, status=Task.STATUS_OPEN)
    quote = get_object_or_404(Quote, pk=qpk, task=task, status=Quote.STATUS_PENDING)
    # Accept this quote, decline all others
    task.quotes.exclude(pk=qpk).update(status=Quote.STATUS_DECLINED)
    quote.status = Quote.STATUS_ACCEPTED
    quote.save()
    task.status          = Task.STATUS_ASSIGNED
    task.assigned_tradie = quote.tradie
    task.save()
    flash.success(request, f'Quote accepted! {quote.tradie.first_name} is assigned.')
    return redirect('task_detail', pk=pk)


# ── Complete task ─────────────────────────────────────────────────────────────

@login_required
def complete_task(request, pk):
    _require_role(request, User.ROLE_CLIENT)
    task = get_object_or_404(Task, pk=pk, client=request.user, status=Task.STATUS_ASSIGNED)
    task.status = Task.STATUS_COMPLETED
    task.completed_at = timezone.now()
    accepted_quote = task.quotes.filter(status=Quote.STATUS_ACCEPTED).first()
    if accepted_quote:
        task.final_job_value = accepted_quote.price
    task.save()
    if task.final_job_value is not None and not task.has_platform_fee():
        create_platform_fee_for_task(task, task.final_job_value)
    flash.success(request, 'Task marked as complete. Please leave a review!')
    return redirect('task_detail', pk=pk)


# ── Rate tradie (public review, client → tradie) ──────────────────────────────

@login_required
def rate_tradie(request, pk):
    _require_role(request, User.ROLE_CLIENT)
    task = get_object_or_404(Task, pk=pk, client=request.user, status=Task.STATUS_COMPLETED)
    if PublicReview.objects.filter(task=task, rater=request.user).exists():
        flash.info(request, 'You have already reviewed this job.')
        return redirect('task_detail', pk=pk)
    if not task.assigned_tradie:
        flash.error(request, 'This task has no assigned local pro to review.')
        return redirect('task_detail', pk=pk)
    form = PublicReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        PublicReview.objects.create(
            task=task,
            rater=request.user,
            ratee=task.assigned_tradie,
            reliability_punctuality   = int(cd['reliability_punctuality']),
            quote_price_accuracy      = int(cd['quote_price_accuracy']),
            value_for_money           = int(cd['value_for_money']),
            service_quality_workmanship = int(cd['service_quality_workmanship']),
            communication_after_service  = int(cd['communication_after_service']),
            timeline_schedule_delivery   = int(cd['timeline_schedule_delivery']),
            comment                    = cd.get('comment', ''),
        )
        flash.success(request, 'Vinaka! Your review has been posted.')
        return redirect('tradie_profile', pk=task.assigned_tradie.pk)
    return render(request, 'marketplace/rate_tradie.html', {
        'task':     task,
        'form':     form,
        'criteria': PUBLIC_REVIEW_CRITERIA,
    })


# ── Rate client (private review, tradie → client) ────────────────────────────
# PrivateReview is imported here only via the models layer; no template ever sees it.

@login_required
def rate_client(request, pk):
    _require_role(request, User.ROLE_TRADIE)
    task = get_object_or_404(Task, pk=pk, assigned_tradie=request.user, status=Task.STATUS_COMPLETED)
    # Import PrivateReview locally so it CANNOT accidentally be passed to context
    from .models import PrivateReview
    if PrivateReview.objects.filter(task=task, rater=request.user).exists():
        flash.info(request, 'You have already submitted your feedback for this job.')
        return redirect('task_detail', pk=pk)
    form = PrivateReviewForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        cd = form.cleaned_data
        PrivateReview.objects.create(
            task=task,
            rater=request.user,
            ratee=task.client,
            access_readiness = int(cd['access_readiness']),
            scope_clarity    = int(cd['scope_clarity']),
            communication    = int(cd['communication']),
            payment          = int(cd['payment']),
            conduct          = int(cd['conduct']),
            comment          = cd.get('comment', ''),
        )
        flash.success(request, 'Feedback recorded. Vinaka!')
        return redirect('task_detail', pk=pk)
    # Pass criteria but NOT the PrivateReview model or any queryset
    return render(request, 'marketplace/rate_client.html', {
        'task':     task,
        'form':     form,
        'criteria': PRIVATE_REVIEW_CRITERIA,
    })


# ── Tradie profile ────────────────────────────────────────────────────────────

def tradie_profile(request, pk):
    tradie  = get_object_or_404(User, pk=pk, role=User.ROLE_TRADIE)
    profile = get_object_or_404(TradieProfile, user=tradie)
    reviews = PublicReview.objects.filter(ratee=tradie).select_related('rater', 'task').order_by('-created_at')
    count   = reviews.count()

    raw_avgs = reviews.aggregate(
        reliability_punctuality   = Avg('reliability_punctuality'),
        quote_price_accuracy      = Avg('quote_price_accuracy'),
        value_for_money           = Avg('value_for_money'),
        service_quality_workmanship = Avg('service_quality_workmanship'),
        communication_after_service  = Avg('communication_after_service'),
        timeline_schedule_delivery   = Avg('timeline_schedule_delivery'),
    )

    criteria_data = []
    total = 0
    for c in PUBLIC_REVIEW_CRITERIA:
        avg = raw_avgs.get(c['field']) or 0
        total += avg
        criteria_data.append({
            'label': c['label'],
            'field': c['field'],
            'avg':   round(avg, 1),
            'pct':   round(avg / 5 * 100),
        })
    overall = round(total / 6, 1) if count else 0

    return render(request, 'marketplace/tradie_profile.html', {
        'tradie':        tradie,
        'profile':       profile,
        'reviews':       reviews,
        'review_count':  count,
        'criteria_data': criteria_data,
        'overall':       overall,
        'jobs_done':     tradie.assigned_tasks.filter(status=Task.STATUS_COMPLETED).count(),
    })


# ── Notices ───────────────────────────────────────────────────────────────────

@login_required
def notices(request):
    return render(request, 'marketplace/notices.html', {
        'notices': PlatformNotice.objects.filter(recipient=request.user).order_by('-sent_at'),
    })


# ── Messages inbox ────────────────────────────────────────────────────────────

@login_required
def inbox(request):
    convs = _build_conversations(request.user)
    return render(request, 'marketplace/messages.html', {
        'conversations':  convs,
        'active_task':    None,
        'active_other':   None,
        'chat_messages':  [],
        'compose_form':   None,
    })


@login_required
def conversation(request, tpk, opk):
    task        = get_object_or_404(Task, pk=tpk)
    other_user  = get_object_or_404(User, pk=opk)
    # Ensure the logged-in user is actually part of this task
    u = request.user
    if u != task.client and u != task.assigned_tradie and not (
        task.quotes.filter(tradie=u).exists()
    ) and not task.quoting_appointments.filter(provider=u).exists():
        raise PermissionDenied

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            Message.objects.create(
                task=task, sender=u, recipient=other_user,
                body=form.cleaned_data['body'],
            )
        return redirect('conversation', tpk=tpk, opk=opk)

    chat_messages = Message.objects.filter(
        task=task
    ).filter(
        Q(sender=u, recipient=other_user) | Q(sender=other_user, recipient=u)
    ).order_by('created_at')

    convs = _build_conversations(u)
    return render(request, 'marketplace/messages.html', {
        'conversations': convs,
        'active_task':   task,
        'active_other':  other_user,
        'chat_messages': chat_messages,
        'compose_form':  MessageForm(),
    })
