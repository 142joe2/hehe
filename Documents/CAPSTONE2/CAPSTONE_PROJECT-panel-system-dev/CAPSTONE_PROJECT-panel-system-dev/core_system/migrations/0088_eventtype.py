from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0087_rename_sensitive_r_table_n_c95688_idx_sensitive_r_module_b2b1eb_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='EventType',
            fields=[
                ('event_type_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'EVENT_TYPE',
                'ordering': ['name'],
            },
        ),
    ]
