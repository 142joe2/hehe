from django.core.management.base import BaseCommand
from django.db.models import Sum
from core_system.models import (
    FundTransaction,
    TransactionArchive,
    Contribution,
    MembershipFee,
    MonthlyDues,
    Member,
    OfficerUser,
)


class Command(BaseCommand):
    help = "Backfill FundTransaction records from MembershipFee, MonthlyDues, TransactionArchive, and Contribution data"

    def handle(self, *args, **options):
        created_count = 0

        default_officer = OfficerUser.objects.filter(role__in=["President", "Treasurer"]).first()

        # --- 1. Inflows from MembershipFee records directly ---
        mf_count = 0
        for fee in MembershipFee.objects.all():
            member_name = fee.member_id_FK.full_name if fee.member_id_FK else "Unknown"
            _, was_created = FundTransaction.objects.get_or_create(
                source_type="membership_fee",
                source_id=fee.fee_id_PK,
                defaults={
                    "direction": "inflow",
                    "amount": fee.amount,
                    "description": f"Membership Fee — {member_name}",
                    "reference_number": fee.receipt_number or "",
                    "recorded_by_user_id_FK": fee.recorded_by_user_id_FK or default_officer,
                    "recorded_at": fee.payment_date,
                },
            )
            if was_created:
                mf_count += 1
                created_count += 1
        self.stdout.write(f"  → {mf_count} inflows from MembershipFee records")

        # --- 2. Inflows from MonthlyDues records directly ---
        md_count = 0
        for dues in MonthlyDues.objects.all():
            member_name = dues.member_id_FK.full_name if dues.member_id_FK else "Unknown"
            _, was_created = FundTransaction.objects.get_or_create(
                source_type="monthly_dues",
                source_id=dues.dues_id_PK,
                defaults={
                    "direction": "inflow",
                    "amount": dues.amount,
                    "description": f"Monthly Dues — {member_name} ({dues.month_covered})",
                    "reference_number": dues.receipt_number or dues.deduction_batch_reference or "",
                    "recorded_by_user_id_FK": dues.recorded_by_user_id_FK or default_officer,
                    "recorded_at": dues.payment_date,
                },
            )
            if was_created:
                md_count += 1
                created_count += 1
        self.stdout.write(f"  → {md_count} inflows from MonthlyDues records")

        # --- 3. Inflows from TransactionArchive (membership_fee, monthly_dues only) ---
        arch_count = 0
        for archive in TransactionArchive.objects.filter(
            transaction_type__in=["membership_fee", "monthly_dues"],
        ):
            _, was_created = FundTransaction.objects.get_or_create(
                source_type=archive.transaction_type,
                source_id=archive.record_id,
                defaults={
                    "direction": "inflow",
                    "amount": archive.amount,
                    "description": f"{dict(FundTransaction.SOURCE_TYPES).get(archive.transaction_type, archive.transaction_type)} — {archive.member_name}",
                    "reference_number": archive.release_reference or "",
                    "recorded_by_user_id_FK": archive.archived_by_user_id_FK or default_officer,
                    "recorded_at": archive.archived_at or archive.verified_at,
                },
            )
            if was_created:
                arch_count += 1
                created_count += 1
        self.stdout.write(f"  → {arch_count} inflows from fee/dues archives (if any)")

        # --- 4. Inflows from paid contributions ---
        contrib_count = 0
        for c in Contribution.objects.filter(status="PAID", paid_amount__gt=0):
            member_name = c.member_id_FK.full_name if c.member_id_FK else "Unknown"
            _, was_created = FundTransaction.objects.get_or_create(
                source_type="contribution",
                source_id=c.contribution_id_PK,
                defaults={
                    "direction": "inflow",
                    "amount": c.paid_amount,
                    "description": f"Aid contribution — {member_name}",
                    "recorded_by_user_id_FK": c.updated_by_user_id_FK or default_officer,
                    "recorded_at": c.updated_at,
                },
            )
            if was_created:
                contrib_count += 1
                created_count += 1
        self.stdout.write(f"  → {contrib_count} inflows from paid contributions")

        total_in = FundTransaction.objects.filter(direction="inflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        total_out = FundTransaction.objects.filter(direction="outflow").aggregate(
            total=Sum("amount")
        )["total"] or 0
        balance = total_in - total_out

        self.stdout.write(self.style.SUCCESS(
            f"\nDone! Created {created_count} new FundTransaction records."
            f"\n  Total inflows:  ₱{total_in:,.2f}"
            f"\n  Total outflows: ₱{total_out:,.2f}"
            f"\n  Fund balance:   ₱{balance:,.2f}"
        ))
