from django.db import migrations

def fix_member_types(apps, schema_editor):
    """Update all 'Officer-Member' member_type values to 'Member'"""
    Member = apps.get_model('core_system', 'Member')
    Member.objects.filter(member_type='Officer-Member').update(member_type='Member')

def reverse_fix(apps, schema_editor):
    """Reverse: This is a data fix, so we don't reverse it"""
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0064_add_member_registration_request'),
    ]

    operations = [
        migrations.RunPython(fix_member_types, reverse_fix),
    ]
