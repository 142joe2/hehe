from django.db import migrations, models

def remove_duplicate_membership_fees(apps, schema_editor):
    MembershipFee = apps.get_model('core_system', 'MembershipFee')
    # Identify duplicates: same member_id_FK and receipt_number, keep the one with smallest fee_id_PK
    duplicates = (
        MembershipFee.objects
        .values('member_id_FK', 'receipt_number')
        .annotate(count=models.Count('fee_id_PK'))
        .filter(count__gt=1)
    )
    for dup in duplicates:
        fees = MembershipFee.objects.filter(member_id_FK=dup['member_id_FK'], receipt_number=dup['receipt_number']).order_by('fee_id_PK')
        # Keep first, delete rest
        first_fee = fees.first()
        if first_fee:
            ids_to_delete = fees.exclude(pk=first_fee.pk).values_list('pk', flat=True)
            MembershipFee.objects.filter(pk__in=ids_to_delete).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('core_system', '0006_medicalaid_hospital_name'),
        ('core_system', '0007_alter_membershipfee_unique_together'),
    ]
    operations = [
        migrations.RunPython(remove_duplicate_membership_fees, reverse_code=migrations.RunPython.noop),
    ]
