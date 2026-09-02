from django.core.management.base import BaseCommand
from django.db import connection
from core_system.models import (
    Contribution, AidTrackingPost, TransactionArchive,
    DeathAid, MedicalAid, Claimant, SupportingProof,
    FundTransaction, TransactionVerification, GlobalAuditTrail,
    OutgoingEmail, FinancialDocumentArchive, AuditFindingsReport,
    MembershipFee, MonthlyDues, PayrollBatch, PayrollDeduction,
    Member, OfficerUser,
)

DELETE_ORDER = [
    SupportingProof,
    Contribution,
    FundTransaction,
    AidTrackingPost,
    TransactionVerification,
    DeathAid,
    MedicalAid,
    Claimant,
    GlobalAuditTrail,
    OutgoingEmail,
    FinancialDocumentArchive,
    AuditFindingsReport,
    TransactionArchive,
]


class Command(BaseCommand):
    help = "Remove all aid/medical/contribution/fund/verification data, keeping members, dues, and payroll."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        total = 0

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN — no data will be deleted ==="))
        else:
            self.stdout.write("Cleaning aid-related data...")

        # Only delete aid-related TransactionArchive records, not fee/dues archives
        archive_types_to_delete = ["death_aid", "medical_aid", "aid_post_payment", "contribution"]

        for model in DELETE_ORDER:
            name = model._meta.db_table
            if model is TransactionArchive:
                qs = model.objects.filter(transaction_type__in=archive_types_to_delete)
                count = qs.count()
            else:
                qs = model.objects.all()
                count = qs.count()
            if count == 0:
                self.stdout.write(f"  {name}: 0 rows (nothing to delete)")
            else:
                if dry_run:
                    self.stdout.write(f"  {name}: {count} rows WILL be deleted")
                else:
                    qs.delete()
                    self.stdout.write(f"  {name}: {count} rows deleted")
                total += count

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Total: {total} rows would be deleted."))
            self.stdout.write(self.style.WARNING("Run without --dry-run to execute."))
        else:
            self._reset_sequences()
            self.stdout.write(self.style.SUCCESS(f"Done. {total} rows deleted. Members, dues, and payroll retained."))

    def _reset_sequences(self):
        cursor = connection.cursor()
        tables = [
            "CONTRIBUTION", "AID_TRACKING_POST", "transaction_archive",
            "DEATH_AID", "MEDICAL_AID", "CLAIMANT", "supporting_proof",
            "FUND_TRANSACTION", "TRANSACTION_VERIFICATION",
            "GLOBAL_AUDIT_TRAIL", "OUTGOING_EMAIL",
            "financial_document_archive", "audit_findings_report",
        ]
        for table in tables:
            try:
                cursor.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1;")
            except Exception:
                pass
        self.stdout.write("  Sequences reset.")
