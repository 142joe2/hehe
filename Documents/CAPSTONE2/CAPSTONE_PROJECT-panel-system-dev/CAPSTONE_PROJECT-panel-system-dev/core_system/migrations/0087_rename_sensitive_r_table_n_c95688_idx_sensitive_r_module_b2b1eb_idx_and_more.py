# Manually created: adds qr_data field to Member with unique constraint

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0086_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='member',
            name='qr_data',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
