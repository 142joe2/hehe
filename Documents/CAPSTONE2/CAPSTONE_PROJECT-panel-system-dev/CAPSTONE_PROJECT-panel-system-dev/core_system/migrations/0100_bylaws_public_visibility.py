# Adds public visibility controls for bylaws documents and secretary documents.

from django.db import migrations, models


def _backfill_public_documents(apps, schema_editor):
    """Promote legacy 'Other' bylaws files to 'Public Documents' and keep them visible.

    Existing 'Other' files were shown on the public resources page before this
    change, so migrate them to the new 'Public Documents' type with visibility on.
    """
    BylawsFile = apps.get_model("core_system", "BylawsFile")
    BylawsFile.objects.filter(document_type="Other").update(
        document_type="Public Documents",
        is_public_visible=True,
    )

    Document = apps.get_model("core_system", "Document")
    public_doc_types = [
        "Constitution", "By-Laws", "Resolution", "Memorandum",
        "Circular", "Office Order", "Financial Document", "Other",
    ]
    Document.objects.filter(
        document_type__in=public_doc_types,
        is_archived=False,
    ).update(is_public_visible=True)


class Migration(migrations.Migration):

    dependencies = [
        ('core_system', '0099_bylawsfile_document_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bylawsfile',
            name='document_type',
            field=models.CharField(
                choices=[
                    ('Constitution', 'Constitution'),
                    ('By-Laws', 'By-Laws'),
                    ('Public Documents', 'Public Documents'),
                    ('Other', 'Other'),
                ],
                default='By-Laws',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='bylawsfile',
            name='is_public_visible',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='document',
            name='is_public_visible',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            code=_backfill_public_documents,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
