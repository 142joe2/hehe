from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0038_alter_medicalaid_hospital_date"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="membershipfee",
            name="month_covered",
        ),
    ]
