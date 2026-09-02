from django.core.management.base import BaseCommand
from django.utils import timezone

from core_system.models import (
    TransactionArchive,
    TransactionVerification,
)
from core_system.constants.status_constants import Status
from core_system.shared_view_utils import archive_transaction, _record_audit_trail


FINAL_STATUSES = {Status.APPROVED, Status.RELEASED, Status.PRESIDENT_APPROVED}


class Command(BaseCommand):
    help = "Archive all approved/released transactions for a fiscal term."

    def add_arguments(self, parser):
        parser.add_argument("term", type=str, help="Fiscal term, e.g. '2024-2025'")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be archived without writing.",
        )

    def handle(self, *args, **options):
        term = options["term"]
        dry_run = options["dry_run"]
        now = timezone.now()

        verifications = TransactionVerification.objects.filter(
            verification_status__in=FINAL_STATUSES,
        )

        archived_count = 0
        already_archived = 0

        for tv in verifications:
            exists = TransactionArchive.objects.filter(
                transaction_type=tv.table_name,
                record_id=tv.record_id,
                fiscal_term=term,
            ).exists()
            if exists:
                already_archived += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"[DRY RUN] Would archive {tv.table_name} #{tv.record_id} "
                    f"(status={tv.verification_status})"
                )
                archived_count += 1
                continue

            archive_transaction(
                table_name=tv.table_name,
                record_id=tv.record_id,
                officer=None,
            )
            TransactionArchive.objects.filter(
                transaction_type=tv.table_name,
                record_id=tv.record_id,
                fiscal_term__isnull=True,
            ).update(fiscal_term=term)

            _record_audit_trail(
                table="TRANSACTION_ARCHIVE",
                record_id=tv.record_id,
                action="TERM_ARCHIVED",
                actor=None,
                actor_type_override="SYSTEM",
                actor_name_override="Term Archive Cron",
                notes=f"Archived for fiscal term {term}",
            )
            archived_count += 1

        self.stdout.write(
            f"{'[DRY RUN] Would archive' if dry_run else 'Archived'} "
            f"{archived_count} record(s) for term '{term}'."
        )
        if already_archived:
            self.stdout.write(
                f"Skipped {already_archived} already-archived record(s)."
            )
