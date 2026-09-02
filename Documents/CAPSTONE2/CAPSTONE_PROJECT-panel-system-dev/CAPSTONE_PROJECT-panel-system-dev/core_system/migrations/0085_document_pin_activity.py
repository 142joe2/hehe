from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0084_add_certificate_fk_columns'),
    ]

    operations = [
        migrations.CreateModel(
            name='Certificate',
            fields=[
                ('certificate_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('certificate_number', models.CharField(max_length=50, unique=True)),
                ('member', models.ForeignKey(db_column='member_id_FK', on_delete=models.deletion.CASCADE, related_name='certificates', to='core_system.member')),
                ('event', models.ForeignKey(db_column='event_id_FK', on_delete=models.deletion.CASCADE, related_name='certificates', to='core_system.event')),
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
                'unique_together': {('member', 'event')},
            },
        ),
        migrations.CreateModel(
            name='CertificateSettings',
            fields=[
                ('settings_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('president_name', models.CharField(help_text='Name of ISU-CAUFA President', max_length=255)),
                ('president_position', models.CharField(default='ISU-CAUFA President', max_length=255)),
                ('president_signature', models.ImageField(blank=True, help_text='Upload PNG with transparent background', null=True, upload_to='signatures/')),
                ('secretary_name', models.CharField(help_text='Name of ISU-CAUFA Secretary', max_length=255)),
                ('secretary_position', models.CharField(default='ISU CAUFA Secretary', max_length=255)),
                ('secretary_signature', models.ImageField(blank=True, help_text='Upload PNG with transparent background', null=True, upload_to='signatures/')),
                ('faculty_regent_name', models.CharField(blank=True, help_text='Name of Faculty Regent or Authorized Official', max_length=255)),
                ('faculty_regent_position', models.CharField(default='Faculty Regent', max_length=255)),
                ('faculty_regent_signature', models.ImageField(blank=True, help_text='Upload PNG with transparent background', null=True, upload_to='signatures/')),
                ('organization_logo', models.ImageField(blank=True, help_text='Organization logo for certificate', null=True, upload_to='logos/')),
                ('header_text', models.CharField(default='Republic of the Philippines', max_length=255)),
                ('footer_text', models.TextField(blank=True, help_text='Optional footer text for certificate')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'Certificate Settings',
                'db_table': 'CERTIFICATE_SETTINGS',
            },
        ),
        migrations.CreateModel(
            name='DocumentPin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pinned_at', models.DateTimeField(auto_now_add=True)),
                ('document_id_FK', models.ForeignKey(db_column='document_id_FK', on_delete=django.db.models.deletion.CASCADE, related_name='pins', to='core_system.document')),
                ('officer_id_FK', models.ForeignKey(db_column='officer_id_FK', on_delete=django.db.models.deletion.CASCADE, related_name='document_pins', to='core_system.officeruser')),
            ],
            options={
                'db_table': 'DOCUMENT_PIN',
                'unique_together': {('document_id_FK', 'officer_id_FK')},
            },
        ),
        migrations.CreateModel(
            name='DocumentActivity',
            fields=[
                ('activity_id', models.AutoField(primary_key=True, serialize=False)),
                ('action', models.CharField(max_length=50)),
                ('officer_name', models.CharField(blank=True, max_length=255)),
                ('details', models.TextField(blank=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('document_id_FK', models.ForeignKey(blank=True, db_column='document_id_FK', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='activities', to='core_system.document')),
                ('officer_id_FK', models.ForeignKey(blank=True, db_column='officer_id_FK', null=True, on_delete=django.db.models.deletion.SET_NULL, to='core_system.officeruser')),
            ],
            options={
                'db_table': 'DOCUMENT_ACTIVITY',
                'ordering': ['-timestamp'],
            },
        ),
    ]
