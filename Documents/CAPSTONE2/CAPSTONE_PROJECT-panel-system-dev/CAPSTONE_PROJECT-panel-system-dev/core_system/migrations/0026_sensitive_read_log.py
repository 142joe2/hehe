from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0025_medicalaid_hospital_date"),
    ]

    operations = [
        migrations.CreateModel(
            name="SensitiveReadLog",
            fields=[
                ("read_id", models.AutoField(db_column="read_id_PK", primary_key=True, serialize=False)),
                ("table_name", models.CharField(db_column="module", max_length=100)),
                ("record_id", models.IntegerField(blank=True, null=True)),
                ("reader_type", models.CharField(db_column="purpose", default="", max_length=50)),
                ("reader_id", models.IntegerField(blank=True, db_column="user_id_FK", null=True)),
                ("read_at", models.DateTimeField(auto_now_add=True, db_column="timestamp")),
            ],
            options={
                "db_table": "SENSITIVE_READ_LOG",
                "indexes": [
                    models.Index(
                        fields=["table_name", "record_id"],
                        name="SENSITIVE_R_module_b2b1eb_idx",
                    ),
                    models.Index(
                        fields=["read_at"],
                        name="SENSITIVE_R_timesta_d47548_idx",
                    ),
                ],
            },
        ),
    ]
