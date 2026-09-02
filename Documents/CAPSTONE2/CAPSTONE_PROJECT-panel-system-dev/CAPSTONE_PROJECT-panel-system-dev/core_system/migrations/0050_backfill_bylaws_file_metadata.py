from django.db import migrations


def backfill_bylaws_file_metadata(apps, schema_editor):
    FinancialDocumentArchive = apps.get_model("core_system", "FinancialDocumentArchive")
    rows = FinancialDocumentArchive.objects.filter(related_module="bylaws_constants")
    mime_map = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pdf": "application/pdf",
        ".txt": "text/plain",
    }
    updated = []
    for row in rows:
        path = row.file_path or ""
        basename = path.split("/")[-1] if "/" in path else path
        if not row.file_name:
            row.file_name = basename
        if not row.file_type:
            ext = basename.lower().split(".")[-1]
            row.file_type = mime_map.get(f".{ext}", "application/octet-stream")
        updated.append(row)
    if updated:
        FinancialDocumentArchive.objects.bulk_update(
            updated, ["file_name", "file_type"]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0049_add_file_name_type_to_financialdocumentarchive"),
    ]

    operations = [
        migrations.RunPython(backfill_bylaws_file_metadata, migrations.RunPython.noop),
    ]
