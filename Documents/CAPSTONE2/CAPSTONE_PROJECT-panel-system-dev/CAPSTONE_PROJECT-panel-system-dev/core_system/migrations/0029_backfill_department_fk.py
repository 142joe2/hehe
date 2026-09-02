from django.db import migrations


def backfill_departments(apps, schema_editor):
    Department = apps.get_model("core_system", "Department")
    Member = apps.get_model("core_system", "Member")
    db_alias = schema_editor.connection.alias

    dept_map = {}
    for member in Member.objects.using(db_alias).all():
        dept_name = member.department
        if not dept_name:
            continue
        if dept_name not in dept_map:
            dept, _ = Department.objects.using(db_alias).get_or_create(
                name=dept_name,
                defaults={"code": dept_name.upper()[:50]},
            )
            dept_map[dept_name] = dept
        member.department_id_FK = dept_map[dept_name]
        member.save(update_fields=["department_id_FK"])


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0028_department_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_departments, reverse_code=migrations.RunPython.noop),
    ]
