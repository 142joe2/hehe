from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0065_fix_officer_member_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='memberregistrationrequest',
            name='password_hash',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
