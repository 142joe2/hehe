from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0021_drop_old_audit_tables"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("subscription_id_PK", models.AutoField(primary_key=True, serialize=False)),
                (
                    "officer_id_FK",
                    models.ForeignKey(
                        "OfficerUser",
                        on_delete=models.CASCADE,
                        db_column="officer_id_FK",
                        related_name="push_subscriptions",
                    ),
                ),
                ("endpoint", models.URLField(max_length=500)),
                ("p256dh_key", models.CharField(max_length=256)),
                ("auth_key", models.CharField(max_length=128)),
                ("user_agent", models.CharField(max_length=500, null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "PUSH_SUBSCRIPTION",
                "unique_together": {("officer_id_FK", "endpoint")},
            },
        ),
    ]
