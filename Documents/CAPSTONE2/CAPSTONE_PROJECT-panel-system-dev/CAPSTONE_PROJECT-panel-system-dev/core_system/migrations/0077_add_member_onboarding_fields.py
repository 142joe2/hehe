from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0076_add_attendance_model"),
    ]

    operations = [
        migrations.AddField(
            model_name="member",
            name="pin_code",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="member",
            name="qr_code",
            field=models.CharField(max_length=255, null=True, blank=True, unique=True),
        ),
        migrations.AddField(
            model_name="member",
            name="emergency_contact",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="member",
            name="emergency_number",
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="member",
            name="setup_complete",
            field=models.BooleanField(default=False),
        ),
    ]