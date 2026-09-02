from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0050_backfill_bylaws_file_metadata"),
    ]

    operations = [
        migrations.CreateModel(
            name="BylawsFile",
            fields=[
                ("bylaws_file_id", models.AutoField(primary_key=True, serialize=False)),
                ("file_name", models.CharField(max_length=255)),
                ("file_type", models.CharField(max_length=100)),
                ("file_data", models.BinaryField()),
                ("file_size", models.IntegerField()),
                ("file_hash", models.CharField(max_length=255)),
                ("verification_status", models.CharField(default="Active", max_length=50)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("uploaded_by_user_id_FK", models.ForeignKey(
                    db_column="uploaded_by_user_id_FK",
                    on_delete=django.db.models.deletion.RESTRICT,
                    to="core_system.officeruser",
                )),
            ],
            options={
                "db_table": "bylaws_files",
            },
        ),
    ]
