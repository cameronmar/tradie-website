"""
Review queryset managers.

PublicReviewManager  — safe to use in any view or template context.
PrivateReviewManager — ADMIN / DISPUTE RECORDS ONLY.
                       Only import PrivateReview and this manager inside admin.py.
                       Never pass PrivateReview querysets to template context.
"""
from django.db import models


class PublicReviewManager(models.Manager):
    """Default manager for PublicReview. Safe for public-facing views."""

    def for_tradie(self, tradie_user):
        return self.get_queryset().filter(ratee=tradie_user)


class PrivateReviewManager(models.Manager):
    """
    ADMIN ONLY.  Never import or call this from views.py or any template.
    Private client ratings must remain invisible to clients and the public.
    """

    def admin_only(self):
        """Explicit guard: forces callers to acknowledge admin-only access."""
        return self.get_queryset()
