from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0034_aidtrackingpost_finish_skip_remaining_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OutboundEmail",
            fields=[
                ("outbound_id_PK", models.AutoField(primary_key=True, serialize=False)),
                ("category", models.CharField(
                    max_length=20,
                    choices=[
                        ("report", "Report"),
                        ("notification", "Notification"),
                    ],
                )),
                ("source_type", models.CharField(max_length=50, blank=True, null=True)),
                ("subject", models.CharField(max_length=255)),
                ("body_html", models.TextField()),
                ("recipients", models.JSONField()),
                ("attachment_meta", models.JSONField(blank=True, null=True)),
                ("send_mode", models.CharField(
                    max_length=20,
                    choices=[
                        ("manual", "Manual"),
                        ("scheduled", "Scheduled"),
                    ],
                )),
                ("scheduled_send_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(
                    max_length=20,
                    choices=[
                        ("Draft", "Draft"),
                        ("Queued", "Queued"),
                        ("Sent", "Sent"),
                        ("Failed", "Failed"),
                        ("Cancelled", "Cancelled"),
                    ],
                    default="Draft",
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, null=True)),
                ("created_by_user_id_FK", models.ForeignKey(
                    on_delete=django.db.models.deletion.RESTRICT,
                    to="core_system.officeruser",
                    db_column="created_by_user_id_FK",
                    related_name="outbound_emails",
                )),
                ("related_report_id_FK", models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    to="core_system.auditfindingsreport",
                    db_column="related_report_id_FK",
                    related_name="outbound_emails",
                    blank=True,
                    null=True,
                )),
            ],
            options={
                "db_table": "OUTBOUND_EMAIL",
                "indexes": [
                    models.Index(
                        fields=["status", "scheduled_send_at"],
                        name="outbound_email_status_scheduled_idx",
                    ),
                ],
            },
        ),
    ]
