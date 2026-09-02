from django.db import migrations, models


def seed_categories(apps, schema_editor):
    Category = apps.get_model('core_system', 'Category')
    defaults = [
        'Constitution', 'By-Laws', 'Minutes of Meeting', 'Memorandum',
        'Office Order', 'Resolution', 'Circular', 'Reports',
        'Certificates', 'Activity Documents', 'Other Files',
    ]
    for name in defaults:
        Category.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0085_document_pin_activity'),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('category_id_PK', models.AutoField(primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'CATEGORY',
                'ordering': ['name'],
            },
        ),
        migrations.RunPython(seed_categories, migrations.RunPython.noop),
    ]
