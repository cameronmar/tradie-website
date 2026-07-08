from django.db import migrations, models


def forward_status(apps, schema_editor):
    TradieProfile = apps.get_model('marketplace', 'TradieProfile')
    TradieProfile.objects.filter(documents_verified=True).update(verification_status='approved')
    TradieProfile.objects.filter(documents_verified=False).update(verification_status='pending')


def reverse_status(apps, schema_editor):
    TradieProfile = apps.get_model('marketplace', 'TradieProfile')
    TradieProfile.objects.filter(verification_status='approved').update(documents_verified=True)
    TradieProfile.objects.exclude(verification_status='approved').update(documents_verified=False)


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0010_invoiceline_line_type_platformsettings_terms_version_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tradieprofile',
            name='verification_status',
            field=models.CharField(
                choices=[
                    ('pending', 'Pending review'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                    ('suspended', 'Suspended'),
                ],
                default='pending',
                max_length=20,
                verbose_name='Verification status',
            ),
        ),
        migrations.RunPython(forward_status, reverse_status),
    ]
