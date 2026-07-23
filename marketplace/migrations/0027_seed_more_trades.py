"""
Seed additional job/trade categories: Joiner, Tiler, Roofer, Plasterer,
Welder, Fencing, Solar Installation.
"""
from django.db import migrations


TRADE_SEED = [
    ('joiner',    '🪵', 'Joiner'),
    ('tiler',     '🧱', 'Tiler'),
    ('roofer',    '🏠', 'Roofer'),
    ('plasterer', '🪣', 'Plasterer'),
    ('welder',    '🔥', 'Welder'),
    ('fencing',   '🚧', 'Fencing'),
    ('solar',     '☀️', 'Solar Installation'),
]


def seed_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    for slug, icon, name in TRADE_SEED:
        TradeCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'icon': icon, 'active': True},
        )


def reverse_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    TradeCategory.objects.filter(slug__in=[slug for slug, _, _ in TRADE_SEED]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0026_tradieprofile_safety_documents_reviewed'),
    ]

    operations = [
        migrations.RunPython(seed_categories, reverse_categories),
    ]
