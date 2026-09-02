from django.core.management.base import BaseCommand
from django.db import transaction

from core_system.models import FundTransaction


class Command(BaseCommand):
    help = (
        "Idempotently delete FundTransaction rows with source_type "
        "'salary_deduction_remittance'. These were double-counted inflows: the "
        "remittance is the same money as the member contributions, which are "
        "already booked as 'contribution' inflows at Auditor verify. Safe to "
        "re-run — it only deletes rows that still exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many rows would be deleted without deleting them.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        qs = FundTransaction.objects.filter(
            source_type="salary_deduction_remittance",
        )
        count = qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] Would delete {count} 'salary_deduction_remittance' "
                    "FundTransaction row(s)."
                )
            )
            return

        with transaction.atomic():
            deleted, _ = qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} 'salary_deduction_remittance' FundTransaction row(s)."
            )
        )