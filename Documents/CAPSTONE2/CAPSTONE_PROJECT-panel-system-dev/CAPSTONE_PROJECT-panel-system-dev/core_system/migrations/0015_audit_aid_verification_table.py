from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('core_system', '0014_auditorpaymentverification'),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditorAidVerification',
            fields=[
                ('auditor_aid_verification_id_PK', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID', db_column='auditor_aid_verification_id_PK')),
                ('target_table', models.CharField(max_length=50)),
                ('target_record_id', models.IntegerField()),
                ('verified_at', models.DateTimeField()),
                ('result_status', models.CharField(max_length=50)),
                ('auditor_remarks', models.TextField()),
                ('evidence_file_path', models.CharField(max_length=500, null=True, blank=True)),
                ('evidence_file_hash', models.CharField(max_length=255, null=True, blank=True)),
                ('auditor_id_FK', models.ForeignKey(on_delete=django.db.models.deletion.RESTRICT, db_column='auditor_id_FK', related_name='auditor_aid_verifications', to='core_system.officeruser')),
            ],
            options={
                'db_table': 'AUDITOR_AID_VERIFICATION',
            },
        ),
        migrations.AddConstraint(
            model_name='auditoraidverification',
            constraint=models.UniqueConstraint(fields=('target_table', 'target_record_id'), name='uq_auditor_aid_verif_target'),
        ),
    ]

