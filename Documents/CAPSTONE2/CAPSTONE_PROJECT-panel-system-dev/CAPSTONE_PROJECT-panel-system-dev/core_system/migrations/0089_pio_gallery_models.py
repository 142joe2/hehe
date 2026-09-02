from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0088_eventtype'),
    ]

    operations = [
        migrations.CreateModel(
            name='Album',
            fields=[
                ('album_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_albums', to='core_system.officeruser')),
                ('event', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='albums', to='core_system.event')),
            ],
            options={
                'db_table': 'ALBUM',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Photo',
            fields=[
                ('photo_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('image', models.ImageField(upload_to='gallery/%Y/%m/')),
                ('caption', models.CharField(blank=True, max_length=255)),
                ('is_featured', models.BooleanField(default=False)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('album', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='core_system.album')),
                ('uploaded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_photos', to='core_system.officeruser')),
            ],
            options={
                'db_table': 'PHOTO',
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
