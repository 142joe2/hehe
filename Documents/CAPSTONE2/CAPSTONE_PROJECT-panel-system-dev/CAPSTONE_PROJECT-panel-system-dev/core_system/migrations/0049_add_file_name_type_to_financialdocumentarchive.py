from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0048_alter_aidtrackingpost_finish_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="financialdocumentarchive",
            name="file_name",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="financialdocumentarchive",
            name="file_type",
            field=models.CharField(default="", max_length=100),
            preserve_default=False,
        ),
    ]
