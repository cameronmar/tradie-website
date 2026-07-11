from django.db import migrations, models


def copy_placement_to_placements(apps, schema_editor):
    Sponsor = apps.get_model('marketplace', 'Sponsor')
    for sponsor in Sponsor.objects.all():
        old_value = getattr(sponsor, 'placement', None)
        sponsor.placements = [old_value] if old_value else []
        sponsor.save(update_fields=['placements'])


def copy_placements_to_placement(apps, schema_editor):
    Sponsor = apps.get_model('marketplace', 'Sponsor')
    for sponsor in Sponsor.objects.all():
        sponsor.placement = sponsor.placements[0] if sponsor.placements else ''
        sponsor.save(update_fields=['placement'])


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0014_seed_trade_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsor',
            name='placements',
            field=models.JSONField(default=list),
        ),
        migrations.RunPython(copy_placement_to_placements, copy_placements_to_placement),
        migrations.RemoveField(
            model_name='sponsor',
            name='placement',
        ),
    ]
