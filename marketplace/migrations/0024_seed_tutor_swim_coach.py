"""
Seed two new job/trade categories: Tutor and Swim Coach.
"""
from django.db import migrations


def seed_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    TradeCategory.objects.get_or_create(
        slug='tutor',
        defaults={'name': 'Tutor', 'icon': '📚', 'active': True},
    )
    TradeCategory.objects.get_or_create(
        slug='swim_coach',
        defaults={'name': 'Swim Coach', 'icon': '🏊', 'active': True},
    )


def reverse_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    TradeCategory.objects.filter(slug__in=['tutor', 'swim_coach']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0023_marketlisting_use_founding_credit_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_categories),
    ]
