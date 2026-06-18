from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0003_alter_tradecategory_options_tradecategory_active_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='publicreview',
            old_name='punctuality',
            new_name='reliability_punctuality',
        ),
        migrations.RenameField(
            model_name='publicreview',
            old_name='quote_accuracy',
            new_name='quote_price_accuracy',
        ),
        migrations.RenameField(
            model_name='publicreview',
            old_name='price_value',
            new_name='value_for_money',
        ),
        migrations.RenameField(
            model_name='publicreview',
            old_name='workmanship',
            new_name='service_quality_workmanship',
        ),
        migrations.RenameField(
            model_name='publicreview',
            old_name='after_service_care',
            new_name='communication_after_service',
        ),
        migrations.RenameField(
            model_name='publicreview',
            old_name='timeline_score',
            new_name='timeline_schedule_delivery',
        ),
    ]
