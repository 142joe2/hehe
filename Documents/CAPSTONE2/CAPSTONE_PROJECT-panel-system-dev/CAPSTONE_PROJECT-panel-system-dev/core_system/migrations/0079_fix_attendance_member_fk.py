# Generated manually to fix missing member_id_FK column in ATTENDANCE table

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0078_rename_sensitive_r_table_n_c95688_idx_sensitive_r_module_b2b1eb_idx_and_more'),
    ]

    operations = [
        # Add the missing member_id_FK column if it doesn't exist
        migrations.AddField(
            model_name='attendance',
            name='member_id_FK',
            field=models.ForeignKey(
                db_column='member_id_FK',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='attendance_records',
                to='core_system.member'
            ),
        ),
    ]
