from django.db import migrations


DEPARTMENTS = [
    ("College of Engineering", "COE"),
    ("College of Science", "CS"),
    ("College of Education", "CED"),
    ("College of Business and Management", "CBM"),
    ("College of Arts and Letters", "CAL"),
    ("College of Agriculture", "CA"),
    ("College of Information Technology", "CIT"),
    ("College of Nursing", "CN"),
    ("College of Law", "CL"),
    ("Administration", "ADMIN"),
    ("Finance Office", "FINANCE"),
    ("Human Resources", "HR"),
]


def seed_departments(apps, schema_editor):
    Department = apps.get_model("core_system", "Department")
    for name, code in DEPARTMENTS:
        Department.objects.get_or_create(
            code=code,
            defaults={"name": name, "is_active": True},
        )


def reverse_departments(apps, schema_editor):
    Department = apps.get_model("core_system", "Department")
    Department.objects.filter(code__in=[code for _, code in DEPARTMENTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core_system", "0056_add_officeruser_department_fk"),
    ]

    operations = [
        migrations.RunPython(seed_departments, reverse_departments),
    ]
