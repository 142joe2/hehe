import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0112_pushsubscription_origin'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizationfundreport',
            name='auditor_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organizationfundreport',
            name='auditor_verified_by_user_id_FK',
            field=models.ForeignKey(blank=True, db_column='auditor_verified_by_user_id_FK', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='fund_reports_verified', to='core_system.officeruser'),
        ),
        migrations.AddField(
            model_name='organizationfundreport',
            name='return_reason',
            field=models.TextField(blank=True, default=''),
        ),
    ]
