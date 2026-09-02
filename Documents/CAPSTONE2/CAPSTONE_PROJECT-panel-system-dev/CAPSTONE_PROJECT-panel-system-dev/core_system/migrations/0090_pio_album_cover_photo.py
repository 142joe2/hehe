from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0089_pio_gallery_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='album',
            name='cover_photo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='core_system.photo'),
        ),
    ]
