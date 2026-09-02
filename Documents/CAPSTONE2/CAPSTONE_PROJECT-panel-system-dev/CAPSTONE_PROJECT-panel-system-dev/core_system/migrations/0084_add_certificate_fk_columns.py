from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0083_certificate_certificatesettings_and_more'),
    ]

    state_operations = [
        migrations.CreateModel(
            name='Certificate',
            fields=[
                ('certificate_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('certificate_number', models.CharField(max_length=50, unique=True)),
                ('pdf_file', models.FileField(blank=True, null=True, upload_to='certificates/')),
                ('email_status', models.CharField(choices=[('Pending', 'Pending'), ('Sent', 'Sent'), ('Failed', 'Failed')], default='Pending', max_length=20)),
                ('email_sent_at', models.DateTimeField(blank=True, null=True)),
                ('email_error', models.TextField(blank=True)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('downloaded_at', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'db_table': 'CERTIFICATE',
                'ordering': ['-generated_at'],
            },
        ),
        migrations.AddField(
            model_name='certificate',
            name='event',
            field=models.ForeignKey(db_column='event_id_FK', on_delete=django.db.models.deletion.CASCADE, related_name='certificates', to='core_system.event'),
        ),
        migrations.AddField(
            model_name='certificate',
            name='member',
            field=models.ForeignKey(db_column='member_id_FK', on_delete=django.db.models.deletion.CASCADE, related_name='certificates', to='core_system.member'),
        ),
        migrations.AlterUniqueTogether(
            name='certificate',
            unique_together={('member', 'event')},
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=state_operations,
        ),
    ]
