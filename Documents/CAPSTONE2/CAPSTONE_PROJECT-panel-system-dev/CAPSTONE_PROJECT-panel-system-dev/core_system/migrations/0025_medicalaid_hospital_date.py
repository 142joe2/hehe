from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0024_death_aid_add_relationship_group"),
    ]

    operations = [
        migrations.AddField(
            model_name="medicalaid",
            name="hospital_date",
            field=models.DateField(null=True, blank=True),
        ),
    ]
