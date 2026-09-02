from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0058_add_officeruser_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_sheet",
            field=models.FileField(
                blank=True,
                help_text="Uploaded salary deduction accounting sheet",
                null=True,
                upload_to="deduction_sheets/",
            ),
        ),
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_batch_reference",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Reference or batch number from the salary deduction sheet",
                max_length=100,
            ),
        ),
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_payroll_period",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Payroll period covered (e.g. 2026-07)",
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_sheet_uploaded_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the deduction sheet was uploaded",
                null=True,
            ),
        ),
    ]
