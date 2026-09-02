import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0091_officerprofile"),
    ]

    operations = [
        migrations.CreateModel(
            name="AnnouncementCategory",
            fields=[
                ("category_id_PK", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "ANNOUNCEMENT_CATEGORY",
                "ordering": ["name"],
            },
        ),
    ]
