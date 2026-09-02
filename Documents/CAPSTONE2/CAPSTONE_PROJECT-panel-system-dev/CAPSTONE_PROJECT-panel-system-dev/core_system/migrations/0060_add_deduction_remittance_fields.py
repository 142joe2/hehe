from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0059_add_deduction_sheet_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_remitted_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Amount deposited from salary deduction remittance",
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_remitted_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the remittance was recorded in the system",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_remitted_date",
            field=models.DateField(
                blank=True,
                help_text="Date the remittance was deposited",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="aidtrackingpost",
            name="deduction_remittance_reference",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Bank reference or deposit slip number for the remittance",
                max_length=100,
            ),
        ),
    ]
