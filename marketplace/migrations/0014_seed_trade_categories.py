"""
Seed TradeCategory from the legacy TRADE_CHOICES constant, idempotently
(by slug), so job/trade categories become editable from the admin instead
of hardcoded in Python. Existing TradeCategory rows are left untouched.
"""
from django.db import migrations


TRADE_SEED = [
    ('plumbing',     '🔧 Plumbing'),
    ('electrical',   '⚡ Electrical'),
    ('cleaning',     '🧹 Cleaning'),
    ('gardening',    '🌿 Gardening'),
    ('carpentry',    '🪚 Carpentry'),
    ('painting',     '🎨 Painting'),
    ('aircon',       '❄️ Air Conditioning'),
    ('removalist',   '🚛 Removalist'),
    ('building',     '🏗️ Building'),
    ('locksmith',    '🔒 Locksmith'),
    ('it',           '🖥️ IT / Tech'),
    ('pest',         '🐛 Pest Control'),
    ('other',        '🔨 Other'),
    ('chef',         '🍳 Chef'),
    ('baker',        '🥐 Baker'),
    ('mechanic',     '🛠️ Mechanic'),
    ('photographer', '📸 Photographer'),
    ('makeup',       '💄 Makeup Artist'),
]


def seed_trade_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    for slug, label in TRADE_SEED:
        icon, _, name = label.partition(' ')
        TradeCategory.objects.get_or_create(
            slug=slug,
            defaults={'name': name, 'icon': icon, 'active': True},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0013_alter_task_category'),
    ]

    operations = [
        migrations.RunPython(seed_trade_categories, noop_reverse),
    ]
