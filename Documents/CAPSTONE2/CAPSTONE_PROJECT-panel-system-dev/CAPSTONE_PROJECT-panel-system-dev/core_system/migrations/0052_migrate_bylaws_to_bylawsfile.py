from django.db import migrations


def migrate_existing_bylaws(apps, schema_editor):
    BylawsFile = apps.get_model("core_system", "BylawsFile")
    FinancialDocumentArchive = apps.get_model("core_system", "FinancialDocumentArchive")
    OfficerUser = apps.get_model("core_system", "OfficerUser")

    old_files = FinancialDocumentArchive.objects.filter(
        related_module="bylaws_constants"
    ).order_by("-uploaded_at")

    migrated = []
    for old in old_files:
        if not old.file_path:
            continue

        try:
            from django.core.files.storage import default_storage
            if not default_storage.exists(old.file_path):
                continue

            file_obj = default_storage.open(old.file_path, "rb")
            data = file_obj.read()
            file_obj.close()
        except Exception:
            continue

        uploader = None
        if old.uploaded_by_user_id_FK_id:
            try:
                uploader = OfficerUser.objects.get(pk=old.uploaded_by_user_id_FK_id)
            except OfficerUser.DoesNotExist:
                uploader = None

        migrated.append(BylawsFile(
            file_name=old.file_name or old.file_path.split("/")[-1],
            file_type=old.file_type or "application/octet-stream",
            file_data=data,
            file_size=len(data),
            file_hash=old.file_hash or "",
            verification_status=old.verification_status or "Active",
            uploaded_by_user_id_FK=uploader,
            uploaded_at=old.uploaded_at,
        ))

    if migrated:
        BylawsFile.objects.bulk_create(migrated)


def reverse_migrate(apps, schema_editor):
    BylawsFile = apps.get_model("core_system", "BylawsFile")
    BylawsFile.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0051_bylawsfile"),
    ]

    operations = [
        migrations.RunPython(migrate_existing_bylaws, reverse_migrate),
    ]
