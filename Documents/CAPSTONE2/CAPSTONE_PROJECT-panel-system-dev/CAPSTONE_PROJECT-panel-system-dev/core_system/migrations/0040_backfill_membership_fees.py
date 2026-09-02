from django.db import migrations
from django.utils import timezone


def backfill_membership_fees(apps, schema_editor):
    Member = apps.get_model("core_system", "Member")
    MembershipFee = apps.get_model("core_system", "MembershipFee")
    OfficerUser = apps.get_model("core_system", "OfficerUser")
    TransactionVerification = apps.get_model("core_system", "TransactionVerification")

    from core_system.constants.policy_constants import get_membership_fee_amount

    system_officer, _ = OfficerUser.objects.get_or_create(
        username="system_backfill",
        defaults={
            "full_name": "System Backfill",
            "password_hash": "",
            "role": "System",
            "account_status": "Inactive",
        },
    )

    members = Member.objects.filter(
        membership_status__in=("Permanent", "Temporary"),
    ).exclude(
        member_id_PK__in=MembershipFee.objects.values("member_id_FK"),
    )

    now = timezone.now()
    count = 0
    for member in members:
        fee = MembershipFee.objects.create(
            member_id_FK=member,
            receipt_number=f"SYS-BACKFILL-{member.member_id_PK}-{now.strftime('%Y%m%d')}",
            amount=str(get_membership_fee_amount()),
            payment_date=member.date_joined or now.date(),
            payment_method="Pending",
            payment_status="Pending",
            recorded_by_user_id_FK=system_officer,
        )
        TransactionVerification.objects.create(
            table_name="membership_fee",
            record_id=fee.fee_id_PK,
            verification_status="Pending",
        )
        count += 1

    if count:
        print(f"  Backfilled {count} membership fee record(s) for existing members.")


class Migration(migrations.Migration):
    dependencies = [
        ("core_system", "0039_remove_membershipfee_month_covered"),
    ]

    operations = [
        migrations.RunPython(backfill_membership_fees, migrations.RunPython.noop),
    ]
