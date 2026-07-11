from decimal import Decimal

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from .constants import TOWN_CHOICES, EXPERIENCE_CHOICES
from .managers import PublicReviewManager, PrivateReviewManager


# ── Custom user manager (email login, no username) ──────────────────────────

class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('Email address is required.')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', '')
        return self._create_user(email, password, **extra_fields)


# ── User ─────────────────────────────────────────────────────────────────────

class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    ROLE_CLIENT = 'client'
    ROLE_TRADIE = 'tradie'
    ROLE_CHOICES = [
        (ROLE_CLIENT, 'Client'),
        (ROLE_TRADIE, 'Tradie'),
        ('',          'Staff / Admin'),
    ]
    role   = models.CharField(max_length=10, choices=ROLE_CHOICES, blank=True, default='')
    mobile = models.CharField(max_length=20, blank=True)
    town   = models.CharField(max_length=50, blank=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return name if name else self.email

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip() or self.email

    @property
    def initials(self):
        parts = [self.first_name[:1], self.last_name[:1]]
        return ''.join(p for p in parts if p).upper() or '?'


# ── Tradie profile ────────────────────────────────────────────────────────────

class TradieProfile(models.Model):
    VERIFICATION_PENDING = 'pending'
    VERIFICATION_APPROVED = 'approved'
    VERIFICATION_REJECTED = 'rejected'
    VERIFICATION_SUSPENDED = 'suspended'
    VERIFICATION_STATUS_CHOICES = [
        (VERIFICATION_PENDING, 'Pending review'),
        (VERIFICATION_APPROVED, 'Approved'),
        (VERIFICATION_REJECTED, 'Rejected'),
        (VERIFICATION_SUSPENDED, 'Suspended'),
    ]

    user            = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tradie_profile')
    business_name   = models.CharField(max_length=100, blank=True)
    tin             = models.CharField(max_length=50, blank=True, verbose_name='TIN Number (optional)')
    years_experience = models.CharField(max_length=20, blank=True, choices=EXPERIENCE_CHOICES)
    bio             = models.TextField(blank=True)
    trades          = models.JSONField(default=list)        # list of TradeCategory slugs
    service_towns   = models.JSONField(default=list)        # list of town keys from TOWN_CHOICES

    # Provider verification documents
    tin_letter                    = models.FileField(upload_to='provider_documents/', blank=True, verbose_name='TIN Letter')
    business_licence              = models.FileField(upload_to='provider_documents/', blank=True, verbose_name='Business Licence')
    public_liability_insurance    = models.FileField(upload_to='provider_documents/', blank=True, verbose_name='Public Liability Insurance')
    electrical_contractors_licence = models.FileField(upload_to='provider_documents/', blank=True, verbose_name='Electrical Contractors Licence')
    plumber_licence               = models.FileField(upload_to='provider_documents/', blank=True, verbose_name='Plumber Licence')
    verification_status           = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default=VERIFICATION_PENDING,
        verbose_name='Verification status',
    )
    documents_verified            = models.BooleanField(default=False, verbose_name='Documents verified by admin')
    verification_notes            = models.TextField(blank=True, verbose_name='Verification notes (admin only)')

    # Founding member program — first 20 tradies get a badge + FJD $200 platform
    # fee credit, spent down automatically as their jobs complete.
    is_founding_member             = models.BooleanField(default=False, verbose_name='Founding member')
    founding_member_credit_balance = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Founding member credit balance (FJD)',
    )

    def __str__(self):
        return f'{self.user} – Tradie Profile'

    def save(self, *args, **kwargs):
        """Keep legacy documents_verified in sync with verification_status."""
        self.documents_verified = self.verification_status == self.VERIFICATION_APPROVED
        super().save(*args, **kwargs)

    def is_approved(self):
        return self.verification_status == self.VERIFICATION_APPROVED

    def trades_display(self):
        lookup = TradeCategory.get_label_map()
        return [lookup.get(t, t) for t in (self.trades or [])]

    def service_towns_display(self):
        return ', '.join(self.service_towns or [])

    def public_completed_job_count(self):
        """Count of completed jobs with public reviews."""
        return PublicReview.objects.filter(ratee=self.user).count()

    def get_public_rating_breakdown(self):
        """
        Get average rating for each criterion.
        Returns dict with criterion averages.
        Overall is computed from these, never stored.
        """
        from django.db.models import Avg
        
        reviews = PublicReview.objects.filter(ratee=self.user)
        if not reviews.exists():
            return None
        
        breakdown = reviews.aggregate(
            reliability_punctuality=Avg('reliability_punctuality'),
            quote_price_accuracy=Avg('quote_price_accuracy'),
            value_for_money=Avg('value_for_money'),
            service_quality_workmanship=Avg('service_quality_workmanship'),
            communication_after_service=Avg('communication_after_service'),
            timeline_schedule_delivery=Avg('timeline_schedule_delivery'),
        )
        
        # Compute overall average
        if breakdown['reliability_punctuality']:
            values = [
                breakdown['reliability_punctuality'],
                breakdown['quote_price_accuracy'],
                breakdown['value_for_money'],
                breakdown['service_quality_workmanship'],
                breakdown['communication_after_service'],
                breakdown['timeline_schedule_delivery'],
            ]
            breakdown['overall'] = sum(values) / len(values)
        
        return breakdown


# ── Task ──────────────────────────────────────────────────────────────────────

class TradeCategory(models.Model):
    """Trade categories can now be M2M on Task."""
    name  = models.CharField(max_length=50, unique=True)
    icon  = models.CharField(max_length=10, blank=True)
    slug  = models.SlugField(unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='children')
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def get_choices(cls):
        """
        Live (slug, "icon name") choices for job/trade categories — the single
        source of truth for category pickers and skill selection across the
        site. Renaming a category here (e.g. Chef -> Catering) updates every
        picker and display label without a code change. Falls back to the
        static TRADE_CHOICES seed list only if the table is empty (e.g. a
        fresh install before migrations have seeded it).
        """
        rows = list(cls.objects.filter(active=True).order_by('name').values_list('slug', 'icon', 'name'))
        if not rows:
            from .constants import TRADE_CHOICES
            return TRADE_CHOICES
        return [(slug, f'{icon} {name}'.strip()) for slug, icon, name in rows]

    @classmethod
    def get_label_map(cls):
        """Dict of slug -> 'icon name' display label, for quick lookups."""
        return dict(cls.get_choices())


class Task(models.Model):
    STATUS_OPEN        = 'open'
    STATUS_ASSIGNED    = 'assigned'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_COMPLETED   = 'completed'
    STATUS_CANCELLED   = 'cancelled'
    STATUS_DISPUTED    = 'disputed'
    STATUS_CHOICES     = [
        (STATUS_OPEN,        'Open'),
        (STATUS_ASSIGNED,    'Assigned'),
        (STATUS_IN_PROGRESS, 'In Progress'),
        (STATUS_COMPLETED,   'Completed'),
        (STATUS_CANCELLED,   'Cancelled'),
        (STATUS_DISPUTED,    'Disputed'),
    ]

    client          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    title           = models.CharField(max_length=200)
    category        = models.CharField(max_length=20, blank=True)  # Slug into TradeCategory; see category_label
    categories      = models.ManyToManyField(TradeCategory, related_name='tasks', blank=True)  # New multi-category
    description     = models.TextField()
    budget          = models.DecimalField(max_digits=10, decimal_places=2)
    town            = models.CharField(max_length=50, choices=TOWN_CHOICES)
    preferred_date  = models.DateField(null=True, blank=True)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    assigned_tradie = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks'
    )
    # New task quality fields
    materials_required  = models.CharField(max_length=50, blank=True, choices=[
        ('client_supplies', 'Client supplies materials'),
        ('tradie_supplies', 'Tradie supplies materials'),
        ('not_sure', 'Not sure'),
    ])
    access_notes        = models.TextField(blank=True)
    parking_available   = models.CharField(max_length=50, blank=True, choices=[
        ('yes', 'Yes'),
        ('no', 'No'),
        ('not_sure', 'Not sure'),
    ])
    urgency             = models.CharField(max_length=50, blank=True, choices=[
        ('urgent', 'Urgent'),
        ('this_week', 'This week'),
        ('flexible', 'Flexible'),
    ])
    budget_type         = models.CharField(max_length=50, blank=True, choices=[
        ('fixed', 'Fixed price'),
        ('flexible', 'Flexible'),
        ('quote_needed', 'Quote needed'),
    ])
    materials_responsibility = models.CharField(max_length=50, blank=True, choices=[
        ('client_will_supply', 'Client will supply materials'),
        ('provider_should_supply', 'Local pro should supply materials'),
        ('provider_to_advise_after_inspection', 'Local pro should advise after inspection'),
        ('not_applicable', 'Not applicable'),
        ('not_sure', 'Not sure'),
    ])
    meals_provided              = models.BooleanField(default=False)
    parking_available_flag      = models.BooleanField(default=False)
    site_access_available       = models.BooleanField(default=False)
    tools_required              = models.BooleanField(default=False)
    rubbish_removal_required    = models.BooleanField(default=False)
    after_hours_required        = models.BooleanField(default=False)
    on_site_inspection_required = models.BooleanField(default=False)
    delivery_required           = models.BooleanField(default=False)
    clean_up_required           = models.BooleanField(default=False)
    client_provide_photos       = models.BooleanField(default=False)
    warranty_followup_requested = models.BooleanField(default=False)
    materials_notes             = models.TextField(blank=True)
    parking_notes               = models.TextField(blank=True)
    special_instructions        = models.TextField(blank=True)

    removed_at          = models.DateTimeField(null=True, blank=True)
    removed_by          = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='removed_tasks')
    removal_reason      = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    backdoor_monitoring_flag  = models.BooleanField(default=False, verbose_name='Platform Circumvention Flag')
    backdoor_monitoring_note  = models.TextField(blank=True, verbose_name='Platform Circumvention Note')
    backdoor_reviewed         = models.BooleanField(default=False, verbose_name='Circumvention Reviewed')
    backdoor_reviewed_at      = models.DateTimeField(null=True, blank=True, verbose_name='Circumvention Reviewed At')
    backdoor_reviewed_by      = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='backdoor_reviewed_tasks', verbose_name='Circumvention Reviewed By')
    # Final job value (set when completed)
    final_job_value     = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    completed_at        = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def category_label(self):
        """Display label for `category`, live from TradeCategory (editable in admin)."""
        if not self.category:
            return ''
        return TradeCategory.get_label_map().get(self.category, self.category)

    @property
    def quote_count(self):
        return self.quotes.count()

    def has_quoting_appointments(self):
        return self.quoting_appointments.exists()

    def has_accepted_quote(self):
        return self.quotes.filter(status=Quote.STATUS_ACCEPTED).exists()

    def has_platform_fee(self):
        return self.platform_fees.exists()

    def flag_backdoor_monitoring(self):
        if self.status == self.STATUS_CANCELLED or self.removed_at:
            if self.has_quoting_appointments() and not (
                self.has_accepted_quote() or self.assigned_tradie or self.status == self.STATUS_COMPLETED or self.has_platform_fee()
            ):
                self.backdoor_monitoring_flag = True
                if not self.backdoor_monitoring_note:
                    self.backdoor_monitoring_note = (
                        'Potential platform circumvention: quoting appointment requested/booked, '
                        'task removed before quote acceptance or completion.'
                    )

    def save(self, *args, **kwargs):
        self.flag_backdoor_monitoring()
        super().save(*args, **kwargs)


# ── Quote ─────────────────────────────────────────────────────────────────────

class Quote(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_DECLINED = 'declined'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_DECLINED, 'Declined'),
    ]

    task                            = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='quotes')
    tradie                          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quotes')
    price                           = models.DecimalField(max_digits=10, decimal_places=2)
    message                         = models.TextField()
    status                          = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    # New: Quote calculator and fee tracking
    minimum_take_home_amount        = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    customer_facing_quote           = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_platform_fee          = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_provider_take_home    = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fee_rule_applied                = models.CharField(max_length=100, blank=True)
    success_fee_rate_at_quote_time  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    success_fee_cap_at_quote_time   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    large_job_threshold_at_quote_time = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    large_job_fee_rate_at_quote_time = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Legacy fee fields
    base_price                      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    include_platform_fee            = models.BooleanField(default=False)
    platform_fee_rate_at_quote_time = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)  # 7.5, 10, etc
    platform_fee_cap_at_quote_time  = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # FJD $75
    client_quote_total              = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    estimated_tradie_take_home      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Quote detail fields
    includes_materials              = models.BooleanField(default=False, verbose_name='Includes materials')
    earliest_available_date         = models.DateField(null=True, blank=True)
    estimated_job_duration          = models.CharField(max_length=100, blank=True)  # e.g. "2-3 days"
    quote_includes = models.CharField(max_length=50, blank=True, choices=[
        ('labour_only', 'Labour only'),
        ('labour_and_materials', 'Labour and materials'),
        ('materials_to_be_confirmed_after_inspection', 'Materials to be confirmed after inspection'),
        ('service_only', 'Service only'),
        ('service_plus_products', 'Service plus products/supplies'),
        ('not_applicable', 'Not applicable'),
    ])
    warranty_or_followup_included   = models.BooleanField(default=False)
    created_at                      = models.DateTimeField(auto_now_add=True)
    # Discount selected at quote time — actually applied (and consumed) when the
    # job completes and a real PlatformFee is created. Mutually exclusive.
    used_founding_credit            = models.BooleanField(default=False)
    promo_code                      = models.ForeignKey('PromoCode', null=True, blank=True, on_delete=models.SET_NULL, related_name='quotes')
    estimated_discount_amount       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        unique_together = ('task', 'tradie')
        ordering = ['created_at']

    def __str__(self):
        return f'Quote by {self.tradie} on "{self.task}" – FJD ${self.price}'


# ── Message ───────────────────────────────────────────────────────────────────

class QuotingAppointment(models.Model):
    STATUS_REQUESTED = 'requested'
    STATUS_ACCEPTED  = 'accepted'
    STATUS_DECLINED  = 'declined'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_NO_SHOW   = 'no_show'
    STATUS_CHOICES   = [
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_ACCEPTED,  'Accepted'),
        (STATUS_DECLINED,  'Declined'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_NO_SHOW,   'No show'),
    ]

    task             = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='quoting_appointments')
    client           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_quoting_appointments')
    provider         = models.ForeignKey(User, on_delete=models.CASCADE, related_name='provider_quoting_appointments')
    appointment_note = models.TextField(blank=True)
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_REQUESTED)
    selected_slot    = models.ForeignKey('QuotingAppointmentSlot', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Appointment request by {self.provider} for "{self.task}"'

    def selected_slot_display(self):
        if self.selected_slot:
            return (
                f'{self.selected_slot.proposed_date} '
                f'{self.selected_slot.start_time.strftime("%H:%M")}–{self.selected_slot.end_time.strftime("%H:%M")} '
                f'({self.selected_slot.proposed_date})'
            )
        return ''

    def has_selected_slot(self):
        return self.selected_slot is not None


class QuotingAppointmentSlot(models.Model):
    quoting_appointment = models.ForeignKey(QuotingAppointment, on_delete=models.CASCADE, related_name='slots')
    proposed_date       = models.DateField()
    start_time          = models.TimeField()
    end_time            = models.TimeField()
    is_selected         = models.BooleanField(default=False)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['proposed_date', 'start_time']

    def __str__(self):
        return f'{self.proposed_date} {self.start_time.strftime("%H:%M")}–{self.end_time.strftime("%H:%M")}'


class Message(models.Model):
    task       = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='messages')
    sender     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender} → {self.recipient} [{self.task}]'


# ── Public review (client → tradie) ──────────────────────────────────────────
# Displayed on the Tradie Profile page.  Safe to query in public views.

SCORE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]
SCORE_CHOICES    = [(i, str(i)) for i in range(1, 6)]


class PublicReview(models.Model):
    task               = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='public_reviews')
    rater              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='public_reviews_given')
    ratee              = models.ForeignKey(User, on_delete=models.CASCADE, related_name='public_reviews_received')
    # Six public rating criteria for all service providers.
    reliability_punctuality   = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    quote_price_accuracy      = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    value_for_money           = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    service_quality_workmanship = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    communication_after_service  = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    timeline_schedule_delivery   = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS, default=5)
    comment                    = models.TextField(blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    objects = PublicReviewManager()

    class Meta:
        unique_together = ('task', 'rater')
        verbose_name = 'Public Review (Client → Provider)'
        verbose_name_plural = 'Public Reviews (Client → Provider)'

    def __str__(self):
        return f'Review by {self.rater} for {self.ratee} on "{self.task}"'

    @property
    def overall(self):
        """Compute overall rating from six public criteria (not stored)."""
        return (
            self.reliability_punctuality + self.quote_price_accuracy + self.value_for_money
            + self.service_quality_workmanship + self.communication_after_service + self.timeline_schedule_delivery
        ) / 6


class PrivateReview(models.Model):
    """
    Tradie's confidential rating of a client.

    ⚠️  ADMIN ONLY — never expose via views, URLs, or templates.
        Only import this model inside admin.py.
        Access via: PrivateReview.objects.admin_only()
    """
    task            = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='private_reviews')
    rater           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_reviews_given')
    ratee           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_reviews_received')
    # Five private criteria
    access_readiness = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    scope_clarity    = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    communication    = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    payment          = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    conduct          = models.IntegerField(choices=SCORE_CHOICES, validators=SCORE_VALIDATORS)
    comment          = models.TextField(blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    objects = PrivateReviewManager()

    class Meta:
        unique_together = ('task', 'rater')
        verbose_name        = '⚠️ Private Review — Dispute Record (Tradie → Client)'
        verbose_name_plural = '⚠️ Private Reviews — Dispute Records (Tradie → Client)'

    def __str__(self):
        return f'[PRIVATE] {self.rater} rated client {self.ratee} on "{self.task}"'


# ── Task Photos ───────────────────────────────────────────────────────────────

class TaskPhoto(models.Model):
    task        = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='photos')
    image       = models.ImageField(upload_to='task_photos/%Y/%m/%d/')
    caption     = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']
        verbose_name = 'Task Photo'
        verbose_name_plural = 'Task Photos'

    def __str__(self):
        return f'Photo for {self.task}'


# ── Promo Codes ────────────────────────────────────────────────────────────────

class PromoCode(models.Model):
    """
    Admin-issued discount codes a tradie can apply to a quote, reducing the
    platform fee charged when that job completes. Mutually exclusive with a
    tradie's own founding-member credit — only one discount applies per quote.
    """
    DISCOUNT_FIXED   = 'fixed'
    DISCOUNT_PERCENT = 'percent'
    DISCOUNT_TYPE_CHOICES = [
        (DISCOUNT_FIXED,   'Fixed amount off (FJD)'),
        (DISCOUNT_PERCENT, 'Percentage off'),
    ]

    code           = models.CharField(max_length=30, unique=True)
    discount_type  = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default=DISCOUNT_FIXED)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, help_text='Dollar amount, or percentage if "Percentage off" is selected.')
    active         = models.BooleanField(default=True)
    start_date     = models.DateField(null=True, blank=True, help_text='Leave blank for no start restriction.')
    end_date       = models.DateField(null=True, blank=True, help_text='Leave blank for no end restriction.')
    max_uses       = models.PositiveIntegerField(null=True, blank=True, help_text='Leave blank for unlimited uses.')
    times_used     = models.PositiveIntegerField(default=0)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Promo Code'
        verbose_name_plural = 'Promo Codes'

    def __str__(self):
        return self.code

    def is_valid_now(self):
        from django.utils import timezone
        today = timezone.localdate()
        if not self.active:
            return False
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        if self.max_uses is not None and self.times_used >= self.max_uses:
            return False
        return True

    def calculate_discount(self, fee_amount):
        """Discount amount for a given platform fee, capped so it never exceeds that fee."""
        fee_amount = Decimal(str(fee_amount))
        if self.discount_type == self.DISCOUNT_PERCENT:
            discount = (fee_amount * self.discount_value / Decimal('100')).quantize(Decimal('0.01'))
        else:
            discount = self.discount_value
        return min(discount, fee_amount)


# ── Platform Settings (fees) ──────────────────────────────────────────────────

class PlatformSettings(models.Model):
    """
    Configurable platform-wide settings.
    Only one active record at any time.
    """
    success_fee_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=7.5,
        help_text='Success fee percentage (e.g. 7.5 for 7.5%)'
    )
    success_fee_cap = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=75.00,
        help_text='Maximum fee cap per job (e.g. 75.00 for FJD $75)'
    )
    large_job_threshold = models.DecimalField(
        max_digits=10, decimal_places=2,
        default=5000.00,
        help_text='Customer-facing quote threshold for large job fee rate (e.g. 5000.00)'
    )
    large_job_fee_rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=3.00,
        help_text='Fee percentage for large jobs over threshold'
    )
    terms_version = models.CharField(
        max_length=20, default='1.0',
        help_text='Active terms version presented to users at registration'
    )
    active        = models.BooleanField(default=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform Settings'
        verbose_name_plural = 'Platform Settings'

    def __str__(self):
        return f'Platform Settings – {self.success_fee_rate}% / FJD ${self.success_fee_cap} cap'

    @classmethod
    def get_active(cls):
        """Get the active settings record."""
        return cls.objects.filter(active=True).first() or cls.objects.create()


# ── Platform Fee (created on job completion) ──────────────────────────────────

class PlatformFee(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_INVOICED = 'invoiced'
    STATUS_PAID     = 'paid'
    STATUS_WAIVED   = 'waived'
    STATUS_OVERDUE  = 'overdue'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_INVOICED, 'Invoiced'),
        (STATUS_PAID,     'Paid'),
        (STATUS_WAIVED,   'Waived'),
        (STATUS_OVERDUE,  'Overdue'),
    ]

    task               = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='platform_fees')
    tradie             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='platform_fees')
    final_job_value    = models.DecimalField(max_digits=10, decimal_places=2)
    fee_rate           = models.DecimalField(max_digits=5, decimal_places=2)  # Stored for audit trail
    fee_cap            = models.DecimalField(max_digits=10, decimal_places=2)  # Stored for audit trail
    gross_fee_amount   = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Before discount
    discount_amount    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fee_amount         = models.DecimalField(max_digits=10, decimal_places=2)  # What's actually owed (after discount)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Platform Fee'
        verbose_name_plural = 'Platform Fees'

    def __str__(self):
        return f'Fee: FJD ${self.fee_amount} on task "{self.task}" ({self.status})'


# ── Invoice ───────────────────────────────────────────────────────────────────

class Invoice(models.Model):
    STATUS_DRAFT   = 'draft'
    STATUS_SENT    = 'sent'
    STATUS_PAID    = 'paid'
    STATUS_OVERDUE = 'overdue'
    STATUS_VOID    = 'void'
    STATUS_CHOICES = [
        (STATUS_DRAFT,   'Draft'),
        (STATUS_SENT,    'Sent'),
        (STATUS_PAID,    'Paid'),
        (STATUS_OVERDUE, 'Overdue'),
        (STATUS_VOID,    'Void'),
    ]

    tradie          = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoices')
    invoice_number  = models.CharField(max_length=50, unique=True)
    period_start    = models.DateField(null=True, blank=True)
    period_end      = models.DateField(null=True, blank=True)
    total_amount    = models.DecimalField(max_digits=10, decimal_places=2)
    status          = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    due_date        = models.DateField()
    created_at      = models.DateTimeField(auto_now_add=True)
    sent_at         = models.DateTimeField(null=True, blank=True)
    paid_at         = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return f'Invoice {self.invoice_number} – {self.tradie} – FJD ${self.total_amount}'

    @property
    def is_overdue(self):
        from django.utils import timezone
        return self.status in (self.STATUS_SENT, self.STATUS_OVERDUE) and self.due_date < timezone.localdate()

    def void(self):
        """Void the invoice and return any invoiced PlatformFees to pending (unless already paid)."""
        PlatformFee.objects.filter(
            invoice_lines__invoice=self, status=PlatformFee.STATUS_INVOICED
        ).update(status=PlatformFee.STATUS_PENDING)
        self.status = self.STATUS_VOID
        self.save(update_fields=['status'])


# ── Invoice Line ──────────────────────────────────────────────────────────────

class InvoiceLine(models.Model):
    LINE_TYPE_CHOICES = [
        ('platform_fee',              'Platform Fee'),
        ('platform_circumvention_fee','Platform Circumvention Fee'),
        ('adjustment',                'Adjustment'),
        ('recovery_cost',             'Recovery Cost'),
    ]

    invoice         = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='lines')
    platform_fee    = models.ForeignKey(PlatformFee, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_lines')
    task            = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_lines')
    line_type       = models.CharField(max_length=30, choices=LINE_TYPE_CHOICES, default='platform_fee', blank=True)
    description     = models.TextField()
    final_job_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fee_rate        = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    amount          = models.DecimalField(max_digits=10, decimal_places=2)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Invoice Line Item'
        verbose_name_plural = 'Invoice Line Items'

    def __str__(self):
        return f'{self.invoice} – {self.description} – FJD ${self.amount}'


# ── Invoice Notification (in-platform / email / SMS log) ───────────────────────

class InvoiceNotification(models.Model):
    CHANNEL_IN_PLATFORM = 'in_platform'
    CHANNEL_EMAIL       = 'email'
    CHANNEL_SMS         = 'sms'
    CHANNEL_CHOICES = [
        (CHANNEL_IN_PLATFORM, 'In-platform message'),
        (CHANNEL_EMAIL,       'Email'),
        (CHANNEL_SMS,         'SMS / phone log'),
    ]

    invoice    = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='notifications')
    recipient  = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invoice_notifications')
    channel    = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    subject    = models.CharField(max_length=200, blank=True)
    body       = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Invoice Notification'
        verbose_name_plural = 'Invoice Notifications'

    def __str__(self):
        return f'{self.get_channel_display()} to {self.recipient} – {self.invoice.invoice_number}'


# ── Sponsor / Ad Banner ────────────────────────────────────────────────────────

class Sponsor(models.Model):
    PLACEMENT_CHOICES = [
        ('homepage',               'Homepage'),
        ('browse_tasks_sidebar',   'Browse Tasks Sidebar'),
        ('task_detail_sidebar',    'Task Detail Sidebar'),
        ('client_dashboard',       'Client Dashboard'),
        ('tradie_dashboard',       'Tradie Dashboard'),
        ('how_it_works',           'How It Works'),
    ]

    business_name  = models.CharField(max_length=200)
    banner_image   = models.ImageField(upload_to='sponsors/')
    destination_url = models.URLField()
    placements     = models.JSONField(default=list)  # list of placement slugs; can span multiple pages
    start_date     = models.DateField()
    end_date       = models.DateField()
    active         = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sponsor / Ad Banner'
        verbose_name_plural = 'Sponsors / Ad Banners'

    def __str__(self):
        return f'{self.business_name} – {", ".join(self.placements)}'

    @classmethod
    def get_active_for_placement(cls, placement):
        """
        Get active sponsors that include the given placement among their pages.
        Filtered in Python rather than via a JSONField `contains` lookup, since
        that lookup isn't supported on SQLite (only Postgres/MySQL) — this way
        works identically on both local dev and production.
        """
        from django.utils import timezone
        today = timezone.localdate()
        candidates = cls.objects.filter(
            active=True,
            start_date__lte=today,
            end_date__gte=today,
        )
        return [s for s in candidates if placement in s.placements]


# ── Terms Acceptance ─────────────────────────────────────────────────────────────

class TermsAcceptance(models.Model):
    user                           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='terms_acceptances')
    terms_version                  = models.CharField(max_length=20)
    accepted_at                    = models.DateTimeField(auto_now_add=True)
    ip_address                     = models.GenericIPAddressField(null=True, blank=True)
    user_agent                     = models.TextField(blank=True)
    accepted_platform_circumvention = models.BooleanField(default=False, verbose_name='Accepted Platform Circumvention Fee policy')
    accepted_invoicing_terms       = models.BooleanField(default=False, verbose_name='Accepted invoicing / payment obligations')

    class Meta:
        ordering = ['-accepted_at']
        verbose_name = 'Terms Acceptance'
        verbose_name_plural = 'Terms Acceptances'

    def __str__(self):
        return f'{self.user} – v{self.terms_version} at {self.accepted_at:%Y-%m-%d %H:%M}'


# ── Platform Circumvention Case ───────────────────────────────────────────────

class PlatformCircumventionCase(models.Model):
    STATUS_OPEN      = 'open'
    STATUS_INVOICED  = 'invoiced'
    STATUS_PAID      = 'paid'
    STATUS_WAIVED    = 'waived'
    STATUS_DISPUTED  = 'disputed'
    STATUS_CLOSED    = 'closed'
    STATUS_CHOICES   = [
        (STATUS_OPEN,     'Open'),
        (STATUS_INVOICED, 'Invoiced'),
        (STATUS_PAID,     'Paid'),
        (STATUS_WAIVED,   'Waived'),
        (STATUS_DISPUTED, 'Disputed'),
        (STATUS_CLOSED,   'Closed'),
    ]

    client             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='circumvention_cases_as_client')
    provider           = models.ForeignKey(User, on_delete=models.CASCADE, related_name='circumvention_cases_as_provider')
    task               = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name='circumvention_cases')
    total_job_value    = models.DecimalField(max_digits=10, decimal_places=2)
    fee_percentage     = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)
    minimum_fee        = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    client_fee_amount  = models.DecimalField(max_digits=10, decimal_places=2)
    provider_fee_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    evidence_notes     = models.TextField(blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)
    reviewed_by        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='circumvention_cases_reviewed')
    reviewed_at        = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Platform Circumvention Case'
        verbose_name_plural = 'Platform Circumvention Cases'

    def __str__(self):
        return f'Circumvention Case #{self.pk}: {self.client} & {self.provider} – FJD ${self.client_fee_amount} + ${self.provider_fee_amount} ({self.status})'

    @classmethod
    def calculate_fee(cls, total_job_value, fee_percentage=None, minimum_fee=None):
        from decimal import Decimal
        if fee_percentage is None:
            fee_percentage = Decimal('5.00')
        if minimum_fee is None:
            minimum_fee = Decimal('50.00')
        total_job_value = Decimal(str(total_job_value))
        fee_percentage  = Decimal(str(fee_percentage))
        minimum_fee     = Decimal(str(minimum_fee))
        fee = total_job_value * fee_percentage / Decimal('100')
        return max(fee, minimum_fee)


# ── Platform Notice (admin-issued communications) ────────────────────────────

class PlatformNotice(models.Model):
    TYPE_WELCOME           = 'welcome'
    TYPE_INVOICE           = 'invoice'
    TYPE_PAYMENT_REMINDER  = 'payment_reminder'
    TYPE_CIRCUMVENTION     = 'circumvention'
    TYPE_TERMS_UPDATE      = 'terms_update'
    TYPE_GENERAL           = 'general'
    TYPE_CHOICES = [
        (TYPE_WELCOME,          'Welcome Message'),
        (TYPE_INVOICE,          'Invoice Notice'),
        (TYPE_PAYMENT_REMINDER, 'Payment Reminder'),
        (TYPE_CIRCUMVENTION,    'Platform Circumvention Notice'),
        (TYPE_TERMS_UPDATE,     'Terms Update Notice'),
        (TYPE_GENERAL,          'General Notice'),
    ]

    CHANNEL_EMAIL       = 'email'
    CHANNEL_IN_PLATFORM = 'in_platform'
    CHANNEL_SMS         = 'sms'
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL,       'Email'),
        (CHANNEL_IN_PLATFORM, 'In-Platform'),
        (CHANNEL_SMS,         'SMS'),
    ]

    recipient   = models.ForeignKey(User, on_delete=models.CASCADE, related_name='platform_notices')
    notice_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    channel     = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_EMAIL)
    subject     = models.CharField(max_length=200)
    body        = models.TextField()
    sent_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='notices_sent')
    sent_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']
        verbose_name = 'Platform Notice'
        verbose_name_plural = 'Platform Notices'

    def __str__(self):
        return f'{self.get_notice_type_display()} → {self.recipient} – {self.subject}'


# ── Signals ─────────────────────────────────────────────────────────────────────

from django.db.models.signals import pre_delete
from django.dispatch import receiver


@receiver(pre_delete, sender=Invoice)
def _release_platform_fees_on_invoice_delete(sender, instance, **kwargs):
    """If an invoice is deleted, return any invoiced PlatformFees to pending (unless already paid)."""
    PlatformFee.objects.filter(
        invoice_lines__invoice=instance, status=PlatformFee.STATUS_INVOICED
    ).update(status=PlatformFee.STATUS_PENDING)
