"""
Update the Baker category's icon from croissant to cake, and seed a new
Nanny category — both surfaced on the homepage's Popular Services grid.
"""
from django.db import migrations


def update_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    TradeCategory.objects.filter(slug='baker').update(icon='🎂')
    TradeCategory.objects.get_or_create(
        slug='nanny',
        defaults={'name': 'Nanny', 'icon': '👶', 'active': True},
    )


def reverse_categories(apps, schema_editor):
    TradeCategory = apps.get_model('marketplace', 'TradeCategory')
    TradeCategory.objects.filter(slug='baker').update(icon='🥐')
    TradeCategory.objects.filter(slug='nanny').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0017_alter_task_materials_responsibility'),
    ]

    operations = [
        migrations.RunPython(update_categories, reverse_categories),
    ]
